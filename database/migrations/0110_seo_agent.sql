-- 0110_seo_agent: storage for the SEO/GEO audit agent (apps/seo).
--
-- The agent crawls the storefront's own sitemap on a cron, parses each page
-- with HTMLRewriter, and records what is missing: schema markup, E-E-A-T
-- signals, broken internal links, and the indexing contradictions that caused
-- the real zero-indexing problem this was built for (pages listed in the
-- sitemap while serving `noindex`, or canonicalising somewhere else).
--
-- Three tables, and the split matters:
--
--   `seo_crawl_runs`  -- one row per crawl. Also the work queue: a manual run
--                        is a row with status 'queued', which the next cron
--                        tick picks up. That keeps the Python API completely
--                        free of a queue producer binding for the crawler.
--
--   `seo_pages`       -- what each URL actually served, per run. Kept rather
--                        than discarded after the rules run, because two of
--                        the checks are cross-page and cannot be answered from
--                        a single response: whether an internal link points at
--                        something that 404s, and whether a sitemap URL has
--                        any inbound internal link at all.
--
--   `seo_findings`    -- deduplicated by `fingerprint` across runs, not
--                        per-run rows. A page missing Product schema for six
--                        weeks is one finding that is six weeks old, not
--                        forty-two identical ones; `first_seen_at` is then a
--                        real age and the queue can be sorted by it. A finding
--                        the newest completed run did not re-observe is closed
--                        automatically as 'fixed'.
PRAGMA foreign_keys = ON;

CREATE TABLE seo_crawl_runs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL DEFAULT 'queued'
    CHECK (status IN ('queued', 'running', 'completed', 'failed')),
  trigger TEXT NOT NULL CHECK (trigger IN ('cron', 'manual')),
  -- Set for a manual run so the dashboard can say who asked for it.
  requested_by TEXT,
  base_url TEXT NOT NULL,
  queued_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  pages_discovered INTEGER NOT NULL DEFAULT 0,
  pages_crawled INTEGER NOT NULL DEFAULT 0,
  pages_failed INTEGER NOT NULL DEFAULT 0,
  findings_opened INTEGER NOT NULL DEFAULT 0,
  findings_closed INTEGER NOT NULL DEFAULT 0,
  error TEXT,
  FOREIGN KEY (requested_by) REFERENCES users(id) ON DELETE SET NULL
);

-- The cron picks up the oldest queued run; the dashboard lists newest first.
CREATE INDEX idx_seo_crawl_runs_status ON seo_crawl_runs(status, queued_at);
CREATE INDEX idx_seo_crawl_runs_recent ON seo_crawl_runs(queued_at DESC);

CREATE TABLE seo_pages (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  path TEXT NOT NULL,
  status_code INTEGER,
  -- Derived from the path, so a rule can require Product schema on
  -- /product/* without hard-coding route knowledge into every check.
  page_type TEXT NOT NULL,
  title TEXT,
  meta_description TEXT,
  canonical TEXT,
  robots TEXT,
  h1_count INTEGER NOT NULL DEFAULT 0,
  word_count INTEGER NOT NULL DEFAULT 0,
  images_without_alt INTEGER NOT NULL DEFAULT 0,
  -- Comma-separated JSON-LD `@type` values found on the page.
  schema_types TEXT NOT NULL DEFAULT '',
  -- Whether the page carried a visible author byline and a published date,
  -- which are the two E-E-A-T signals that can be read from markup alone.
  has_author INTEGER NOT NULL DEFAULT 0 CHECK (has_author IN (0, 1)),
  has_published_date INTEGER NOT NULL DEFAULT 0 CHECK (has_published_date IN (0, 1)),
  internal_links INTEGER NOT NULL DEFAULT 0,
  crawled_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE,
  UNIQUE (run_id, path)
);

CREATE INDEX idx_seo_pages_run ON seo_pages(run_id, path);

-- Every internal link seen, so broken links and orphans are both answerable
-- once the run has finished. Stored per run and cascaded away with it.
CREATE TABLE seo_page_links (
  run_id TEXT NOT NULL,
  from_path TEXT NOT NULL,
  to_path TEXT NOT NULL,
  PRIMARY KEY (run_id, from_path, to_path),
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE
);

CREATE INDEX idx_seo_page_links_target ON seo_page_links(run_id, to_path);

CREATE TABLE seo_findings (
  id TEXT PRIMARY KEY,
  -- rule + path, hashed by the agent. UNIQUE is what makes a recurring
  -- problem one ageing row instead of one row per run.
  fingerprint TEXT NOT NULL UNIQUE,
  rule TEXT NOT NULL,
  category TEXT NOT NULL
    CHECK (category IN ('schema', 'eeat', 'links', 'indexing', 'content')),
  severity TEXT NOT NULL CHECK (severity IN ('critical', 'high', 'medium', 'low')),
  path TEXT NOT NULL,
  page_type TEXT NOT NULL,
  summary TEXT NOT NULL,
  detail TEXT NOT NULL,
  evidence_json TEXT,
  -- What a person (or a generated PR) would actually change. Written by the
  -- rule that raised the finding, because that is the only place that knows.
  fix_hint TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'fixed', 'ignored')),
  first_seen_run_id TEXT NOT NULL,
  last_seen_run_id TEXT NOT NULL,
  first_seen_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  note TEXT,
  -- Set once a fix PR has been opened for this finding, so the dashboard can
  -- show the link instead of offering the button again.
  pr_url TEXT,
  pr_opened_at TEXT,
  FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

-- The queue view: open findings, worst first, oldest first within a severity.
CREATE INDEX idx_seo_findings_queue ON seo_findings(status, severity, first_seen_at);
CREATE INDEX idx_seo_findings_path ON seo_findings(path);
CREATE INDEX idx_seo_findings_rule ON seo_findings(rule, status);

-- --------------------------------------------------------------------------
-- Competitor keyword research.
--
-- What this can and cannot tell you, stated here because the distinction
-- decides how the numbers may be labelled in the UI:
--
--   It CAN see what a competitor *targets* -- which terms they put in titles,
--   H1s and meta descriptions, how many pages they build around a term, and
--   how heavily they link to those pages internally. Those are deliberate
--   editorial decisions and a fair proxy for where they are investing.
--
--   It CANNOT see what they *rank* for, or the search volume behind any of it.
--   That needs Search Console (our own property only) or a paid rankings API.
--   No column here should ever be presented as "keywords they rank for".
--
-- `gap_score` is therefore an investment-gap measure: high when a competitor
-- builds heavily around a term and this site barely mentions it. It is a
-- research prompt, not a ranking prediction.
CREATE TABLE seo_competitors (
  id TEXT PRIMARY KEY,
  label TEXT NOT NULL,
  origin TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused')),
  -- Set when the site's robots.txt disallows our crawler. The crawl then skips
  -- it permanently rather than retrying every night, and the dashboard can say
  -- why instead of showing a competitor that silently never produces data.
  robots_blocked INTEGER NOT NULL DEFAULT 0 CHECK (robots_blocked IN (0, 1)),
  last_crawled_at TEXT,
  last_error TEXT,
  notes TEXT,
  added_at TEXT NOT NULL,
  added_by TEXT,
  FOREIGN KEY (added_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE seo_competitor_pages (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  competitor_id TEXT NOT NULL,
  path TEXT NOT NULL,
  status_code INTEGER,
  title TEXT,
  meta_description TEXT,
  h1 TEXT,
  word_count INTEGER NOT NULL DEFAULT 0,
  inbound_internal_links INTEGER NOT NULL DEFAULT 0,
  crawled_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (competitor_id) REFERENCES seo_competitors(id) ON DELETE CASCADE,
  UNIQUE (run_id, competitor_id, path)
);

CREATE INDEX idx_seo_competitor_pages_run ON seo_competitor_pages(run_id, competitor_id);

-- One row per term per run, holding both sides of the comparison so the gap
-- is a stored fact rather than a join computed differently by each reader.
CREATE TABLE seo_keywords (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  term TEXT NOT NULL,
  -- How many words the term is. Two- and three-word phrases are where the
  -- useful signal is; single words are mostly category nouns everybody uses.
  term_words INTEGER NOT NULL DEFAULT 1,
  own_pages INTEGER NOT NULL DEFAULT 0,
  own_title_hits INTEGER NOT NULL DEFAULT 0,
  own_heading_hits INTEGER NOT NULL DEFAULT 0,
  competitor_pages INTEGER NOT NULL DEFAULT 0,
  competitor_title_hits INTEGER NOT NULL DEFAULT 0,
  competitor_heading_hits INTEGER NOT NULL DEFAULT 0,
  -- How many distinct competitors use it. A term two rivals both build around
  -- is a stronger signal than one obsessed over by a single site.
  competitor_count INTEGER NOT NULL DEFAULT 0,
  gap_score REAL NOT NULL DEFAULT 0,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE,
  UNIQUE (run_id, term)
);

CREATE INDEX idx_seo_keywords_gap ON seo_keywords(run_id, gap_score DESC);

-- Section headings seen on competitor pages, so a content structure they all
-- have and we lack (an FAQ block, a storage section) is visible as a gap
-- rather than having to be spotted by eye.
CREATE TABLE seo_content_chunks (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  competitor_id TEXT,
  source TEXT NOT NULL CHECK (source IN ('own', 'competitor')),
  page_type TEXT NOT NULL,
  heading TEXT NOT NULL,
  -- Normalised form the comparison is done on, so "Frequently asked questions"
  -- and "FAQs" are recognised as the same section.
  heading_key TEXT NOT NULL,
  occurrences INTEGER NOT NULL DEFAULT 1,
  observed_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (competitor_id) REFERENCES seo_competitors(id) ON DELETE CASCADE,
  UNIQUE (run_id, source, competitor_id, page_type, heading_key)
);

CREATE INDEX idx_seo_content_chunks_run ON seo_content_chunks(run_id, page_type);

-- --------------------------------------------------------------------------
-- Proposals: the part that removes the manual work.
--
-- A proposal is one concrete field change to one CMS row, with the value it
-- would replace stored alongside it. That shape is chosen for three reasons:
--
--   * **It is reviewable.** The dashboard can show before and after for every
--     change before anything is written.
--   * **It is reversible.** `previous_value` is captured at apply time, not
--     generation time, so a revert restores exactly what was there rather than
--     what the agent assumed was there.
--   * **It needs no deploy.** Every field named here already exists on
--     products, articles, recipes, categories and route_seo_overrides, so
--     applying a proposal is an UPDATE, not a code change. Pull requests are
--     only needed for the findings that are genuinely template-level (a route
--     emitting no JSON-LD), and those never become proposals.
--
-- Values are generated from the entity's own text plus a matched keyword
-- phrase, never invented. A proposal that cannot be built from real data is
-- simply not created, which is the same fail-closed posture the support bot's
-- templates take.
CREATE TABLE seo_proposals (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  entity_type TEXT NOT NULL
    CHECK (entity_type IN ('product', 'article', 'recipe', 'category', 'page', 'route')),
  -- The row's primary key, or the path for a 'route' override.
  entity_id TEXT NOT NULL,
  entity_label TEXT NOT NULL,
  path TEXT NOT NULL,
  field TEXT NOT NULL
    CHECK (field IN ('seo_title', 'seo_description', 'seo_keywords', 'indexing_policy')),
  -- What the field held when the proposal was generated. Shown as "before" in
  -- the dashboard; NOT what a revert restores.
  current_value TEXT,
  proposed_value TEXT NOT NULL,
  -- Captured during apply, and the value a revert writes back.
  previous_value TEXT,
  rationale TEXT NOT NULL,
  source TEXT NOT NULL CHECK (source IN ('gap', 'finding')),
  source_ref TEXT NOT NULL DEFAULT '',
  confidence REAL NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending', 'applied', 'rejected', 'superseded', 'reverted')),
  created_at TEXT NOT NULL,
  applied_at TEXT,
  applied_by TEXT,
  reverted_at TEXT,
  FOREIGN KEY (run_id) REFERENCES seo_crawl_runs(id) ON DELETE CASCADE,
  FOREIGN KEY (applied_by) REFERENCES users(id) ON DELETE SET NULL,
  -- One live proposal per field per entity per run.
  UNIQUE (run_id, entity_type, entity_id, field)
);

CREATE INDEX idx_seo_proposals_pending ON seo_proposals(status, confidence DESC);
CREATE INDEX idx_seo_proposals_entity ON seo_proposals(entity_type, entity_id);

-- Feature switch, off until an owner turns it on from Site Settings, matching
-- how every other roadmap feature is gated. `seo.auto_pr` stays off separately:
-- opening pull requests unattended is a second decision, and it should not ride
-- in on the back of enabling the crawl.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('seo.enabled', 'false', '2026-08-19T00:00:00Z'),
  ('seo.auto_pr', 'false', '2026-08-19T00:00:00Z'),
  ('seo.max_pages', '500', '2026-08-19T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_seo_manage', 'seo.manage', 'View SEO audit findings and run the site crawler');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'seo.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key = 'seo.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

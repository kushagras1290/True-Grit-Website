/**
 * Crawl orchestration: sitemap discovery, page fetching, finding lifecycle.
 *
 * **Why there is no queue.** The original sketch fanned out over Cloudflare
 * Queues. That was dropped for a resumable cron instead, and the reason is
 * operational rather than aesthetic: a queue is a piece of infrastructure
 * somebody has to create and bind before the first crawl can run, and it buys
 * nothing at this size. Instead `startRun` writes one `seo_pages` row per
 * discovered URL with a null status code, and `advanceRun` crawls whichever
 * rows are still null. That makes progress durable in the table itself, so an
 * invocation that hits a CPU limit, a deploy, or an isolate eviction simply
 * loses that batch and the next cron tick continues from where it stopped.
 * There is no state anywhere except D1, and no run can get permanently stuck
 * because a message was dropped.
 *
 * **Finding lifecycle.** `finaliseRun` diffs what this run saw against what is
 * currently open. Something still present is touched, something new is opened,
 * and something no longer observed is closed as fixed. That is what makes
 * `firstSeenAt` a real age rather than the timestamp of the most recent crawl,
 * and it means the dashboard can be sorted by "how long has this been broken",
 * which is the ordering an operator actually wants.
 */

import { evaluateCrawl, evaluatePage } from "./rules";
import { type Env, type Finding, type PageSnapshot, fingerprintFor, pageTypeFor } from "./types";
import { extractPage, normaliseInternalHref } from "./extract";
import { CRAWLER_USER_AGENT, fetchRobots, isAllowed } from "./robots";
import {
  type KeywordGap,
  type PageText,
  type TermStats,
  extractTerms,
  scoreGaps,
} from "./keywords";
import {
  SUPPORTED_FIELDS,
  type Proposal,
  type SeoEntity,
  headingKey,
  proposalsFor,
} from "./proposals";

/** Pages fetched per cron invocation. Sized to stay well inside a scheduled
 *  handler's budget with room for slow responses, since exceeding it costs a
 *  batch rather than a run. */
const BATCH_SIZE = 40;
/** Parallel fetches within a batch. Politeness toward our own origin as much
 *  as anything; the storefront is a Worker too and shares an account. */
const CONCURRENCY = 8;
const FETCH_TIMEOUT_MS = 15_000;
const USER_AGENT = "TrueGritSeoAgent/1.0 (+https://www.truegritin.com)";

const LOC_PATTERN = /<loc>\s*([^<\s]+)\s*<\/loc>/gi;

function nowIso(): string {
  return new Date().toISOString();
}

function newId(prefix: string): string {
  return `${prefix}_${crypto.randomUUID().replace(/-/g, "").slice(0, 24)}`;
}

async function fetchWithTimeout(url: string): Promise<Response> {
  // Workers have no default fetch timeout, and one hanging URL would otherwise
  // hold the whole batch until the invocation is killed.
  return fetch(url, {
    headers: { "user-agent": USER_AGENT, accept: "text/html,application/xhtml+xml" },
    redirect: "follow",
    signal: AbortSignal.timeout(FETCH_TIMEOUT_MS),
  });
}

/**
 * Every URL the sitemap advertises, as paths.
 *
 * Handles both shapes: `/sitemap.xml` is an index pointing at child sitemaps
 * on this site, and each child is a urlset. Anything that fails to fetch is
 * skipped rather than aborting discovery, because one broken child sitemap
 * should not cancel the audit of the rest of the site.
 */
export async function discoverSitemapPaths(origin: string, maxPages: number): Promise<string[]> {
  const seen = new Set<string>();
  const roots = [`${origin}/sitemap.xml`];
  const childSitemaps: string[] = [];

  for (const root of roots) {
    let body: string;
    try {
      const response = await fetchWithTimeout(root);
      if (!response.ok) continue;
      body = await response.text();
    } catch {
      continue;
    }
    const isIndex = /<sitemapindex/i.test(body);
    for (const match of body.matchAll(LOC_PATTERN)) {
      const loc = match[1];
      if (!loc) continue;
      if (isIndex) {
        childSitemaps.push(loc);
      } else {
        const path = normaliseInternalHref(loc, origin);
        if (path) seen.add(path);
      }
    }
  }

  for (const child of childSitemaps) {
    if (seen.size >= maxPages) break;
    try {
      const response = await fetchWithTimeout(child);
      if (!response.ok) continue;
      const body = await response.text();
      for (const match of body.matchAll(LOC_PATTERN)) {
        const loc = match[1];
        if (!loc) continue;
        const path = normaliseInternalHref(loc, origin);
        if (path) seen.add(path);
        if (seen.size >= maxPages) break;
      }
    } catch {
      continue;
    }
  }

  // The home page is not always in a sitemap and is always worth auditing.
  seen.add("/");
  return [...seen].slice(0, maxPages);
}

async function setting(env: Env, key: string, fallback: string): Promise<string> {
  const row = await env.DB.prepare("SELECT value FROM app_settings WHERE key = ?")
    .bind(key)
    .first<{ value: string }>();
  return row?.value ?? fallback;
}

export async function isEnabled(env: Env): Promise<boolean> {
  return (await setting(env, "seo.enabled", "false")) === "true";
}

/** Whether the daily cron tick should actually queue a run right now.
 *
 * The Cloudflare Cron Trigger itself still fires once a day (changing that
 * needs a deploy), but the *decision* to queue is dashboard-configurable:
 * `seo.schedule_days` is compared against the last cron-queued run's
 * timestamp, so "every 3 days" or "weekly" falls out of the same daily tick
 * without a different trigger. `0` (or unset) means manual-only -- the tick
 * checks in but never queues anything on its own; only the "Run crawl"
 * button does. */
export async function isScheduleDue(env: Env): Promise<boolean> {
  const days = Number.parseInt(await setting(env, "seo.schedule_days", "1"), 10);
  if (!Number.isFinite(days) || days <= 0) return false;
  const last = await env.DB.prepare(
    "SELECT queued_at FROM seo_crawl_runs WHERE trigger = 'cron' ORDER BY queued_at DESC LIMIT 1",
  ).first<{ queued_at: string }>();
  if (!last) return true;
  const elapsedMs = Date.now() - new Date(last.queued_at).getTime();
  return elapsedMs >= days * 24 * 60 * 60 * 1000;
}

/** Claim the oldest queued run, or null. The conditional UPDATE is the lock:
 *  two overlapping cron invocations cannot both claim the same row. */
export async function claimQueuedRun(env: Env): Promise<string | null> {
  const row = await env.DB.prepare(
    "SELECT id FROM seo_crawl_runs WHERE status = 'queued' ORDER BY queued_at LIMIT 1",
  ).first<{ id: string }>();
  if (!row) return null;

  const claimed = await env.DB.prepare(
    "UPDATE seo_crawl_runs SET status = 'running', started_at = ? WHERE id = ? AND status = 'queued'",
  )
    .bind(nowIso(), row.id)
    .run();
  return claimed.meta.changes > 0 ? row.id : null;
}

export async function enqueueRun(
  env: Env,
  trigger: "cron" | "manual",
  requestedBy: string | null = null,
): Promise<string> {
  const id = newId("seorun");
  await env.DB.prepare(
    "INSERT INTO seo_crawl_runs (id, status, trigger, requested_by, base_url, queued_at)" +
      " VALUES (?, 'queued', ?, ?, ?, ?)",
  )
    .bind(id, trigger, requestedBy, env.SITE_ORIGIN, nowIso())
    .run();
  return id;
}

/** Discover the URL set and record one placeholder row per page. */
export async function startRun(env: Env, runId: string): Promise<number> {
  const maxPages = Number.parseInt(await setting(env, "seo.max_pages", "500"), 10) || 500;
  const paths = await discoverSitemapPaths(env.SITE_ORIGIN, maxPages);
  const queuedAt = nowIso();

  // D1 batches are capped in practice, so this is chunked rather than sent as
  // one enormous statement list.
  for (let index = 0; index < paths.length; index += 50) {
    const chunk = paths.slice(index, index + 50);
    await env.DB.batch(
      chunk.map((path) =>
        env.DB.prepare(
          "INSERT OR IGNORE INTO seo_pages (id, run_id, path, page_type, crawled_at)" +
            " VALUES (?, ?, ?, ?, ?)",
        ).bind(newId("seopg"), runId, path, pageTypeFor(path), queuedAt),
      ),
    );
  }

  await env.DB.prepare("UPDATE seo_crawl_runs SET pages_discovered = ? WHERE id = ?")
    .bind(paths.length, runId)
    .run();
  return paths.length;
}

async function crawlOne(env: Env, runId: string, path: string): Promise<void> {
  const url = `${env.SITE_ORIGIN}${path}`;
  let snapshot: PageSnapshot;
  try {
    const response = await fetchWithTimeout(url);
    snapshot = await extractPage(response, path, env.SITE_ORIGIN);
  } catch (error) {
    // A page that could not be fetched at all is recorded as a 0 so the run
    // can complete and the failure shows up as a finding, rather than the row
    // staying null forever and the run never finishing.
    await env.DB.prepare(
      "UPDATE seo_pages SET status_code = 0, crawled_at = ? WHERE run_id = ? AND path = ?",
    )
      .bind(nowIso(), runId, path)
      .run();
    await env.DB.prepare("UPDATE seo_crawl_runs SET pages_failed = pages_failed + 1 WHERE id = ?")
      .bind(runId)
      .run();
    console.error(`seo.crawl_failed path=${path} error=${String(error)}`);
    return;
  }

  const statements = [
    env.DB.prepare(
      "UPDATE seo_pages SET status_code = ?, page_type = ?, title = ?, meta_description = ?," +
        " canonical = ?, robots = ?, h1_count = ?, word_count = ?, images_without_alt = ?," +
        " schema_types = ?, has_author = ?, has_published_date = ?, internal_links = ?," +
        " crawled_at = ? WHERE run_id = ? AND path = ?",
    ).bind(
      snapshot.statusCode,
      snapshot.pageType,
      snapshot.title || null,
      snapshot.metaDescription || null,
      snapshot.canonical || null,
      snapshot.robots || null,
      snapshot.h1Count,
      snapshot.wordCount,
      snapshot.imagesWithoutAlt,
      snapshot.schemaTypes.join(","),
      snapshot.hasAuthor ? 1 : 0,
      snapshot.hasPublishedDate ? 1 : 0,
      snapshot.internalLinks.length,
      nowIso(),
      runId,
      path,
    ),
  ];
  for (const target of snapshot.internalLinks) {
    statements.push(
      env.DB.prepare(
        "INSERT OR IGNORE INTO seo_page_links (run_id, from_path, to_path) VALUES (?, ?, ?)",
      ).bind(runId, path, target),
    );
  }
  await env.DB.batch(statements);
  await recordChunks(env, runId, "own", null, snapshot.pageType, snapshot.headings);
  await env.DB.prepare("UPDATE seo_crawl_runs SET pages_crawled = pages_crawled + 1 WHERE id = ?")
    .bind(runId)
    .run();
}

/** Crawl up to one batch. Returns true when pages remain for the next tick. */
export async function advanceRun(env: Env, runId: string): Promise<boolean> {
  const pending = await env.DB.prepare(
    "SELECT path FROM seo_pages WHERE run_id = ? AND status_code IS NULL LIMIT ?",
  )
    .bind(runId, BATCH_SIZE)
    .all<{ path: string }>();

  const paths = (pending.results ?? []).map((row) => row.path);
  if (paths.length === 0) return false;

  for (let index = 0; index < paths.length; index += CONCURRENCY) {
    const slice = paths.slice(index, index + CONCURRENCY);
    await Promise.all(slice.map((path) => crawlOne(env, runId, path)));
  }
  return paths.length === BATCH_SIZE;
}

/** Rebuild the snapshots this run recorded, for the cross-page rules. */
async function loadSnapshots(env: Env, runId: string): Promise<PageSnapshot[]> {
  const pages = await env.DB.prepare(
    "SELECT path, status_code, page_type, title, meta_description, canonical, robots," +
      " h1_count, word_count, images_without_alt, schema_types, has_author, has_published_date" +
      " FROM seo_pages WHERE run_id = ?",
  )
    .bind(runId)
    .all<Record<string, string | number | null>>();

  const links = await env.DB.prepare(
    "SELECT from_path, to_path FROM seo_page_links WHERE run_id = ?",
  )
    .bind(runId)
    .all<{ from_path: string; to_path: string }>();

  const linksByPath = new Map<string, string[]>();
  for (const row of links.results ?? []) {
    const existing = linksByPath.get(row.from_path) ?? [];
    existing.push(row.to_path);
    linksByPath.set(row.from_path, existing);
  }

  return (pages.results ?? []).map((row) => {
    const path = String(row.path);
    return {
      path,
      statusCode: Number(row.status_code ?? 0),
      pageType: pageTypeFor(path),
      title: String(row.title ?? ""),
      // Headings are not reloaded for the cross-page pass: they were already
      // folded into `seo_content_chunks` during the crawl, and no cross-page
      // rule reads them.
      h1: "",
      headings: [],
      metaDescription: String(row.meta_description ?? ""),
      canonical: String(row.canonical ?? ""),
      robots: String(row.robots ?? ""),
      h1Count: Number(row.h1_count ?? 0),
      wordCount: Number(row.word_count ?? 0),
      imagesWithoutAlt: Number(row.images_without_alt ?? 0),
      schemaTypes: String(row.schema_types ?? "")
        .split(",")
        .filter(Boolean),
      // Per-page schema detail is not persisted, so the cross-page pass works
      // from what the columns carry. The property-level schema rules already
      // ran during the crawl, when the parsed objects were in hand.
      malformedSchemaBlocks: 0,
      schemaObjects: [],
      hasAuthor: Number(row.has_author ?? 0) === 1,
      hasPublishedDate: Number(row.has_published_date ?? 0) === 1,
      internalLinks: linksByPath.get(path) ?? [],
      externalLinkCount: 0,
    };
  });
}

async function persistFindings(env: Env, runId: string, findings: Finding[]): Promise<void> {
  const timestamp = nowIso();
  const seen = new Set<string>();

  for (const finding of findings) {
    const fingerprint = fingerprintFor(finding.rule, finding.path);
    if (seen.has(fingerprint)) continue;
    seen.add(fingerprint);

    // One upsert covers both cases: a new problem is opened, and one already
    // in the table is touched and reopened if a previous run had closed it.
    await env.DB.prepare(
      `INSERT INTO seo_findings (
         id, fingerprint, rule, category, severity, path, page_type, summary, detail,
         evidence_json, fix_hint, status, first_seen_run_id, last_seen_run_id,
         first_seen_at, last_seen_at
       ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?)
       ON CONFLICT(fingerprint) DO UPDATE SET
         severity = excluded.severity,
         summary = excluded.summary,
         detail = excluded.detail,
         evidence_json = excluded.evidence_json,
         fix_hint = excluded.fix_hint,
         last_seen_run_id = excluded.last_seen_run_id,
         last_seen_at = excluded.last_seen_at,
         -- An ignored finding stays ignored when it recurs; a fixed one that
         -- came back is genuinely open again.
         status = CASE WHEN seo_findings.status = 'ignored' THEN 'ignored' ELSE 'open' END,
         resolved_at = CASE WHEN seo_findings.status = 'ignored' THEN seo_findings.resolved_at
                            ELSE NULL END`,
    )
      .bind(
        newId("seofnd"),
        fingerprint,
        finding.rule,
        finding.category,
        finding.severity,
        finding.path,
        finding.pageType,
        finding.summary,
        finding.detail,
        finding.evidence ? JSON.stringify(finding.evidence) : null,
        finding.fixHint,
        runId,
        runId,
        timestamp,
        timestamp,
      )
      .run();
  }

  // Anything open that this run did not re-observe has been fixed. Scoped to
  // findings whose page was actually visited, so a crawl that stopped early
  // cannot mass-close the rest of the site.
  const closed = await env.DB.prepare(
    `UPDATE seo_findings SET status = 'fixed', resolved_at = ?
      WHERE status = 'open' AND last_seen_run_id != ?
        AND path IN (SELECT path FROM seo_pages WHERE run_id = ? AND status_code IS NOT NULL)`,
  )
    .bind(timestamp, runId, runId)
    .run();

  await env.DB.prepare(
    "UPDATE seo_crawl_runs SET findings_opened = ?, findings_closed = ? WHERE id = ?",
  )
    .bind(seen.size, closed.meta.changes ?? 0, runId)
    .run();
}

// --- Competitor research ----------------------------------------------------

/** Pages fetched per competitor. Small on purpose: the goal is a read on what
 *  they put in titles and headings, and their top pages carry that. Crawling a
 *  rival's whole catalogue would be both slow and rude. */
const COMPETITOR_PAGE_LIMIT = 30;
/** Sequential fetches with a gap, rather than the parallelism used on our own
 *  origin. Someone else's server does not owe us throughput. */
const COMPETITOR_DELAY_MS = 700;

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function competitorPaths(origin: string, limit: number): Promise<string[]> {
  // Prefer their sitemap. Falling back to links from the home page keeps the
  // feature working for sites that do not publish one.
  const fromSitemap = await discoverSitemapPaths(origin, limit).catch(() => []);
  if (fromSitemap.length > 1) return fromSitemap.slice(0, limit);

  try {
    const response = await fetchWithTimeout(origin);
    if (!response.ok) return ["/"];
    const snapshot = await extractPage(response, "/", origin);
    return ["/", ...snapshot.internalLinks].slice(0, limit);
  } catch {
    return ["/"];
  }
}

/**
 * Crawl each active competitor, subject to their robots.txt.
 *
 * A competitor that disallows us is marked `robots_blocked` and skipped from
 * then on, so we ask once and respect the answer rather than re-testing it
 * every night.
 */
export async function crawlCompetitors(env: Env, runId: string): Promise<void> {
  const competitors = await env.DB.prepare(
    "SELECT id, label, origin FROM seo_competitors WHERE status = 'active' AND robots_blocked = 0",
  ).all<{ id: string; label: string; origin: string }>();

  const limit =
    Number.parseInt(await setting(env, "seo.competitor_max_pages", "30"), 10) ||
    COMPETITOR_PAGE_LIMIT;

  for (const competitor of competitors.results ?? []) {
    const rules = await fetchRobots(competitor.origin);
    if (rules.blocksEverything && rules.allow.length === 0) {
      await env.DB.prepare(
        "UPDATE seo_competitors SET robots_blocked = 1, last_error = ?, last_crawled_at = ?" +
          " WHERE id = ?",
      )
        .bind(
          `robots.txt disallows ${CRAWLER_USER_AGENT}; not crawling this site.`,
          nowIso(),
          competitor.id,
        )
        .run();
      console.log(`seo.competitor_blocked origin=${competitor.origin}`);
      continue;
    }

    const paths = (await competitorPaths(competitor.origin, limit)).filter((path) =>
      isAllowed(rules, path),
    );

    let crawled = 0;
    for (const path of paths.slice(0, limit)) {
      try {
        const response = await fetchWithTimeout(`${competitor.origin}${path}`);
        const snapshot = await extractPage(response, path, competitor.origin);
        await env.DB.prepare(
          "INSERT OR REPLACE INTO seo_competitor_pages (id, run_id, competitor_id, path," +
            " status_code, title, meta_description, h1, word_count, crawled_at)" +
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        )
          .bind(
            newId("seocp"),
            runId,
            competitor.id,
            path,
            snapshot.statusCode,
            snapshot.title || null,
            snapshot.metaDescription || null,
            snapshot.h1 || null,
            snapshot.wordCount,
            nowIso(),
          )
          .run();
        await recordChunks(
          env,
          runId,
          "competitor",
          competitor.id,
          snapshot.pageType,
          snapshot.headings,
        );
        crawled += 1;
      } catch (error) {
        console.error(
          `seo.competitor_page_failed origin=${competitor.origin} path=${path} ${error}`,
        );
      }
      await sleep(Math.max(COMPETITOR_DELAY_MS, rules.crawlDelaySeconds * 1000));
    }

    await env.DB.prepare(
      "UPDATE seo_competitors SET last_crawled_at = ?, last_error = NULL WHERE id = ?",
    )
      .bind(nowIso(), competitor.id)
      .run();
    console.log(`seo.competitor_crawled origin=${competitor.origin} pages=${crawled}`);
  }
}

/** Compare what we put in titles and headings against what they do. */
export async function computeKeywordGaps(env: Env, runId: string): Promise<void> {
  const ownRows = await env.DB.prepare(
    "SELECT title, meta_description FROM seo_pages WHERE run_id = ? AND status_code = 200",
  )
    .bind(runId)
    .all<{ title: string | null; meta_description: string | null }>();

  const own = extractTerms(
    (ownRows.results ?? []).map<PageText>((row) => ({
      title: row.title ?? "",
      heading: row.title ?? "",
      metaDescription: row.meta_description ?? "",
    })),
  );

  const competitorRows = await env.DB.prepare(
    "SELECT competitor_id, title, meta_description, h1 FROM seo_competitor_pages" +
      " WHERE run_id = ? AND status_code = 200",
  )
    .bind(runId)
    .all<{
      competitor_id: string;
      title: string | null;
      meta_description: string | null;
      h1: string | null;
    }>();

  const byCompetitor = new Map<string, PageText[]>();
  for (const row of competitorRows.results ?? []) {
    const pages = byCompetitor.get(row.competitor_id) ?? [];
    pages.push({
      title: row.title ?? "",
      heading: row.h1 ?? "",
      metaDescription: row.meta_description ?? "",
    });
    byCompetitor.set(row.competitor_id, pages);
  }
  if (byCompetitor.size === 0) return;

  const perCompetitor: Map<string, TermStats>[] = [...byCompetitor.values()].map((pages) =>
    extractTerms(pages),
  );
  const gaps = scoreGaps(own, perCompetitor).slice(0, 300);
  const observedAt = nowIso();

  for (let index = 0; index < gaps.length; index += 50) {
    const chunk = gaps.slice(index, index + 50);
    await env.DB.batch(
      chunk.map((gap) =>
        env.DB.prepare(
          "INSERT OR REPLACE INTO seo_keywords (id, run_id, term, term_words, own_pages," +
            " own_title_hits, own_heading_hits, competitor_pages, competitor_title_hits," +
            " competitor_heading_hits, competitor_count, gap_score, observed_at)" +
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ).bind(
          newId("seokw"),
          runId,
          gap.term,
          gap.termWords,
          gap.ownPages,
          gap.ownTitleHits,
          gap.ownHeadingHits,
          gap.competitorPages,
          gap.competitorTitleHits,
          gap.competitorHeadingHits,
          gap.competitorCount,
          gap.gapScore,
          observedAt,
        ),
      ),
    );
  }
  console.log(`seo.keywords_scored run=${runId} terms=${gaps.length}`);
}

// --- Content-structure gaps and proposals -----------------------------------

async function recordChunks(
  env: Env,
  runId: string,
  source: "own" | "competitor",
  competitorId: string | null,
  pageType: string,
  headings: string[],
): Promise<void> {
  if (headings.length === 0) return;
  const observedAt = nowIso();
  const seen = new Map<string, string>();
  for (const heading of headings) {
    const key = headingKey(heading);
    if (key && !seen.has(key)) seen.set(key, heading);
  }

  await env.DB.batch(
    [...seen].map(([key, heading]) =>
      env.DB.prepare(
        "INSERT INTO seo_content_chunks (id, run_id, competitor_id, source, page_type," +
          " heading, heading_key, occurrences, observed_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)" +
          " ON CONFLICT(run_id, source, competitor_id, page_type, heading_key)" +
          " DO UPDATE SET occurrences = occurrences + 1",
      ).bind(newId("seochk"), runId, competitorId, source, pageType, heading, key, observedAt),
    ),
  );
}

/** Load every CMS row the agent may propose changes to, with its path. */
async function loadEntities(env: Env): Promise<SeoEntity[]> {
  const entities: SeoEntity[] = [];

  const products = await env.DB.prepare(
    "SELECT p.id, p.name, p.slug, p.short_description, p.seo_title, p.seo_description," +
      " p.indexing_policy, f.name AS farm_name" +
      " FROM products p LEFT JOIN farms f ON f.id = p.farm_id WHERE p.status = 'published'",
  ).all<Record<string, string | null>>();
  for (const row of products.results ?? []) {
    entities.push({
      entityType: "product",
      entityId: String(row.id),
      label: String(row.name ?? ""),
      path: `/product/${row.slug}`,
      name: String(row.name ?? ""),
      description: String(row.short_description ?? ""),
      context: [row.farm_name ? `${row.farm_name}` : ""].filter(Boolean),
      seoTitle: String(row.seo_title ?? ""),
      seoDescription: String(row.seo_description ?? ""),
      seoKeywords: "",
      indexingPolicy: String(row.indexing_policy ?? "index"),
      supportedFields: SUPPORTED_FIELDS.product,
    });
  }

  for (const [table, type, pathPrefix] of [
    ["articles", "article", "/blog/"],
    ["recipes", "recipe", "/recipes/"],
  ] as const) {
    const rows = await env.DB.prepare(
      `SELECT id, title, slug, excerpt, seo_title, seo_description, seo_keywords, indexing_policy
         FROM ${table} WHERE status = 'published' AND archived_at IS NULL`,
    ).all<Record<string, string | null>>();
    for (const row of rows.results ?? []) {
      entities.push({
        entityType: type,
        entityId: String(row.id),
        label: String(row.title ?? ""),
        path: `${pathPrefix}${row.slug}`,
        name: String(row.title ?? ""),
        description: String(row.excerpt ?? ""),
        context: [],
        seoTitle: String(row.seo_title ?? ""),
        seoDescription: String(row.seo_description ?? ""),
        seoKeywords: String(row.seo_keywords ?? ""),
        indexingPolicy: String(row.indexing_policy ?? "index"),
        supportedFields: SUPPORTED_FIELDS[type],
      });
    }
  }

  const categories = await env.DB.prepare(
    "SELECT id, name, slug, short_description, seo_title, seo_description, indexing_policy" +
      " FROM categories WHERE status = 'published' AND visibility = 'public'",
  ).all<Record<string, string | null>>();
  for (const row of categories.results ?? []) {
    entities.push({
      entityType: "category",
      entityId: String(row.id),
      label: String(row.name ?? ""),
      path: `/category/${row.slug}`,
      name: String(row.name ?? ""),
      description: String(row.short_description ?? ""),
      context: [],
      seoTitle: String(row.seo_title ?? ""),
      seoDescription: String(row.seo_description ?? ""),
      seoKeywords: "",
      indexingPolicy: String(row.indexing_policy ?? "index"),
      supportedFields: SUPPORTED_FIELDS.category,
    });
  }

  return entities;
}

/**
 * Turn this run's gaps and findings into concrete, applyable field changes.
 *
 * Proposals from earlier runs that are still pending are superseded rather
 * than left to accumulate: an operator opening the dashboard should see this
 * crawl's view of the site, not a pile of suggestions built against a
 * catalogue that has since changed.
 */
export async function generateProposals(env: Env, runId: string): Promise<number> {
  const gapRows = await env.DB.prepare(
    "SELECT term, term_words, own_pages, own_title_hits, own_heading_hits, competitor_pages," +
      " competitor_title_hits, competitor_heading_hits, competitor_count, gap_score" +
      " FROM seo_keywords WHERE run_id = ? ORDER BY gap_score DESC LIMIT 200",
  )
    .bind(runId)
    .all<Record<string, number | string>>();

  const gaps: KeywordGap[] = (gapRows.results ?? []).map((row) => ({
    term: String(row.term),
    termWords: Number(row.term_words),
    ownPages: Number(row.own_pages),
    ownTitleHits: Number(row.own_title_hits),
    ownHeadingHits: Number(row.own_heading_hits),
    competitorPages: Number(row.competitor_pages),
    competitorTitleHits: Number(row.competitor_title_hits),
    competitorHeadingHits: Number(row.competitor_heading_hits),
    competitorCount: Number(row.competitor_count),
    gapScore: Number(row.gap_score),
  }));

  const findingRows = await env.DB.prepare(
    "SELECT path, rule FROM seo_findings WHERE status = 'open'",
  ).all<{ path: string; rule: string }>();
  const rulesByPath = new Map<string, Set<string>>();
  for (const row of findingRows.results ?? []) {
    const existing = rulesByPath.get(row.path) ?? new Set<string>();
    existing.add(row.rule);
    rulesByPath.set(row.path, existing);
  }

  const entities = await loadEntities(env);
  const proposals: Proposal[] = [];
  for (const entity of entities) {
    proposals.push(...proposalsFor(entity, gaps, rulesByPath.get(entity.path) ?? new Set()));
  }

  await env.DB.prepare(
    "UPDATE seo_proposals SET status = 'superseded' WHERE status = 'pending' AND run_id != ?",
  )
    .bind(runId)
    .run();

  const createdAt = nowIso();
  for (let index = 0; index < proposals.length; index += 40) {
    const chunk = proposals.slice(index, index + 40);
    await env.DB.batch(
      chunk.map((proposal) =>
        env.DB.prepare(
          "INSERT INTO seo_proposals (id, run_id, entity_type, entity_id, entity_label, path," +
            " field, current_value, proposed_value, rationale, source, source_ref, confidence," +
            " status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)" +
            " ON CONFLICT(run_id, entity_type, entity_id, field) DO UPDATE SET" +
            "  proposed_value = excluded.proposed_value, rationale = excluded.rationale," +
            "  confidence = excluded.confidence",
        ).bind(
          newId("seoprp"),
          runId,
          proposal.entityType,
          proposal.entityId,
          proposal.entityLabel,
          proposal.path,
          proposal.field,
          proposal.currentValue,
          proposal.proposedValue,
          proposal.rationale,
          proposal.source,
          proposal.sourceRef,
          proposal.confidence,
          createdAt,
        ),
      ),
    );
  }
  console.log(`seo.proposals_generated run=${runId} count=${proposals.length}`);
  return proposals.length;
}

export async function finaliseRun(env: Env, runId: string): Promise<void> {
  const snapshots = await loadSnapshots(env, runId);
  const sitemapPaths = new Set(snapshots.map((snapshot) => snapshot.path));

  const findings: Finding[] = [];
  for (const snapshot of snapshots) {
    findings.push(...evaluatePage(snapshot));
  }
  findings.push(...evaluateCrawl(snapshots, sitemapPaths));

  await persistFindings(env, runId, findings);
  await env.DB.prepare(
    "UPDATE seo_crawl_runs SET status = 'completed', finished_at = ? WHERE id = ?",
  )
    .bind(nowIso(), runId)
    .run();
}

export async function failRun(env: Env, runId: string, error: unknown): Promise<void> {
  await env.DB.prepare(
    "UPDATE seo_crawl_runs SET status = 'failed', finished_at = ?, error = ? WHERE id = ?",
  )
    .bind(nowIso(), String(error).slice(0, 1000), runId)
    .run();
}

/** One cron tick: claim or continue a run, crawl a batch, finish if done. */
export async function tick(env: Env): Promise<void> {
  if (!(await isEnabled(env))) return;

  const running = await env.DB.prepare(
    "SELECT id, pages_discovered FROM seo_crawl_runs WHERE status = 'running' ORDER BY started_at LIMIT 1",
  ).first<{ id: string; pages_discovered: number }>();

  let runId: string;
  if (running) {
    runId = running.id;
  } else {
    const claimed = await claimQueuedRun(env);
    if (!claimed) return;
    runId = claimed;
  }

  try {
    const discovered = await env.DB.prepare(
      "SELECT pages_discovered FROM seo_crawl_runs WHERE id = ?",
    )
      .bind(runId)
      .first<{ pages_discovered: number }>();
    if (!discovered || discovered.pages_discovered === 0) {
      const count = await startRun(env, runId);
      if (count === 0) {
        await failRun(env, runId, "Sitemap discovery returned no URLs.");
        return;
      }
    }

    const more = await advanceRun(env, runId);
    if (more) return;

    // Own site is done. Competitor research and keyword scoring run once, in
    // this final tick, before the run is closed. Both are wrapped so that a
    // competitor being slow or unreachable cannot fail an otherwise good audit
    // of our own site, which is the part that always matters.
    try {
      await crawlCompetitors(env, runId);
      await computeKeywordGaps(env, runId);
    } catch (error) {
      console.error(`seo.competitor_phase_failed run=${runId} error=${String(error)}`);
    }

    // Findings have to exist before proposals: a proposal cites the rule that
    // justifies it, so `finaliseRun` runs first and generation reads what it
    // wrote.
    await finaliseRun(env, runId);
    try {
      await generateProposals(env, runId);
    } catch (error) {
      console.error(`seo.proposal_phase_failed run=${runId} error=${String(error)}`);
    }
    return;
  } catch (error) {
    await failRun(env, runId, error);
    throw error;
  }
}

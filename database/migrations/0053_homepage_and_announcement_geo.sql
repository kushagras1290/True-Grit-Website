-- 0053_homepage_and_announcement_geo: per-country overrides for the
-- announcement banner and for which homepage sections show.
--
-- ANNOUNCEMENT BANNER
-- `country` mirrors `theme_settings.scope`'s own sentinel: `'global'` for the
-- site-wide banner, an ISO-3166 alpha-2 code (`'IN'`, `'US'`) for a
-- country-specific one. A sentinel string rather than a nullable column with
-- `UNIQUE(country)` on purpose -- SQL treats every NULL as distinct from every
-- other NULL, so a NULL-means-global column could quietly accumulate more
-- than one "global" row with nothing to stop it. `'global'` is an ordinary
-- value the unique index compares normally.
--
-- Resolution (`services/announcements.resolve_announcement`): the active row
-- for the visitor's country if one exists, else the active global row, else
-- no banner. A country row is a full replacement, not a patch -- a banner
-- either is or is not shown, so there is nothing sensible to merge key by key
-- the way theme colours are.
--
-- HOMEPAGE SECTION OVERRIDES
-- The homepage's own `enabled` flag on each block (`page_versions.content_json`)
-- is the global default. `homepage_country_overrides` is a second, narrower
-- opinion: "for visitors in this country, force this one section on or off",
-- without touching the block's stored default or its content. Reordering is
-- deliberately out of scope -- a section that moves to a different position
-- per visitor is a much larger claim on the page's layout than one that is
-- simply present or absent, and the latter covers the real cases this exists
-- for (a festival section shown only in its home market, a cold-weather
-- effect hidden in tropical ones).
--
-- `block_id` is not a foreign key: blocks live inside a JSON document
-- (`page_versions.content_json`), not their own table, so there is nothing in
-- SQL for it to reference. An override for a block that has since been
-- deleted or had its id changed is simply inert -- it matches nothing and
-- affects nothing, which is the correct failure mode for a stale row.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

ALTER TABLE announcements ADD COLUMN country TEXT NOT NULL DEFAULT 'global'
  CHECK (
    country = 'global'
    OR (
      length(country) = 2
      AND substr(country, 1, 2) = upper(substr(country, 1, 2))
    )
  );

-- One row per scope: a second PUT for the same country replaces it (see
-- `save_announcement`'s upsert), so the table can never grow a duplicate
-- "global" or duplicate "IN" the earlier single-row-by-recency logic could
-- otherwise leave behind.
CREATE UNIQUE INDEX IF NOT EXISTS idx_announcements_country ON announcements(country);

CREATE TABLE IF NOT EXISTS homepage_country_overrides (
  country    TEXT NOT NULL
             CHECK (length(country) = 2 AND substr(country, 1, 2) = upper(substr(country, 1, 2))),
  block_id   TEXT NOT NULL,
  enabled    INTEGER NOT NULL CHECK (enabled IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
  PRIMARY KEY (country, block_id)
);

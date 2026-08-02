-- 0067_i18n_page_translations: per-locale content for CMS pages (the
-- homepage and static pages both use `pages`/`page_versions`).
--
-- WHY A PARALLEL content_json PER LOCALE, NOT PER-FIELD TRANSLATION ROWS
-- A page's `content_json` is an array of CMS blocks (ADR-005), and each
-- block type has a different shape (hero has `slides`, faq has `items`,
-- rich_text has `paragraphs`...). Modelling "the Hindi version of this page"
-- as a second, complete content_json blob -- rather than one row per
-- translatable string -- means the SAME block-schema validation
-- (`domain.blocks.validate_blocks`) that already guards the English content
-- guards every locale too, with no second schema to maintain.
--
-- WHY THIS IS A SEPARATE TABLE, NOT A COLUMN ON `page_versions`
-- `page_versions` is an append-only history (draft -> approved -> published);
-- a translation is not a version of the page, it is a parallel rendering of
-- whatever the CURRENT published version says, per locale. Keying on
-- `page_id` (not `page_version_id`) means a translation survives the English
-- content's next edit without needing its own version bump -- it simply
-- becomes stale until an editor revisits it, the same "falls back to
-- English, never breaks" property `auto_translated` below exists to surface.
--
-- WHY `auto_translated`
-- Populated by Cloudflare Workers AI's `@cf/meta/m2m100-1.2b` model (see
-- `platform.translation`), a real but imperfect translator -- this flag is
-- what lets the admin editor show "machine-translated, not yet reviewed"
-- honestly rather than presenting a first-draft as a finished one. Cleared
-- the moment an editor saves their own edit over it.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS page_content_translations (
  page_id TEXT NOT NULL,
  locale TEXT NOT NULL,
  content_json TEXT NOT NULL,
  auto_translated INTEGER NOT NULL DEFAULT 0 CHECK (auto_translated IN (0, 1)),
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  PRIMARY KEY (page_id, locale),
  FOREIGN KEY (page_id) REFERENCES pages(id) ON DELETE CASCADE,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

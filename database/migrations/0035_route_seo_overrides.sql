-- 0035_route_seo_overrides: admin-editable SEO (title, description, keywords,
-- indexing) for storefront routes that are not backed by a single-segment
-- CMS page record. `pages.slug` only ever maps to `/{slug}` (enforced by
-- `domain.slugs.validate_slug`, which rejects `/`), so nested utility routes
-- like `/blog/submit` and `/recipes/submit` cannot use that mechanism. A
-- route with no row here keeps using its own hardcoded fallback metadata,
-- exactly like a CMS page falls back to `fallbackSeo` when unpublished.
PRAGMA foreign_keys = ON;

CREATE TABLE route_seo_overrides (
  path TEXT PRIMARY KEY,
  seo_title TEXT,
  seo_description TEXT,
  seo_keywords TEXT,
  indexing_policy TEXT NOT NULL DEFAULT 'index' CHECK (indexing_policy IN ('index', 'noindex')),
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

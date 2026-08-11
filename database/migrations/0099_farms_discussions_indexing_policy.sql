-- 0099_farms_discussions_indexing_policy: bring farms and discussions up to
-- the same indexing_policy control every other public content type already
-- has (products/categories/pages, migration 0002/0003; articles/recipes,
-- migration 0024), so an owner can pull a specific farm profile or community
-- thread out of the sitemap/search index without deleting it.
PRAGMA foreign_keys = ON;

ALTER TABLE farms ADD COLUMN indexing_policy TEXT NOT NULL DEFAULT 'index'
  CHECK (indexing_policy IN ('index', 'noindex'));

ALTER TABLE discussions ADD COLUMN indexing_policy TEXT NOT NULL DEFAULT 'index'
  CHECK (indexing_policy IN ('index', 'noindex'));

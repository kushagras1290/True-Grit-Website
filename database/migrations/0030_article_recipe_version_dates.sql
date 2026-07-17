-- 0030_article_recipe_version_dates: add workflow timestamps to article and recipe versions
-- This allows the universal _publish_content_version in publishing.py to track
-- approval and publication metadata without SQL errors.

PRAGMA foreign_keys = ON;

ALTER TABLE article_versions ADD COLUMN approved_at TEXT;
ALTER TABLE article_versions ADD COLUMN approved_by TEXT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE article_versions ADD COLUMN published_at TEXT;

ALTER TABLE recipe_versions ADD COLUMN approved_at TEXT;
ALTER TABLE recipe_versions ADD COLUMN approved_by TEXT REFERENCES users(id) ON DELETE SET NULL;
ALTER TABLE recipe_versions ADD COLUMN published_at TEXT;

-- 0024_articles_recipes_seo_parity: bring articles and recipes up to the same
-- SEO control surface pages already have (seo_keywords, canonical_url,
-- indexing_policy), and give recipes an explicit chef byline column that
-- mirrors articles.author_user_id so recipe authorship can be scoped the
-- same way article authorship is.
PRAGMA foreign_keys = ON;

ALTER TABLE articles ADD COLUMN seo_keywords TEXT;
ALTER TABLE articles ADD COLUMN canonical_url TEXT;
ALTER TABLE articles ADD COLUMN indexing_policy TEXT NOT NULL DEFAULT 'index'
  CHECK (indexing_policy IN ('index', 'noindex'));

ALTER TABLE recipes ADD COLUMN seo_keywords TEXT;
ALTER TABLE recipes ADD COLUMN canonical_url TEXT;
ALTER TABLE recipes ADD COLUMN indexing_policy TEXT NOT NULL DEFAULT 'index'
  CHECK (indexing_policy IN ('index', 'noindex'));
ALTER TABLE recipes ADD COLUMN chef_user_id TEXT REFERENCES users(id) ON DELETE SET NULL;

-- 0083_articles_recipes_archive: adds archived_at to articles and recipes so
-- "delete" for blog posts and recipes becomes a soft-archive -- the same
-- pattern products and categories already use (status = 'archived',
-- archived_at stamped, row kept, filtered out of the normal admin list, and
-- recoverable from /archive) -- instead of the previous state where these
-- two content types had no delete capability at all. The 'archived' status
-- value already existed in each table's CHECK constraint (0003_cms.sql) but
-- nothing ever set it.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, plain
-- ALTER TABLE ADD COLUMN, matching every other ALTER TABLE ADD COLUMN
-- migration in this codebase.
ALTER TABLE articles ADD COLUMN archived_at TEXT;
ALTER TABLE recipes ADD COLUMN archived_at TEXT;

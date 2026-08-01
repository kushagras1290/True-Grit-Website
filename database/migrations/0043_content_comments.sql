-- 0043_content_comments: reader comments on published blog posts and recipes.
--
-- WHY A SEPARATE TABLE FROM discussion_comments
-- `discussion_comments` is keyed by a NOT NULL `discussion_id` foreign key.
-- Widening it to also point at an article or a recipe would mean three
-- nullable parent columns and a CHECK asserting exactly one is set -- a shape
-- SQLite cannot enforce referentially, and one where a bug silently orphans
-- rows. A dedicated table keeps each parent relationship a real foreign key,
-- so deleting an article takes its comments with it and nothing else.
--
-- The polymorphic pair (`content_type`, article_id | recipe_id) is therefore
-- modelled as two nullable, individually-constrained foreign keys plus a CHECK
-- that binds the discriminator to whichever one is populated. That is the only
-- arrangement where the database itself refuses a comment attached to both, or
-- to neither.
--
-- MODERATION mirrors discussions exactly (0034): 'visible' | 'hidden' |
-- 'removed', with the moderator, timestamp and reason recorded on the row.
-- Public reads filter on 'visible', so hiding is instant and reversible while
-- keeping the evidence, and permanent deletion stays a separate, deliberate
-- act. Reusing `discussions.moderate` rather than minting a parallel
-- permission is intentional: the people who police one comment stream are the
-- people who police the other, and a second permission would only create a
-- role that can silence half the site.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, every insert idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE content_comments (
  id TEXT PRIMARY KEY,
  content_type TEXT NOT NULL CHECK (content_type IN ('article', 'recipe')),
  -- Exactly one of these is set, pinned to content_type by the CHECK below.
  article_id TEXT,
  recipe_id TEXT,
  author_user_id TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'visible' CHECK (status IN ('visible', 'hidden', 'removed')),
  moderated_by TEXT,
  moderated_at TEXT,
  moderation_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (article_id) REFERENCES articles(id) ON DELETE CASCADE,
  FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE,
  FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL,
  CHECK (
    (content_type = 'article' AND article_id IS NOT NULL AND recipe_id IS NULL)
    OR (content_type = 'recipe' AND recipe_id IS NOT NULL AND article_id IS NULL)
  )
);

-- The two hot reads: a post's comment thread, oldest first (how a conversation
-- is read), and a recipe's. Status leads both because every public query
-- filters on it.
CREATE INDEX idx_content_comments_article
  ON content_comments(article_id, status, created_at);

CREATE INDEX idx_content_comments_recipe
  ON content_comments(recipe_id, status, created_at);

-- The moderation queue: newest first across both content types.
CREATE INDEX idx_content_comments_status_time
  ON content_comments(status, created_at DESC);

CREATE INDEX idx_content_comments_author
  ON content_comments(author_user_id, created_at DESC);

-- Whether readers may comment at all is an owner switch, not a deploy. Stored
-- as text like every other app_settings value; the service parses it.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('content_comments.enabled', 'true', '2026-08-01T00:00:00Z');

-- 0034_community_discussions: open discussions among signed-in customers.
-- Anyone signed in may comment; starting a new discussion additionally
-- requires an account at least `discussions.min_account_age_months` old
-- (app_settings, admin-editable, default 6) so the first voices shaping the
-- community are established customers rather than throwaway accounts.
-- Staff with discussions.moderate can hide, archive, restore or delete any
-- thread or comment from a dedicated admin section.
PRAGMA foreign_keys = ON;

-- Minimal key/value store for admin-editable settings that don't belong to
-- any single entity (unlike site-control, which lives on the homepage CMS
-- page). Values are always stored as text; callers parse what they expect.
CREATE TABLE app_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

INSERT OR IGNORE INTO app_settings (key, value, updated_at)
VALUES ('discussions.min_account_age_months', '6', '2026-07-18T00:00:00Z');

CREATE TABLE discussions (
  id TEXT PRIMARY KEY,
  author_user_id TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'visible' CHECK (
    status IN ('visible', 'hidden', 'archived', 'removed')
  ),
  comment_count INTEGER NOT NULL DEFAULT 0,
  last_activity_at TEXT NOT NULL,
  moderated_by TEXT,
  moderated_at TEXT,
  moderation_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_discussions_status_activity
  ON discussions(status, last_activity_at DESC);

CREATE INDEX idx_discussions_author
  ON discussions(author_user_id, created_at DESC);

CREATE TABLE discussion_comments (
  id TEXT PRIMARY KEY,
  discussion_id TEXT NOT NULL,
  author_user_id TEXT NOT NULL,
  body TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'visible' CHECK (status IN ('visible', 'hidden', 'removed')),
  moderated_by TEXT,
  moderated_at TEXT,
  moderation_reason TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (discussion_id) REFERENCES discussions(id) ON DELETE CASCADE,
  FOREIGN KEY (author_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_discussion_comments_discussion
  ON discussion_comments(discussion_id, created_at);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_discussions_view', 'discussions.view', 'View community discussions and comments'),
  (
    'prm_discussions_moderate',
    'discussions.moderate',
    'Edit, hide, archive, restore or delete discussions and comments'
  ),
  (
    'prm_settings_community',
    'settings.community',
    'Change community settings, e.g. the minimum account age to start a discussion'
  );

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('discussions.view', 'discussions.moderate', 'settings.community')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('discussions.view', 'discussions.moderate', 'settings.community')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

-- Header nav: add a Community link right after the existing Blog item, in
-- whatever menu that item lives in. Guarded so a re-run (or a database that
-- never seeded the Blog item) never duplicates or errors.
INSERT INTO navigation_items
  (id, menu_id, parent_id, label, destination_type, destination_reference, sort_order, visible)
SELECT
  'nav_community_header',
  blog_item.menu_id,
  NULL,
  'Community',
  'internal_path',
  '/community',
  blog_item.sort_order + 1,
  1
FROM navigation_items blog_item
WHERE blog_item.destination_type = 'internal_path'
  AND blog_item.destination_reference = '/blog'
  AND NOT EXISTS (
    SELECT 1 FROM navigation_items WHERE destination_reference = '/community'
  );

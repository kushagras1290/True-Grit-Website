-- 0025_content_roles_and_permissions: permission keys for the new blog
-- (articles), recipe, returns, media-delete and owner-reporting surfaces,
-- plus two new authoring roles: 'blogger' (owns articles, cannot approve or
-- publish) and 'chef' (owns recipes, cannot approve or publish). Approval and
-- publishing stay with Manager/Publisher/Super Administrator, matching the
-- existing draft -> in_review -> approved -> published workflow_state machine
-- already used by pages/articles/recipes.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_articles_view', 'articles.view', 'View articles'),
  ('prm_articles_create', 'articles.create', 'Create articles'),
  ('prm_articles_edit', 'articles.edit', 'Edit articles'),
  ('prm_articles_approve', 'articles.approve', 'Approve articles'),
  ('prm_articles_publish', 'articles.publish', 'Publish articles'),
  ('prm_recipes_view', 'recipes.view', 'View recipes'),
  ('prm_recipes_create', 'recipes.create', 'Create recipes'),
  ('prm_recipes_edit', 'recipes.edit', 'Edit recipes'),
  ('prm_recipes_approve', 'recipes.approve', 'Approve recipes'),
  ('prm_recipes_publish', 'recipes.publish', 'Publish recipes'),
  ('prm_returns_view', 'returns.view', 'View return requests'),
  ('prm_returns_manage', 'returns.manage', 'Approve, reject and resolve return requests'),
  ('prm_media_delete', 'media.delete', 'Permanently delete media assets'),
  ('prm_reports_query', 'reports.query', 'Run curated data-export report queries');

INSERT OR IGNORE INTO roles (id, key, name, description, is_system, created_at) VALUES
  (
    'rol_blogger',
    'blogger',
    'Blogger',
    'Write and submit blog articles for review; cannot publish',
    1,
    '2026-07-17T00:00:00Z'
  ),
  (
    'rol_chef',
    'chef',
    'Chef',
    'Write and submit recipes for review; cannot publish',
    1,
    '2026-07-17T00:00:00Z'
  );

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_blogger', id FROM permissions
WHERE key IN ('articles.view', 'articles.create', 'articles.edit', 'media.view', 'media.upload');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_chef', id FROM permissions
WHERE key IN ('recipes.view', 'recipes.create', 'recipes.edit', 'media.view', 'media.upload');

-- Manager already approves/publishes pages and categories; extend it to
-- articles, recipes and returns so it can review blogger/chef submissions.
-- 'rol_manager' is guaranteed to exist (created in 0013_users_roles_contact.sql),
-- but every other role referenced below is only ever created by the dev seed
-- (database/seeds/development.sql), which never runs against a deployed
-- database — so each of those grants is guarded with an EXISTS check, the
-- same defensive pattern 0013 already uses for 'rol_farm_owner'. A fresh dev
-- database still gets every grant because the seed creates those roles
-- before this migration would ever need to re-run.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN (
  'articles.view', 'articles.create', 'articles.edit', 'articles.approve', 'articles.publish',
  'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.approve', 'recipes.publish',
  'returns.view', 'returns.manage', 'media.delete'
);

-- Publisher's whole job is approve + publish, same shape as its pages grant.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_publisher', id FROM permissions
WHERE key IN ('articles.approve', 'articles.publish', 'recipes.approve', 'recipes.publish')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_publisher');

-- Content editor drafts and edits content broadly, same shape as its pages grant.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_content_editor', id FROM permissions
WHERE key IN ('articles.view', 'articles.create', 'articles.edit', 'recipes.view', 'recipes.create', 'recipes.edit')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_content_editor');

-- Order manager triages post-delivery issues alongside orders.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_order_manager', id FROM permissions
WHERE key IN ('returns.view', 'returns.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_order_manager');

-- Super administrator: the dev seed grants every existing permission row to
-- rol_super_admin with a blanket "SELECT * FROM permissions", but that seed
-- only runs once for a fresh dev database. Environments that already have
-- data need these new rows granted explicitly here.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN (
  'articles.view', 'articles.create', 'articles.edit', 'articles.approve', 'articles.publish',
  'recipes.view', 'recipes.create', 'recipes.edit', 'recipes.approve', 'recipes.publish',
  'returns.view', 'returns.manage', 'media.delete', 'reports.query'
)
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

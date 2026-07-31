-- 0041_role_permission_baseline: give every seeded role the permissions its
-- job actually needs.
--
-- Grants accumulated one feature at a time (0013, 0025, 0032, 0033, 0034), and
-- each migration only granted what that feature introduced. The result had real
-- holes:
--
--   * Administrator held nothing but submissions + discussions — the broadest
--     non-owner role could not open Products, Orders or Users.
--   * Publisher could approve and publish articles/recipes but had no
--     articles.view / recipes.view, so the lists it works from were invisible.
--   * Manager could not see Users, Farms, Contact Attempts (users.view), Site
--     Control (settings.view), Submissions or Discussions.
--   * Accounts owns refunds, but "Payments & Refunds" is gated on audit.view,
--     so the role built for it could not reach the page.
--   * Content Editor could draft articles/recipes with no media.edit, and
--     Product/Inventory/Order managers each missed an adjacent read they need
--     to do their own job (stock levels, order lines, category assignment).
--
-- This migration closes those holes in one place. It only ever ADDS grants
-- (INSERT OR IGNORE) — no role loses anything, so re-running is a no-op and no
-- signed-in user is downgraded mid-session.
--
-- Every grant is guarded with EXISTS because, apart from rol_manager (0013),
-- these roles are created by database/seeds/development.sql, which never runs
-- against a deployed database. On a fresh local database the migrations run
-- BEFORE the seed, so these statements no-op there and the seed carries the
-- same grants itself — the two must be kept in step.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

-- Administrator: everything except the super-admin-only diagnostics, which are
-- gated on the `super_admin` role itself rather than on any permission row.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

-- Manager: runs the shop day to day. Adds the reads its console pages need
-- (users.view backs Farms and Contact Attempts) plus the community queues it is
-- expected to clear. settings.* is deliberately withheld: Site Control now also
-- holds the sign-in and payment kill-switches, which stay with the owner.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN (
  'users.view',
  'submissions.view',
  'submissions.review',
  'discussions.view',
  'discussions.moderate',
  'categories.approve',
  'products.approve',
  'pages.approve',
  'media.archive'
);

-- Publisher: approves and publishes. Without the matching view grants it was
-- approving content it could not list.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_publisher', id FROM permissions
WHERE key IN (
  'articles.view',
  'recipes.view',
  'media.view',
  'submissions.view',
  'submissions.review'
)
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_publisher');

-- Content Editor: drafts and edits. Editing media metadata (alt text, captions)
-- is part of writing a page; approving and publishing deliberately are not.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_content_editor', id FROM permissions
WHERE key IN ('media.edit', 'media.archive', 'submissions.view')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_content_editor');

-- Blogger / Chef: authoring roles. Both already own their content type; the
-- community threads are the other half of the conversation they moderate
-- through Submissions, so give them read access to it.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_blogger', id FROM permissions
WHERE key = 'discussions.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_blogger');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_chef', id FROM permissions
WHERE key = 'discussions.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_chef');

-- Product Manager: owns the catalogue. Publishing and archiving a product is
-- the job; inventory.view tells it whether a product can be sold at all, and
-- categories.edit lets it place the product it just created.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_product_manager', id FROM permissions
WHERE key IN (
  'products.publish',
  'products.archive',
  'categories.edit',
  'inventory.view',
  'media.edit'
)
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_product_manager');

-- Inventory Manager: adjusts stock. Orders are what consume it, so seeing them
-- is part of knowing why a level moved.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_inventory_manager', id FROM permissions
WHERE key IN ('orders.view', 'categories.view')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_inventory_manager');

-- Order Manager: fulfilment. Already triages returns (0025); add the stock and
-- product reads a fulfilment decision depends on.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_order_manager', id FROM permissions
WHERE key IN ('products.view', 'inventory.view')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_order_manager');

-- Accounts: payments and refunds only. audit.view is what the "Payments &
-- Refunds" console is gated on, and returns are where most refunds originate —
-- without both, the role could not reach the work it exists to do. Catalogue,
-- users and settings stay out of reach, as its description promises.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_accounts', id FROM permissions
WHERE key IN ('audit.view', 'returns.view', 'customers.view')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_accounts');

-- Inventory (monitoring role): read-only sibling of Inventory Manager.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_inventory', id FROM permissions
WHERE key = 'categories.view';

-- Farm Owner: a sub-admin scoped to one farm by `farm_members`; the scoping is
-- enforced in the API, not by permissions. Seeing its own orders and returns is
-- what makes the scope useful.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_farm_owner', id FROM permissions
WHERE key IN ('orders.view', 'categories.view')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_farm_owner');

-- Super administrator holds every permission by definition. The dev seed does
-- this with a blanket SELECT, which only runs for a fresh local database; a
-- deployed database needs it stated here.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

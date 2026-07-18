-- 0032_accounts_role_and_refunds: an 'accounts' role scoped to payments and
-- refunds (orders.view/cancel/refund only -- no catalogue, users or settings
-- access), plus orders.refund itself as a real migration row. orders.refund
-- previously only existed via the dev seed (database/seeds/development.sql),
-- which never runs against a deployed database that already has data -- any
-- such environment would have no way to grant it at all.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_orders_refund', 'orders.refund', 'Refund orders');

INSERT OR IGNORE INTO roles (id, key, name, description, is_system, created_at) VALUES
  (
    'rol_accounts',
    'accounts',
    'Accounts',
    'Handle order payments and refunds; cannot touch catalogue, users or settings',
    1,
    '2026-07-18T00:00:00Z'
  );

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_accounts', id FROM permissions
WHERE key IN ('orders.view', 'orders.cancel', 'orders.refund');

-- Super administrator: the dev seed grants every permission row to
-- rol_super_admin with a blanket "SELECT * FROM permissions", but that seed
-- only runs once for a fresh dev database. A deployed database that already
-- has data needs orders.refund granted explicitly here (matching the same
-- pattern 0025 already used for its own new permissions).
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'orders.refund'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

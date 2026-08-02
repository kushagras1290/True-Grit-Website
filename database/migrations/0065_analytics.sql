-- 0065_analytics: owner-facing revenue/order analytics dashboard.
--
-- No new tables -- every metric is computed live from `orders`/`order_items`,
-- the same "real data, never a fabricated number" standard `services.catalogue`
-- bestsellers and `services.subscriptions` renewals already hold. This
-- migration only grants the permission the dashboard's routes are gated on.
--
-- WHY THIS IS SEPARATE FROM "OWNER REPORTS" (`reports.query`, migration 0041)
-- Reports is a curated library of named, parameterized, row-returning
-- queries -- a data-export tool. Analytics is a visual dashboard (KPI cards,
-- a revenue trend, a top-products table) meant to be glanced at, not
-- exported. Different audience too: Reports is gated to the owner alone;
-- analytics.view is granted to Admin and Manager as well, the same
-- commercial-visibility tier bundles/subscriptions already use, since
-- "how is the store doing" is not an owner-only question.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_analytics_view', 'analytics.view', 'View the revenue and orders analytics dashboard');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'analytics.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key = 'analytics.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key = 'analytics.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

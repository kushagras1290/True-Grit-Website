-- 0087_pickup_points: local pickup locations as an alternative to home delivery.
--
-- A customer selects a pickup point at checkout instead of entering a delivery
-- address; the delivery fee is waived (pickup is free). The admin manages the
-- list of available points (name, address, operating hours).
--
-- Pickup reuses the existing fulfilment states: packed means ready for pickup,
-- fulfilled means collected. This avoids adding invalid delivery_status values.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE pickup_points (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  address_json TEXT NOT NULL DEFAULT '{}',
  hours TEXT,
  phone TEXT,
  latitude REAL,
  longitude REAL,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_pickup_points_status ON pickup_points(status);

-- Extend orders with delivery method tracking.
ALTER TABLE orders ADD COLUMN delivery_method TEXT NOT NULL DEFAULT 'delivery'
  CHECK (delivery_method IN ('delivery', 'pickup'));
ALTER TABLE orders ADD COLUMN pickup_point_id TEXT REFERENCES pickup_points(id) ON DELETE SET NULL;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.pickup.enabled', '0', '2026-08-08T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_pickup_view', 'pickup_points.view', 'View pickup points'),
  ('prm_pickup_manage', 'pickup_points.manage', 'Create, edit and deactivate pickup points');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('pickup_points.view', 'pickup_points.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('pickup_points.view', 'pickup_points.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('pickup_points.view', 'pickup_points.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

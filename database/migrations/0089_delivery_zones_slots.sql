-- 0089_delivery_zones_slots: real delivery slot selection and serviceable-zone
-- enforcement at checkout.
--
-- When enabled, checkout validates the customer's postal code against defined
-- zones. Each zone can override the global delivery fee, set a lead time, and
-- define available delivery slots (day + time window). Unserviceable postal
-- codes are rejected at checkout with a clear error.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE delivery_zones (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  -- JSON array of postal code patterns, e.g. ["560*", "110001", "400*"]
  -- The service layer matches customer postal codes against these patterns.
  postal_codes_json TEXT NOT NULL DEFAULT '[]',
  fee_override_minor INTEGER,
  free_threshold_override_minor INTEGER,
  lead_time_hours INTEGER NOT NULL DEFAULT 24,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  sort_order INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_delivery_zones_status ON delivery_zones(status);

CREATE TABLE delivery_slots (
  id TEXT PRIMARY KEY,
  zone_id TEXT NOT NULL,
  day_of_week INTEGER NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  start_time TEXT NOT NULL,
  end_time TEXT NOT NULL,
  max_orders INTEGER NOT NULL DEFAULT 20,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  FOREIGN KEY (zone_id) REFERENCES delivery_zones(id) ON DELETE CASCADE
);

CREATE INDEX idx_delivery_slots_zone ON delivery_slots(zone_id);

CREATE TABLE delivery_slot_bookings (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  slot_id TEXT NOT NULL,
  delivery_date TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (slot_id) REFERENCES delivery_slots(id) ON DELETE RESTRICT
);

CREATE INDEX idx_slot_bookings_order ON delivery_slot_bookings(order_id);
CREATE INDEX idx_slot_bookings_slot_date ON delivery_slot_bookings(slot_id, delivery_date);

CREATE TRIGGER trg_delivery_slot_capacity_before_insert
BEFORE INSERT ON delivery_slot_bookings
WHEN (
  SELECT COUNT(*) FROM delivery_slot_bookings
  WHERE slot_id = NEW.slot_id AND delivery_date = NEW.delivery_date
) >= (
  SELECT max_orders FROM delivery_slots WHERE id = NEW.slot_id
)
BEGIN
  SELECT RAISE(ABORT, 'delivery slot capacity exceeded');
END;

-- Extend orders with delivery zone/slot tracking.
ALTER TABLE orders ADD COLUMN delivery_zone_id TEXT REFERENCES delivery_zones(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN delivery_slot_id TEXT REFERENCES delivery_slots(id) ON DELETE SET NULL;
ALTER TABLE orders ADD COLUMN delivery_date TEXT;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.delivery_zones.enabled', '0', '2026-08-08T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_delivery_zones_view', 'delivery_zones.view', 'View delivery zones and slots'),
  ('prm_delivery_zones_manage', 'delivery_zones.manage', 'Create, edit and manage delivery zones and slots');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('delivery_zones.view', 'delivery_zones.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('delivery_zones.view', 'delivery_zones.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('delivery_zones.view', 'delivery_zones.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

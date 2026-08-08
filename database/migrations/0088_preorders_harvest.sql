-- 0088_preorders_harvest: seasonal pre-ordering backed by a harvest calendar.
--
-- Customers reserve a not-yet-harvested product ahead of its expected harvest
-- window. Charged at order time, fulfilled when the harvest actually comes in.
-- Pre-orders reserve against a *future* harvest, not current on_hand stock --
-- the service layer handles this distinction, skipping the normal
-- inventory_levels reservation path.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE harvest_windows (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  title TEXT,
  expected_start TEXT NOT NULL,
  expected_end TEXT NOT NULL,
  actual_start TEXT,
  actual_end TEXT,
  max_preorders INTEGER,
  status TEXT NOT NULL DEFAULT 'upcoming' CHECK (
    status IN ('upcoming', 'active', 'harvesting', 'completed', 'cancelled')
  ),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE INDEX idx_harvest_windows_product ON harvest_windows(product_id);
CREATE INDEX idx_harvest_windows_status ON harvest_windows(status);
CREATE INDEX idx_harvest_windows_dates ON harvest_windows(expected_start, expected_end);

CREATE TABLE preorders (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  harvest_window_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  status TEXT NOT NULL DEFAULT 'reserved' CHECK (
    status IN ('reserved', 'ready', 'fulfilled', 'cancelled')
  ),
  created_at TEXT NOT NULL,
  fulfilled_at TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (harvest_window_id) REFERENCES harvest_windows(id) ON DELETE RESTRICT,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
);

CREATE INDEX idx_preorders_order ON preorders(order_id);
CREATE INDEX idx_preorders_harvest ON preorders(harvest_window_id);
CREATE INDEX idx_preorders_status ON preorders(status);

CREATE TRIGGER trg_preorders_capacity_before_insert
BEFORE INSERT ON preorders
WHEN (
  SELECT max_preorders FROM harvest_windows WHERE id = NEW.harvest_window_id
) IS NOT NULL
AND (
  SELECT COALESCE(SUM(quantity), 0) FROM preorders
  WHERE harvest_window_id = NEW.harvest_window_id
    AND status IN ('reserved', 'ready')
) + NEW.quantity > (
  SELECT max_preorders FROM harvest_windows WHERE id = NEW.harvest_window_id
)
BEGIN
  SELECT RAISE(ABORT, 'harvest preorder capacity exceeded');
END;

-- Extend orders with order type tracking.
ALTER TABLE orders ADD COLUMN order_type TEXT NOT NULL DEFAULT 'standard'
  CHECK (order_type IN ('standard', 'preorder'));

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.preorders.enabled', '0', '2026-08-08T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_preorders_view', 'preorders.view', 'View harvest calendar and preorders'),
  ('prm_preorders_manage', 'preorders.manage', 'Manage harvest windows and fulfill preorders');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('preorders.view', 'preorders.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('preorders.view', 'preorders.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('preorders.view', 'preorders.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

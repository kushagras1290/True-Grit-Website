-- 0004_inventory: locations, levels, reservations, movements
PRAGMA foreign_keys = ON;

CREATE TABLE inventory_locations (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  location_type TEXT NOT NULL CHECK (location_type IN ('warehouse', 'farm', 'store', 'virtual')),
  timezone TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE inventory_levels (
  variant_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  on_hand INTEGER NOT NULL DEFAULT 0 CHECK (on_hand >= 0),
  reserved INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
  reorder_threshold INTEGER NOT NULL DEFAULT 0 CHECK (reorder_threshold >= 0),
  version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
  updated_at TEXT NOT NULL,
  PRIMARY KEY (variant_id, location_id),
  CHECK (reserved <= on_hand),
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
  FOREIGN KEY (location_id) REFERENCES inventory_locations(id) ON DELETE RESTRICT
);

CREATE INDEX idx_inventory_low_stock
  ON inventory_levels(location_id, on_hand, reserved, reorder_threshold);

CREATE TABLE inventory_reservations (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  reference_type TEXT NOT NULL CHECK (reference_type IN ('order', 'checkout', 'manual')),
  reference_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('held', 'consumed', 'released', 'expired')),
  expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE RESTRICT,
  FOREIGN KEY (location_id) REFERENCES inventory_locations(id) ON DELETE RESTRICT
);

CREATE INDEX idx_reservations_reference
  ON inventory_reservations(reference_type, reference_id);

CREATE INDEX idx_reservations_active
  ON inventory_reservations(status, expires_at);

CREATE TABLE inventory_movements (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL,
  location_id TEXT NOT NULL,
  movement_type TEXT NOT NULL CHECK (
    movement_type IN (
      'receipt', 'sale', 'reservation', 'reservation_release',
      'shipment', 'return', 'manual_adjustment', 'write_off', 'correction'
    )
  ),
  quantity_delta INTEGER NOT NULL,
  reference_type TEXT,
  reference_id TEXT,
  reason_code TEXT,
  note TEXT,
  actor_id TEXT,
  created_at TEXT NOT NULL,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE RESTRICT,
  FOREIGN KEY (location_id) REFERENCES inventory_locations(id) ON DELETE RESTRICT,
  FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_inventory_movements_variant_time
  ON inventory_movements(variant_id, created_at DESC);

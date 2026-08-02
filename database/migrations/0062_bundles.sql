-- 0062_bundles: curated multi-product bundles sold as a set at a set price.
--
-- WHY A FLAT `bundle_price_minor` RATHER THAN A PERCENTAGE
-- Percentage-off (as promotions already do) reads naturally for "X% off your
-- order"; a bundle is closer to "buy this exact set for ₹999", a single
-- advertised number the admin picks directly. `bundle_items` pins the exact
-- variant + quantity combination that price covers -- the same variant-level
-- precision `product_variants` prices everything else at.
--
-- WHY DISCOUNT ENFORCEMENT LIVES IN CHECKOUT, NOT JUST DISPLAY
-- Matching the standard this session already held coupons to: a bundle has to
-- be a real price the customer is charged, not just a shop-page label. When a
-- cart contains at least a bundle's full item list, `resolve_bundle_discount`
-- (services/bundles.py) computes savings against the current live variant
-- prices and `place_order` writes it into `order_adjustments` alongside any
-- coupon/promotion discount -- the two are independent and both apply.
--
-- WHY adjustment_type STAYS 'promotion' (NO NEW ENUM VALUE)
-- order_adjustments.adjustment_type is a CHECK constraint baked into the
-- table (0005_commerce.sql); widening it needs a full table rebuild, which is
-- not D1-safe as a single ALTER. A bundle discount is, semantically, exactly
-- what 'promotion' already means here -- an automatic catalogue discount, as
-- opposed to a customer-entered 'coupon' code -- so it reuses that value and
-- carries "Bundle savings — {name}" in `label` to stay distinguishable in any
-- report that reads order_adjustments.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS bundles (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  slug TEXT NOT NULL UNIQUE,
  description TEXT,
  status TEXT NOT NULL CHECK (status IN ('draft', 'active', 'ended', 'archived')) DEFAULT 'draft',
  bundle_price_minor INTEGER NOT NULL CHECK (bundle_price_minor >= 0),
  image_url TEXT,
  image_alt TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX IF NOT EXISTS idx_bundles_status ON bundles(status);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bundles_slug ON bundles(slug);

CREATE TABLE IF NOT EXISTS bundle_items (
  id TEXT PRIMARY KEY,
  bundle_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  sort_order INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (bundle_id) REFERENCES bundles(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE,
  UNIQUE (bundle_id, variant_id)
);

CREATE INDEX IF NOT EXISTS idx_bundle_items_bundle ON bundle_items(bundle_id, sort_order);

-- Checkout resolves bundle matches by looking up, per variant in the cart,
-- which bundles need it -- the reverse direction from the admin's own
-- "items in this bundle" read.
CREATE INDEX IF NOT EXISTS idx_bundle_items_variant ON bundle_items(variant_id);

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_bundles_view', 'bundles.view', 'View product bundles'),
  ('prm_bundles_manage', 'bundles.manage', 'Create, edit, publish and delete product bundles');

-- Owner, Admin and Manager -- a bundle sets a real sale price, the same
-- commercial-impact tier that governs promotions and price adjustments.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('bundles.view', 'bundles.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('bundles.view', 'bundles.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('bundles.view', 'bundles.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

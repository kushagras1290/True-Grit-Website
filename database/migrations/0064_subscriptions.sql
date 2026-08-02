-- 0064_subscriptions: "Subscribe & Save" recurring deliveries of a single
-- product variant, gated off by default (see `commerce.subscriptions.enabled`
-- in services/feature_settings.py) -- not needed at launch, but built for
-- real rather than stubbed, per the same "tickbox, default off, dormant
-- until switched on" pattern promotions/recommendations already use.
--
-- WHY EACH SUBSCRIPTION IS ONE VARIANT, NOT A CART OF ITEMS
-- "Subscribe & Save" is a per-product commitment a customer makes from that
-- product's own page (mirrors the well-known Amazon/Subscribe-and-save
-- shape) -- not a second cart/checkout system. A customer who wants several
-- products on a schedule creates several subscriptions, each independently
-- pausable/cancellable, rather than one compound object where cancelling
-- half of it is an edit instead of a delete.
--
-- WHY `address_id` (A REFERENCE), NOT A JSON SNAPSHOT LIKE `orders`
-- An order is a historical record -- its delivery address must never drift
-- after the fact, which is why `orders.delivery_address_json` is frozen at
-- checkout. A subscription is the opposite: it is *supposed* to track
-- "wherever this customer currently wants to be delivered to", the same way
-- Subscribe & Save renews against your current default address, not the one
-- on file when you first subscribed. Each renewal snapshots the address
-- in the resulting order exactly like a normal checkout would.
--
-- WHY RENEWALS ARE CASH-ON-DELIVERY ONLY
-- The only payment gateway wired up (Razorpay, see services/payments.py) is
-- a one-time, browser-present checkout: it hands the browser an order to
-- confirm and verifies the signed result -- there is no stored payment
-- method or mandate/token this codebase could charge unattended on a
-- schedule. Building a fake "auto-charge" would be dishonest about what
-- actually happens to the customer's money. COD needs no stored instrument
-- and is already this codebase's default, fully-working payment path (see
-- `services/checkout.place_order`), so subscription renewals reuse it
-- as-is -- a real, functioning recurring delivery, just not a recurring
-- *card charge*. Recurring online payment is future work if a
-- mandate-capable gateway is ever integrated.
--
-- WHY A DISCOUNT PERCENT SETTING, APPLIED THE SAME WAY BUNDLE DISCOUNTS ARE
-- A schedule with no incentive is not "subscribe and save", just "subscribe
-- and wait" -- `commerce.subscriptions.discount_percent` (default 5,
-- services/feature_settings.py) is threaded into `place_order` as a third,
-- independent stacking discount alongside coupon/promotion and bundle
-- discounts (see the WHY note added to services/checkout.py). Recorded via
-- the same 'promotion' `order_adjustments` type bundles already reuse, for
-- the same CHECK-constraint-widening reason documented in 0062_bundles.sql.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS subscriptions (
  id TEXT PRIMARY KEY,
  customer_user_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0 AND quantity <= 12),
  frequency TEXT NOT NULL CHECK (frequency IN ('weekly', 'biweekly', 'monthly')),
  status TEXT NOT NULL CHECK (status IN ('active', 'paused', 'cancelled')) DEFAULT 'active',
  address_id TEXT NOT NULL,
  -- ISO date (YYYY-MM-DD) the next renewal order is due. Compared against
  -- the current UTC date by the renewal job -- see services/subscriptions.py
  -- `list_due`.
  next_order_date TEXT NOT NULL,
  last_order_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  cancelled_at TEXT,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE RESTRICT,
  FOREIGN KEY (address_id) REFERENCES addresses(id) ON DELETE RESTRICT,
  FOREIGN KEY (last_order_id) REFERENCES orders(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer
  ON subscriptions(customer_user_id, status);

-- The renewal job's own read: "every active subscription due on or before
-- today", processed oldest-due first.
CREATE INDEX IF NOT EXISTS idx_subscriptions_due
  ON subscriptions(status, next_order_date);

-- Lets an order be traced back to the subscription that generated it (order
-- history, admin support view) without a join table -- one renewal produces
-- exactly one order, so a nullable column on `orders` is enough; a NULL
-- means an ordinary cart checkout, unrelated to any subscription.
ALTER TABLE orders ADD COLUMN subscription_id TEXT REFERENCES subscriptions(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_orders_subscription
  ON orders(subscription_id)
  WHERE subscription_id IS NOT NULL;

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_subscriptions_view', 'subscriptions.view', 'View customer subscriptions'),
  ('prm_subscriptions_manage', 'subscriptions.manage', 'Pause, resume, cancel subscriptions and run renewals');

-- Owner, Admin and Manager -- subscriptions place real orders on a customer's
-- behalf, the same commercial-impact tier that governs bundles and
-- promotions.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('subscriptions.view', 'subscriptions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('subscriptions.view', 'subscriptions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('subscriptions.view', 'subscriptions.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

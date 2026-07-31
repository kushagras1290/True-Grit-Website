-- 0042_farm_revenue_payouts: per-farm revenue accounting and the payout ledger
-- behind the admin console's Revenue page.
--
-- WHAT A FARM EARNS
-- Revenue is attributed by `order_items.product_id -> products.farm_id`, over
-- orders that actually took money (`payment_status = 'paid'`, order not
-- cancelled). Refunds are netted off pro-rata: `order_adjustments` records
-- refunds against the ORDER, not the line, so on a multi-farm order the only
-- honest attribution is each farm's share of that order's goods value. Paying
-- a farm on gross would hand out money the business has already given back.
--
-- THE CUT
-- `commission_bps` is the platform's cut in basis points (10000 = 100%),
-- matching ADR-006 — money and percentages are integers, never floats. It
-- lives in two places on purpose:
--   * `app_settings['revenue.commission_bps']` — the house default, applied to
--     every farm that has not been given its own rate.
--   * `farms.commission_bps` — a per-farm override. NULL means "follow the
--     default", which is different from 0 ("this farm is charged nothing"),
--     so the column is deliberately nullable rather than defaulted.
-- A payout snapshots the rate it used, so changing the rate later never
-- rewrites what a farm was already paid.
--
-- PAYING ONCE, EXACTLY
-- `farm_payout_items.order_item_id` is the PRIMARY KEY, not a plain column.
-- That is the whole double-payment defence: an order line can be attached to
-- one payout and never a second, enforced by the database rather than by a
-- read-then-write check that two concurrent clicks would both pass. The
-- outstanding balance is therefore "eligible lines not present in this table",
-- which stays correct when an order is paid late or refunded after a payout.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, every insert idempotent.
PRAGMA foreign_keys = ON;

-- NULL = use app_settings['revenue.commission_bps'].
ALTER TABLE farms ADD COLUMN commission_bps INTEGER
  CHECK (commission_bps IS NULL OR (commission_bps >= 0 AND commission_bps <= 10000));

-- House default cut: 15%. Chosen only so the feature is usable on first run;
-- the owner sets the real number from the Revenue page.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('revenue.commission_bps', '1500', '2026-08-01T00:00:00Z');

CREATE TABLE farm_payouts (
  id TEXT PRIMARY KEY,
  farm_id TEXT NOT NULL,
  currency_code TEXT NOT NULL DEFAULT 'INR',
  -- Snapshot of the arithmetic at the moment of payment. Recomputing these
  -- from today's commission rate would silently restate history.
  gross_minor INTEGER NOT NULL CHECK (gross_minor >= 0),
  refunded_minor INTEGER NOT NULL DEFAULT 0 CHECK (refunded_minor >= 0),
  net_revenue_minor INTEGER NOT NULL CHECK (net_revenue_minor >= 0),
  commission_bps INTEGER NOT NULL CHECK (commission_bps >= 0 AND commission_bps <= 10000),
  commission_minor INTEGER NOT NULL CHECK (commission_minor >= 0),
  payout_minor INTEGER NOT NULL CHECK (payout_minor >= 0),
  item_count INTEGER NOT NULL CHECK (item_count > 0),
  -- 'recorded' means the ledger entry exists and the lines are settled; it does
  -- NOT mean a bank transfer happened. No payout rail is wired up (Razorpay
  -- here collects payments, it does not disburse), so an operator moves the
  -- money out of band and files the bank/UPI reference below. `provider` and
  -- `provider_reference` are the seam for automating that later without a
  -- second ledger.
  status TEXT NOT NULL DEFAULT 'recorded' CHECK (status IN ('recorded', 'reversed')),
  provider TEXT,
  provider_reference TEXT,
  reference TEXT,
  note TEXT,
  paid_to_user_id TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  reversed_at TEXT,
  reversed_by TEXT,
  FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE RESTRICT,
  FOREIGN KEY (paid_to_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (reversed_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_farm_payouts_farm_time ON farm_payouts(farm_id, created_at DESC);

CREATE TABLE farm_payout_items (
  -- PRIMARY KEY, not just a foreign key: this is what makes a line payable
  -- exactly once, race or no race.
  order_item_id TEXT PRIMARY KEY,
  payout_id TEXT NOT NULL,
  farm_id TEXT NOT NULL,
  -- Per-line snapshot, so a detailed payout statement can be reproduced
  -- without re-deriving refunds that may since have changed.
  gross_minor INTEGER NOT NULL CHECK (gross_minor >= 0),
  refunded_minor INTEGER NOT NULL DEFAULT 0 CHECK (refunded_minor >= 0),
  net_minor INTEGER NOT NULL CHECK (net_minor >= 0),
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE RESTRICT,
  FOREIGN KEY (payout_id) REFERENCES farm_payouts(id) ON DELETE CASCADE,
  FOREIGN KEY (farm_id) REFERENCES farms(id) ON DELETE RESTRICT
);

CREATE INDEX idx_farm_payout_items_payout ON farm_payout_items(payout_id);
CREATE INDEX idx_farm_payout_items_farm ON farm_payout_items(farm_id);

-- Revenue is money: reading it and moving it are separate grants, so a role can
-- be given oversight without the ability to pay anyone.
INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_revenue_view', 'revenue.view', 'View per-farm revenue, commission and payout history'),
  ('prm_revenue_manage', 'revenue.manage', 'Set farm commission rates and issue farm payouts');

-- Owner and Administrator get both. Accounts — the role that already owns
-- refunds — gets both, since disbursing to farms is the same job.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('revenue.view', 'revenue.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('revenue.view', 'revenue.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_accounts', id FROM permissions
WHERE key IN ('revenue.view', 'revenue.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_accounts');

-- Manager oversees the shop but does not move money out of it: read only.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key = 'revenue.view'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

-- 0082_gift_cards: issuable, purchasable stored-value codes redeemable at
-- checkout toward an order's total.
--
-- WHY A LEDGER, NOT A MUTABLE BALANCE COLUMN
-- Same reasoning inventory_movements and payment_events already use: a gift
-- card's remaining balance is `initial_balance_minor - SUM(gift_card_
-- redemptions.amount_minor)`, derived fresh on every read, never written
-- directly -- a mutable counter invites exactly the lost-update bug a
-- derived balance exists to prevent.
--
-- WHY NEW COLUMNS ON orders, NOT A NEW order_adjustments.adjustment_type
-- order_adjustments.adjustment_type is a CHECK constraint baked into the
-- table (0005_commerce.sql); widening it needs a full table rebuild, not
-- D1-safe as a single ALTER -- see migration 0062's own note on this exact
-- constraint. A gift card redemption also is not really a "discount" in the
-- sense order_adjustments tracks: the business already recognised that
-- revenue when the card was sold/issued. orders.gift_card_applied_minor and
-- gift_card_code sit alongside subtotal_minor/discount_minor as their own
-- first-class order columns instead.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE gift_cards (
  id TEXT PRIMARY KEY,
  code TEXT NOT NULL UNIQUE COLLATE NOCASE,
  initial_balance_minor INTEGER NOT NULL CHECK (initial_balance_minor > 0),
  currency_code TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled', 'expired')),
  issued_to_email TEXT,
  note TEXT,
  expires_at TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE INDEX idx_gift_cards_code ON gift_cards(code);

CREATE TABLE gift_card_redemptions (
  id TEXT PRIMARY KEY,
  gift_card_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  customer_user_id TEXT,
  amount_minor INTEGER NOT NULL CHECK (amount_minor > 0),
  redeemed_at TEXT NOT NULL,
  UNIQUE(gift_card_id, order_id),
  FOREIGN KEY (gift_card_id) REFERENCES gift_cards(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Balance-derivation queries are COUNT/SUM scoped by gift_card_id.
CREATE INDEX idx_gift_card_redemptions_card ON gift_card_redemptions(gift_card_id);

ALTER TABLE orders ADD COLUMN gift_card_applied_minor INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN gift_card_code TEXT;

-- Off by default -- a real payment-adjacent feature an owner switches on
-- deliberately, same reasoning as commerce.promotions.enabled (migration
-- 0060). load_storefront_settings() already defaults a missing row this
-- way; this INSERT just matches 0060's own explicit-seed convention.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.gift_cards.enabled', '0', '2026-08-06T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_gift_cards_view', 'gift_cards.view', 'View gift cards'),
  ('prm_gift_cards_manage', 'gift_cards.manage', 'Issue and cancel gift cards');

-- Owner, Admin and Manager -- issuing stored value is a commercial call with
-- real revenue impact, the same tier that governs promotions/payouts/price
-- adjustments (migration 0060's own reasoning).
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('gift_cards.view', 'gift_cards.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('gift_cards.view', 'gift_cards.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('gift_cards.view', 'gift_cards.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

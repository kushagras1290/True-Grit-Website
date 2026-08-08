-- 0086_loyalty_referral: points earned per order, redeemable like a gift card,
-- plus referral codes that reward both parties once the referred customer's
-- first order ships.
--
-- WHY A LEDGER, NOT A MUTABLE BALANCE COLUMN
-- Same reasoning gift_cards (0082) and inventory_movements already use: a
-- customer's loyalty balance is `SUM(loyalty_transactions.points)`, derived
-- fresh on every read, never written directly -- a mutable counter invites
-- exactly the lost-update bug a derived balance exists to prevent.
--
-- The gift_card ledger pattern is reused directly: earn and redeem are both
-- just ledger rows with positive/negative points, and redemption at checkout
-- converts points to a discount amount the same way gift_card_redemptions
-- does for stored value.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE loyalty_accounts (
  id TEXT PRIMARY KEY,
  customer_user_id TEXT NOT NULL UNIQUE,
  referral_code TEXT NOT NULL UNIQUE COLLATE NOCASE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
  created_at TEXT NOT NULL,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_loyalty_accounts_customer ON loyalty_accounts(customer_user_id);
CREATE INDEX idx_loyalty_accounts_referral ON loyalty_accounts(referral_code);

CREATE TABLE loyalty_transactions (
  id TEXT PRIMARY KEY,
  loyalty_account_id TEXT NOT NULL,
  points INTEGER NOT NULL,
  transaction_type TEXT NOT NULL CHECK (
    transaction_type IN ('earn_order', 'redeem_checkout', 'referral_reward',
                         'admin_credit', 'admin_debit', 'expiry')
  ),
  reference_id TEXT,
  description TEXT,
  created_at TEXT NOT NULL,
  created_by TEXT,
  FOREIGN KEY (loyalty_account_id) REFERENCES loyalty_accounts(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_loyalty_transactions_account ON loyalty_transactions(loyalty_account_id);
CREATE INDEX idx_loyalty_transactions_ref ON loyalty_transactions(reference_id);
CREATE UNIQUE INDEX idx_loyalty_transactions_idempotent_reference
  ON loyalty_transactions(loyalty_account_id, transaction_type, reference_id)
  WHERE reference_id IS NOT NULL;

CREATE TRIGGER trg_loyalty_nonnegative_before_insert
BEFORE INSERT ON loyalty_transactions
WHEN NEW.points < 0 AND (
  SELECT COALESCE(SUM(points), 0) FROM loyalty_transactions
  WHERE loyalty_account_id = NEW.loyalty_account_id
) + NEW.points < 0
BEGIN
  SELECT RAISE(ABORT, 'insufficient loyalty points');
END;

CREATE TABLE referral_redemptions (
  id TEXT PRIMARY KEY,
  referral_code TEXT NOT NULL,
  referrer_account_id TEXT NOT NULL,
  referred_user_id TEXT NOT NULL,
  referred_order_id TEXT,
  referrer_points INTEGER NOT NULL DEFAULT 0,
  referred_points INTEGER NOT NULL DEFAULT 0,
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'cancelled')),
  created_at TEXT NOT NULL,
  completed_at TEXT,
  FOREIGN KEY (referrer_account_id) REFERENCES loyalty_accounts(id) ON DELETE CASCADE,
  FOREIGN KEY (referred_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (referred_order_id) REFERENCES orders(id) ON DELETE SET NULL
);

CREATE INDEX idx_referral_redemptions_referrer ON referral_redemptions(referrer_account_id);
CREATE INDEX idx_referral_redemptions_referred ON referral_redemptions(referred_user_id);

ALTER TABLE orders ADD COLUMN loyalty_points_redeemed INTEGER NOT NULL DEFAULT 0;
ALTER TABLE orders ADD COLUMN loyalty_applied_minor INTEGER NOT NULL DEFAULT 0;

-- Off by default -- a real customer-facing feature an owner switches on
-- deliberately, same reasoning as commerce.gift_cards.enabled (migration
-- 0082). load_storefront_settings() already defaults a missing row this
-- way; this INSERT just matches 0082's own explicit-seed convention.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.loyalty.enabled', '0', '2026-08-08T00:00:00Z'),
  ('commerce.loyalty.points_per_100', '10', '2026-08-08T00:00:00Z'),
  ('commerce.loyalty.referral_reward_points', '100', '2026-08-08T00:00:00Z'),
  ('commerce.loyalty.points_value_minor', '100', '2026-08-08T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_loyalty_view', 'loyalty.view', 'View loyalty accounts and transactions'),
  ('prm_loyalty_manage', 'loyalty.manage', 'Adjust loyalty points and manage referrals');

-- Owner, Admin and Manager -- loyalty management has the same revenue
-- impact as gift cards and promotions.
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('loyalty.view', 'loyalty.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('loyalty.view', 'loyalty.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('loyalty.view', 'loyalty.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

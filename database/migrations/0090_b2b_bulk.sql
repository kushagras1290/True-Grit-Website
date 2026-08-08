-- 0090_b2b_bulk: wholesale/bulk pricing tier for business customers.
--
-- A B2B account is a company-level entity linked to one or more user accounts.
-- B2B customers see quantity-based price breaks on products and can optionally
-- pay via net-terms invoicing instead of immediate payment.
--
-- v1 scope: quantity price breaks, B2B account management, invoice tracking.
-- Full credit-check/approval workflow is deferred to v2.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, every insert
-- idempotent.
PRAGMA foreign_keys = ON;

CREATE TABLE b2b_accounts (
  id TEXT PRIMARY KEY,
  company_name TEXT NOT NULL,
  gst_number TEXT,
  contact_name TEXT,
  contact_email TEXT,
  contact_phone TEXT,
  billing_address_json TEXT NOT NULL DEFAULT '{}',
  credit_limit_minor INTEGER NOT NULL DEFAULT 0,
  payment_terms_days INTEGER NOT NULL DEFAULT 30,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('pending', 'active', 'suspended')),
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_b2b_accounts_status ON b2b_accounts(status);

-- Link users to B2B accounts: a user can belong to at most one B2B account.
ALTER TABLE users ADD COLUMN b2b_account_id TEXT REFERENCES b2b_accounts(id) ON DELETE SET NULL;

CREATE TABLE b2b_price_breaks (
  id TEXT PRIMARY KEY,
  variant_id TEXT NOT NULL,
  min_quantity INTEGER NOT NULL CHECK (min_quantity > 0),
  price_minor INTEGER NOT NULL CHECK (price_minor >= 0),
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(variant_id, min_quantity),
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE CASCADE
);

CREATE INDEX idx_b2b_price_breaks_variant ON b2b_price_breaks(variant_id);

CREATE TABLE b2b_invoices (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  b2b_account_id TEXT NOT NULL,
  invoice_number TEXT NOT NULL UNIQUE,
  amount_minor INTEGER NOT NULL,
  currency_code TEXT NOT NULL DEFAULT 'INR',
  due_date TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'issued' CHECK (
    status IN ('issued', 'sent', 'paid', 'overdue', 'cancelled')
  ),
  payment_reference TEXT,
  issued_at TEXT NOT NULL,
  paid_at TEXT,
  notes TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (b2b_account_id) REFERENCES b2b_accounts(id) ON DELETE RESTRICT
);

CREATE INDEX idx_b2b_invoices_order ON b2b_invoices(order_id);
CREATE INDEX idx_b2b_invoices_account ON b2b_invoices(b2b_account_id);
CREATE INDEX idx_b2b_invoices_status ON b2b_invoices(status);

CREATE TRIGGER trg_b2b_invoice_credit_before_insert
BEFORE INSERT ON b2b_invoices
WHEN (
  SELECT credit_limit_minor FROM b2b_accounts WHERE id = NEW.b2b_account_id
) > 0
AND (
  SELECT COALESCE(SUM(amount_minor), 0) FROM b2b_invoices
  WHERE b2b_account_id = NEW.b2b_account_id
    AND status IN ('issued', 'sent', 'overdue')
) + NEW.amount_minor > (
  SELECT credit_limit_minor FROM b2b_accounts WHERE id = NEW.b2b_account_id
)
BEGIN
  SELECT RAISE(ABORT, 'b2b credit limit exceeded');
END;

INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.b2b.enabled', '0', '2026-08-08T00:00:00Z');

INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_b2b_view', 'b2b.view', 'View B2B accounts, price breaks and invoices'),
  ('prm_b2b_manage', 'b2b.manage', 'Manage B2B accounts, price breaks and invoices');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key IN ('b2b.view', 'b2b.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key IN ('b2b.view', 'b2b.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_manager', id FROM permissions
WHERE key IN ('b2b.view', 'b2b.manage')
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_manager');

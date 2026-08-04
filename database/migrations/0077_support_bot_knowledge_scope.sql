-- 0077_support_bot_knowledge_scope: split support_bot_knowledge (0076) into
-- admin-panel and storefront audiences sharing one table and one admin-panel
-- management UI, rather than building a second parallel CRUD surface.
--
-- The admin bot (services/support_bot.py) reads scope='admin'; the storefront
-- bot (services/support_bot_public.py) reads scope='storefront'. Both stay
-- admin-managed -- customers never edit what their bot knows -- so one
-- support_bot.manage-gated screen just filters by scope instead of needing
-- two.
--
-- SQLite cannot add a CHECK-constrained NOT NULL column with a literal
-- default to an existing table in one ALTER, so this is the standard
-- twelve-step rebuild (see migration 0072 for the same pattern).
PRAGMA foreign_keys = OFF;

CREATE TABLE support_bot_knowledge_new (
  id TEXT PRIMARY KEY,
  scope TEXT NOT NULL DEFAULT 'admin' CHECK (scope IN ('admin', 'storefront')),
  title TEXT NOT NULL,
  keywords TEXT NOT NULL,
  content TEXT NOT NULL,
  is_builtin INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

INSERT INTO support_bot_knowledge_new (
  id, scope, title, keywords, content, is_builtin, created_at, updated_at, updated_by
)
SELECT id, 'admin', title, keywords, content, is_builtin, created_at, updated_at, updated_by
FROM support_bot_knowledge;

DROP TABLE support_bot_knowledge;

ALTER TABLE support_bot_knowledge_new RENAME TO support_bot_knowledge;

CREATE INDEX idx_support_bot_knowledge_scope_title ON support_bot_knowledge(scope, title);

PRAGMA foreign_keys = ON;

-- Storefront-facing reference: policy/how-to answers the customer bot can
-- give directly, without needing a catalogue-search tool call.
INSERT INTO support_bot_knowledge (id, scope, title, keywords, content, is_builtin, created_at, updated_at) VALUES
  ('sbk_sf_001', 'storefront', 'Shipping', 'shipping delivery time cost how long ship', 'Orders are delivered by the partner farm or courier assigned to your area; delivery windows and any delivery fee are shown at checkout before you pay, based on your address.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_sf_002', 'storefront', 'Returns and refunds', 'return refund money back exchange damaged wrong', 'Start a return from your order detail page (Account > Orders) within the window shown there. Once the return is approved, refunds are issued to your original payment method; cash-on-delivery refunds are processed as store credit or bank transfer as arranged with support.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_sf_003', 'storefront', 'Subscribe & Save', 'subscribe save subscription recurring cancel pause', 'Subscribe & Save lets you set a product to reorder automatically on a schedule, usually at a discount. Manage, pause, or cancel an active subscription from your account.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_sf_004', 'storefront', 'Coupons and bundles', 'coupon code discount promo bundle kit combo', 'Coupon codes are entered at checkout and apply their discount to the qualifying items automatically. Bundles are fixed sets of products sold together, usually at a better price than buying each item separately.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_sf_005', 'storefront', 'Payment methods', 'payment pay cash cod card upi online', 'Cash on delivery is available for eligible orders; online payment (cards, UPI, netbanking, wallets) is available at checkout where enabled. Payment methods shown depend on your order total and location.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z'),
  ('sbk_sf_006', 'storefront', 'Account and sign-in', 'account sign in login register phone email password', 'You can sign in with email/password, a Google or Facebook account, or a verified mobile number, depending on what is enabled. Create an account from the sign-in page, or check out as a guest where available.', 1, '2026-08-04T00:00:00Z', '2026-08-04T00:00:00Z');

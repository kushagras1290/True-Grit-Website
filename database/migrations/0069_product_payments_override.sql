-- 0069_product_payments_override: lets a specific product's orderability
-- diverge from the site-wide payments switch (`commerce.payments.enabled`,
-- migration 0040) in EITHER direction.
--
-- WHY THIS DIFFERS FROM `accepts_orders` (migration 0048)
-- `accepts_orders` is a stock/quality signal ("this batch failed a check")
-- that can only narrow -- it takes a product off sale within an already-open
-- storefront, and migration 0048 says so explicitly: "the site-wide switch
-- is still checked first and independently... this one narrows within an
-- already-open storefront, it does not widen a closed one." That was a
-- deliberate limit at the time, not an oversight -- but an owner running a
-- mostly-manual storefront (payments off site-wide) still wants a handful of
-- prepaid or sample products orderable, and conversely wants one specific
-- product pulled from sale even while payments are on generally. Neither
-- direction is expressible with a single boolean, so this is a second,
-- independent tri-state rather than a new meaning grafted onto the first.
--
-- WHY A TRI-STATE, NOT A SECOND BOOLEAN
-- 'inherit' (the default) means "follow the site-wide switch", which must be
-- distinguishable from an explicit "on" or "off" -- a boolean can only ever
-- represent two of those three, and the third would have to be smuggled in
-- via some other column's absence, which is exactly the kind of implicit
-- state this codebase's explicit-permission conventions (see role_permissions,
-- migration 0041) avoid elsewhere.
--
-- ENFORCEMENT
-- Computed and checked in `services.checkout._resolve_line` alongside
-- `accepts_orders` (same authoritative, re-validated-at-checkout spot), and
-- returned on the product detail response so the storefront can swap in the
-- checkout button (or the contact-us fallback) before the customer ever
-- reaches checkout. `services.checkout.place_order` is also what subscription
-- renewals call (`services.subscriptions`), so this same effective check
-- covers recurring orders too, not just the one-off checkout route.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

ALTER TABLE products ADD COLUMN payments_override TEXT NOT NULL DEFAULT 'inherit'
  CHECK (payments_override IN ('inherit', 'force_enabled', 'force_disabled'));

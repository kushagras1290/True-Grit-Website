-- 0048_product_accepts_orders: a per-product order/payment kill-switch,
-- alongside the site-wide one on Site Control (migration 0040,
-- `commerce.payments.enabled`).
--
-- WHY A SEPARATE SWITCH FROM `status`
-- Unpublishing a product removes it from the storefront entirely. This is a
-- narrower thing: a farm runs out of this season's crop, or a batch fails a
-- quality check, but the product page itself -- photos, farm story, reviews
-- -- is still worth keeping live and indexed. `accepts_orders = 0` keeps the
-- page visible and browsable while pulling only the ability to buy it, the
-- same "still shown, cannot be bought" state the site-wide switch puts the
-- whole storefront into.
--
-- DEFAULT 1
-- Every existing and future product is orderable unless someone turns it off
-- -- the same permissive-default posture as every switch introduced since
-- migration 0040, so a missing or unmigrated row never silently stops sales.
--
-- ENFORCEMENT
-- Checked in `services.checkout._resolve_line` (server-authoritative, same
-- place stock and price are re-validated) and returned to the storefront on
-- the product detail response so the page can swap "Add to basket" for a
-- contact form before the customer ever reaches checkout. The site-wide
-- switch is still checked first and independently -- this one narrows within
-- an already-open storefront, it does not widen a closed one.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

ALTER TABLE products ADD COLUMN accepts_orders INTEGER NOT NULL DEFAULT 1
  CHECK (accepts_orders IN (0, 1));

-- 0079_activate_wishlists: activates the dormant `wishlists`/`wishlist_items`
-- schema from 0005_commerce.sql -- shipped on day one and never touched by
-- any repository, service, route, or UI since (confirmed by repo-wide
-- search), the same "activate what's already there" move 0057 made for
-- `reviews` and 0060 made for `promotions`/`coupons`. No new columns are
-- needed: `wishlists(user_id UNIQUE)` and `wishlist_items(wishlist_id,
-- product_id)` are already exactly the right shape -- one wishlist per
-- customer, product-level (not variant-level, which fits the storefront's
-- product-card UI directly: a shop grid card is one product, not a variant
-- picker).
--
-- Only addition: a secondary index for listing a wishlist newest-first. The
-- composite primary key `(wishlist_id, product_id)` is already efficient for
-- "is product X saved" and "every product in wishlist Y", but has no useful
-- order for "most recently saved first".
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables, idempotent to
-- rerun.
CREATE INDEX IF NOT EXISTS idx_wishlist_items_added
  ON wishlist_items(wishlist_id, added_at DESC);

-- 0055_checkout_idempotency: a client-supplied key that makes a retried
-- checkout return the original order instead of placing a second one.
--
-- The key is scoped to the customer, not global, so two different customers
-- can never collide on the same client-generated value. NULL is allowed
-- (older clients, or a request made without one) and deliberately excluded
-- from the unique index -- SQL already treats every NULL as distinct, so
-- this needs no sentinel the way `announcements.country`/`price_adjustments.scope`
-- do; only two real keys for the same customer can ever collide.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT.
PRAGMA foreign_keys = ON;

ALTER TABLE orders ADD COLUMN idempotency_key TEXT;

CREATE UNIQUE INDEX idx_orders_customer_idempotency_key
  ON orders(customer_user_id, idempotency_key)
  WHERE idempotency_key IS NOT NULL;

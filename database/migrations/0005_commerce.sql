-- 0005_commerce: carts, addresses, orders, payments, shipments, wishlists, reviews, promotions
PRAGMA foreign_keys = ON;

CREATE TABLE carts (
  id TEXT PRIMARY KEY,
  customer_user_id TEXT,
  guest_token_hash TEXT,
  currency_code TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL CHECK (status IN ('active', 'converted', 'abandoned', 'expired')),
  expires_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE SET NULL,
  CHECK (customer_user_id IS NOT NULL OR guest_token_hash IS NOT NULL)
);

CREATE UNIQUE INDEX idx_carts_guest_token
  ON carts(guest_token_hash)
  WHERE guest_token_hash IS NOT NULL;

CREATE INDEX idx_carts_customer
  ON carts(customer_user_id, status);

CREATE TABLE cart_items (
  id TEXT PRIMARY KEY,
  cart_id TEXT NOT NULL,
  variant_id TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  added_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE(cart_id, variant_id),
  FOREIGN KEY (cart_id) REFERENCES carts(id) ON DELETE CASCADE,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE RESTRICT
);

CREATE TABLE addresses (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  label TEXT,
  recipient_name TEXT NOT NULL,
  phone_e164 TEXT,
  line1 TEXT NOT NULL,
  line2 TEXT,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  postal_code TEXT NOT NULL,
  country_code TEXT NOT NULL DEFAULT 'IN',
  is_default_delivery INTEGER NOT NULL DEFAULT 0 CHECK (is_default_delivery IN (0, 1)),
  is_default_billing INTEGER NOT NULL DEFAULT 0 CHECK (is_default_billing IN (0, 1)),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  archived_at TEXT,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_addresses_user
  ON addresses(user_id, archived_at);

CREATE TABLE orders (
  id TEXT PRIMARY KEY,
  public_reference TEXT NOT NULL UNIQUE,
  customer_user_id TEXT,
  customer_email TEXT NOT NULL,
  customer_phone_e164 TEXT,
  currency_code TEXT NOT NULL DEFAULT 'INR',
  subtotal_minor INTEGER NOT NULL CHECK (subtotal_minor >= 0),
  discount_minor INTEGER NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
  delivery_minor INTEGER NOT NULL DEFAULT 0 CHECK (delivery_minor >= 0),
  tax_minor INTEGER NOT NULL DEFAULT 0 CHECK (tax_minor >= 0),
  total_minor INTEGER NOT NULL CHECK (total_minor >= 0),
  order_status TEXT NOT NULL CHECK (
    order_status IN ('pending_payment', 'confirmed', 'processing', 'completed', 'cancelled')
  ),
  payment_status TEXT NOT NULL CHECK (
    payment_status IN ('not_required', 'pending', 'authorized', 'paid', 'partially_refunded', 'refunded', 'failed')
  ),
  fulfilment_status TEXT NOT NULL CHECK (
    fulfilment_status IN ('unfulfilled', 'reserved', 'picking', 'packed', 'quality_checked', 'dispatched', 'partially_fulfilled', 'fulfilled', 'cancelled')
  ),
  delivery_status TEXT NOT NULL CHECK (
    delivery_status IN ('not_ready', 'awaiting_carrier', 'in_transit', 'out_for_delivery', 'delivered', 'delivery_failed', 'returned')
  ),
  billing_address_json TEXT,
  delivery_address_json TEXT,
  promotion_snapshot_json TEXT,
  placed_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_orders_customer_time
  ON orders(customer_user_id, created_at DESC);

CREATE INDEX idx_orders_status_time
  ON orders(order_status, created_at DESC);

CREATE TABLE order_items (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  product_id TEXT,
  variant_id TEXT,
  product_name TEXT NOT NULL,
  variant_name TEXT NOT NULL,
  sku TEXT NOT NULL,
  quantity INTEGER NOT NULL CHECK (quantity > 0),
  unit_list_amount_minor INTEGER NOT NULL CHECK (unit_list_amount_minor >= 0),
  unit_effective_amount_minor INTEGER NOT NULL CHECK (unit_effective_amount_minor >= 0),
  discount_minor INTEGER NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
  tax_minor INTEGER NOT NULL DEFAULT 0 CHECK (tax_minor >= 0),
  line_total_minor INTEGER NOT NULL CHECK (line_total_minor >= 0),
  product_snapshot_json TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL,
  FOREIGN KEY (variant_id) REFERENCES product_variants(id) ON DELETE SET NULL
);

CREATE INDEX idx_order_items_order
  ON order_items(order_id);

CREATE TABLE order_adjustments (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  adjustment_type TEXT NOT NULL CHECK (
    adjustment_type IN ('promotion', 'coupon', 'manual_discount', 'delivery_fee', 'refund')
  ),
  label TEXT NOT NULL,
  amount_minor INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  created_by TEXT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE payments (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  provider_intent_id TEXT,
  amount_minor INTEGER NOT NULL CHECK (amount_minor >= 0),
  currency_code TEXT NOT NULL DEFAULT 'INR',
  status TEXT NOT NULL CHECK (
    status IN ('created', 'pending', 'authorized', 'paid', 'partially_refunded', 'refunded', 'failed', 'cancelled')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE RESTRICT
);

CREATE UNIQUE INDEX idx_payments_provider_intent
  ON payments(provider, provider_intent_id)
  WHERE provider_intent_id IS NOT NULL;

CREATE TABLE payment_events (
  id TEXT PRIMARY KEY,
  payment_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  provider_event_id TEXT,
  amount_minor INTEGER,
  created_at TEXT NOT NULL,
  FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE CASCADE
);

CREATE TABLE shipments (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  carrier TEXT,
  tracking_reference TEXT,
  status TEXT NOT NULL CHECK (
    status IN ('pending', 'packed', 'dispatched', 'in_transit', 'out_for_delivery', 'delivered', 'failed', 'returned')
  ),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

CREATE TABLE shipment_events (
  id TEXT PRIMARY KEY,
  shipment_id TEXT NOT NULL,
  event_type TEXT NOT NULL,
  note TEXT,
  actor_id TEXT,
  customer_visible INTEGER NOT NULL DEFAULT 1 CHECK (customer_visible IN (0, 1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(id) ON DELETE CASCADE,
  FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE wishlists (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL,
  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE wishlist_items (
  wishlist_id TEXT NOT NULL,
  product_id TEXT NOT NULL,
  added_at TEXT NOT NULL,
  PRIMARY KEY (wishlist_id, product_id),
  FOREIGN KEY (wishlist_id) REFERENCES wishlists(id) ON DELETE CASCADE,
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

CREATE TABLE reviews (
  id TEXT PRIMARY KEY,
  product_id TEXT NOT NULL,
  customer_user_id TEXT NOT NULL,
  order_id TEXT,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  title TEXT,
  body TEXT,
  status TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'rejected', 'removed')),
  created_at TEXT NOT NULL,
  moderated_at TEXT,
  moderated_by TEXT,
  UNIQUE(product_id, customer_user_id, order_id),
  FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE CASCADE,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL,
  FOREIGN KEY (moderated_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_reviews_product_status
  ON reviews(product_id, status, created_at DESC);

CREATE TABLE promotions (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('draft', 'scheduled', 'active', 'paused', 'ended', 'archived')),
  priority INTEGER NOT NULL DEFAULT 0,
  starts_at TEXT,
  ends_at TEXT,
  stacking_policy TEXT NOT NULL DEFAULT 'exclusive' CHECK (
    stacking_policy IN ('exclusive', 'stackable')
  ),
  usage_limit_total INTEGER CHECK (usage_limit_total IS NULL OR usage_limit_total > 0),
  usage_limit_per_customer INTEGER CHECK (usage_limit_per_customer IS NULL OR usage_limit_per_customer > 0),
  created_at TEXT NOT NULL,
  created_by TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  updated_by TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE RESTRICT,
  CHECK (ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at)
);

CREATE TABLE promotion_rules (
  id TEXT PRIMARY KEY,
  promotion_id TEXT NOT NULL,
  rule_json TEXT NOT NULL,
  FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE CASCADE
);

CREATE TABLE promotion_actions (
  id TEXT PRIMARY KEY,
  promotion_id TEXT NOT NULL,
  action_type TEXT NOT NULL CHECK (
    action_type IN ('percentage_discount', 'fixed_discount', 'free_delivery')
  ),
  value_basis_points INTEGER CHECK (value_basis_points IS NULL OR (value_basis_points BETWEEN 0 AND 10000)),
  amount_minor INTEGER CHECK (amount_minor IS NULL OR amount_minor >= 0),
  maximum_discount_minor INTEGER CHECK (maximum_discount_minor IS NULL OR maximum_discount_minor >= 0),
  FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE CASCADE
);

CREATE TABLE coupons (
  id TEXT PRIMARY KEY,
  promotion_id TEXT NOT NULL,
  code TEXT NOT NULL UNIQUE COLLATE NOCASE,
  active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
  created_at TEXT NOT NULL,
  FOREIGN KEY (promotion_id) REFERENCES promotions(id) ON DELETE CASCADE
);

CREATE TABLE coupon_redemptions (
  id TEXT PRIMARY KEY,
  coupon_id TEXT NOT NULL,
  order_id TEXT NOT NULL,
  customer_user_id TEXT,
  redeemed_at TEXT NOT NULL,
  UNIQUE(coupon_id, order_id),
  FOREIGN KEY (coupon_id) REFERENCES coupons(id) ON DELETE RESTRICT,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE SET NULL
);

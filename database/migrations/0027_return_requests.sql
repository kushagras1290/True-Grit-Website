-- 0027_return_requests: customer-initiated return/refund requests (RMA),
-- reviewed and resolved from a dedicated admin section. Modelled as an
-- append-and-update record per order (or order line), separate from
-- order_adjustments (which stays the immutable ledger of amounts actually
-- applied to an order once a return is resolved as a refund).
PRAGMA foreign_keys = ON;

CREATE TABLE return_requests (
  id TEXT PRIMARY KEY,
  order_id TEXT NOT NULL,
  order_item_id TEXT,
  customer_user_id TEXT NOT NULL,
  reason_code TEXT NOT NULL CHECK (
    reason_code IN ('damaged', 'wrong_item', 'quality_issue', 'not_as_described', 'missing_item', 'other')
  ),
  description TEXT NOT NULL,
  evidence_media_ids_json TEXT,
  status TEXT NOT NULL DEFAULT 'requested' CHECK (
    status IN ('requested', 'under_review', 'approved', 'rejected', 'refunded', 'replaced', 'completed', 'cancelled')
  ),
  requested_refund_amount_minor INTEGER CHECK (requested_refund_amount_minor IS NULL OR requested_refund_amount_minor >= 0),
  resolution_type TEXT CHECK (resolution_type IS NULL OR resolution_type IN ('refund', 'replacement', 'store_credit', 'none')),
  resolution_amount_minor INTEGER CHECK (resolution_amount_minor IS NULL OR resolution_amount_minor >= 0),
  resolution_notes TEXT,
  requested_at TEXT NOT NULL,
  resolved_at TEXT,
  resolved_by TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
  FOREIGN KEY (order_item_id) REFERENCES order_items(id) ON DELETE SET NULL,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE RESTRICT,
  FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX idx_return_requests_order
  ON return_requests(order_id);

CREATE INDEX idx_return_requests_status_time
  ON return_requests(status, requested_at DESC);

CREATE INDEX idx_return_requests_customer_time
  ON return_requests(customer_user_id, requested_at DESC);

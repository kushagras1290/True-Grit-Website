-- Durable queue consumer idempotency. Queue delivery is at-least-once, so a
-- successful side effect must be recorded before a duplicate can repeat it.

CREATE TABLE processed_queue_messages (
  idempotency_key TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  completed_at TEXT NOT NULL
);

CREATE INDEX idx_processed_queue_messages_completed
  ON processed_queue_messages(completed_at);

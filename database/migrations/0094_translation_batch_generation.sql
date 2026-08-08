-- Large interface selections are generated into queue tasks gradually. This
-- keeps a "select all" request small, respects D1's 100-bound-parameter limit,
-- and lets the existing minute scheduler provide natural backpressure.
PRAGMA foreign_keys = ON;

ALTER TABLE translation_batches
  ADD COLUMN generation_cursor INTEGER NOT NULL DEFAULT 0
  CHECK (generation_cursor >= 0);

ALTER TABLE translation_batches
  ADD COLUMN generation_complete INTEGER NOT NULL DEFAULT 1
  CHECK (generation_complete IN (0, 1));

CREATE INDEX idx_translation_batches_generation
  ON translation_batches(generation_complete, created_at);

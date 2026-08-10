-- Durable bulk translation runs. One admin action can fan out selected text
-- across every active language without keeping an HTTP request open while
-- Workers AI completes the work.
PRAGMA foreign_keys = ON;

CREATE TABLE translation_batches (
  id TEXT PRIMARY KEY,
  mode TEXT NOT NULL CHECK (mode IN ('content', 'interface')),
  resource_type TEXT,
  target TEXT CHECK (target IS NULL OR target IN ('storefront', 'admin')),
  payload_json TEXT NOT NULL DEFAULT '{}',
  overwrite_existing INTEGER NOT NULL DEFAULT 0 CHECK (overwrite_existing IN (0, 1)),
  total_tasks INTEGER NOT NULL CHECK (total_tasks > 0),
  status TEXT NOT NULL DEFAULT 'queued' CHECK (
    status IN ('queued', 'running', 'completed', 'partial', 'failed')
  ),
  created_by TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE RESTRICT
);

CREATE TABLE translation_batch_tasks (
  id TEXT PRIMARY KEY,
  batch_id TEXT NOT NULL,
  locale TEXT NOT NULL COLLATE NOCASE,
  resource_type TEXT,
  resource_id TEXT,
  payload_json TEXT NOT NULL DEFAULT '{}',
  status TEXT NOT NULL DEFAULT 'pending' CHECK (
    status IN ('pending', 'queued', 'running', 'completed', 'failed')
  ),
  translated_count INTEGER NOT NULL DEFAULT 0,
  error_summary TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (batch_id) REFERENCES translation_batches(id) ON DELETE CASCADE
);

CREATE INDEX idx_translation_batch_tasks_dispatch
  ON translation_batch_tasks(status, created_at);

CREATE INDEX idx_translation_batch_tasks_batch
  ON translation_batch_tasks(batch_id, status, locale);

CREATE INDEX idx_translation_batches_created
  ON translation_batches(created_at DESC);

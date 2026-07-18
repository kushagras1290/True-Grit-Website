-- 0031_application_logs: persisted copy of severe server log events (5xx
-- AppErrors and unhandled exceptions only — see error_handler.py) so the
-- owner-only Server Logs admin page has something queryable. Every other
-- log_event() call stays stdout-only; this table is not a general log sink.
PRAGMA foreign_keys = ON;

CREATE TABLE application_logs (
  id TEXT PRIMARY KEY,
  level TEXT NOT NULL,
  event TEXT NOT NULL,
  fields_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE INDEX idx_application_logs_created_at
  ON application_logs(created_at DESC);

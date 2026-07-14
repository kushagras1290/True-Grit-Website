-- 0008_auth_rate_limits: fixed-window rate limiting for authentication.
--
-- Durable, DB-backed counters so brute-force and credential-stuffing limits
-- hold across Worker isolates (D1 is shared) — an in-process counter would
-- reset per isolate and per deploy. Each key is one bucket; the window resets
-- in place via an UPSERT. `expires_at` supports periodic cleanup of idle keys.
PRAGMA foreign_keys = ON;

CREATE TABLE auth_rate_limits (
  key TEXT PRIMARY KEY,
  window_start TEXT NOT NULL,
  count INTEGER NOT NULL,
  expires_at TEXT NOT NULL
);

CREATE INDEX idx_auth_rate_limits_expiry ON auth_rate_limits(expires_at);

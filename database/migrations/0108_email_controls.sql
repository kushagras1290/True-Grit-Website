-- 0108_email_controls: per-category email toggles/rate limits and send log.
--
-- Categorizes every outbox email so an operator can disable a category or cap
-- its send rate from the admin console (services/email_gate.py). Toggles and
-- limits themselves live in app_settings, same as every other admin switch
-- (services/feature_settings.py) -- this migration only adds what app_settings
-- cannot hold: a durable rate-limit counter and a per-attempt outcome log.
PRAGMA foreign_keys = ON;

ALTER TABLE outbox_events ADD COLUMN category TEXT NOT NULL DEFAULT 'uncategorized';
CREATE INDEX idx_outbox_events_category ON outbox_events(category);

-- Fixed-window counters for email sends. Same shape and UPSERT algorithm as
-- auth_rate_limits (0008), kept in a separate table because email throttling
-- and login brute-force protection are different concerns that only happen
-- to share an algorithm -- mixing their keys into one table would make either
-- one harder to reason about or clean up independently.
CREATE TABLE email_rate_limits (
  key TEXT PRIMARY KEY,
  window_start TEXT NOT NULL,
  count INTEGER NOT NULL,
  expires_at TEXT NOT NULL
);
CREATE INDEX idx_email_rate_limits_expiry ON email_rate_limits(expires_at);

-- One row per send attempt outcome, for the admin activity view. No raw
-- recipient address is stored -- mirrors hash_identifier's privacy stance in
-- auth/rate_limit.py -- domain only, enough to debug delivery without holding
-- a customer's full address in a log table.
CREATE TABLE email_send_log (
  id TEXT PRIMARY KEY,
  category TEXT NOT NULL,
  provider TEXT NOT NULL,
  outcome TEXT NOT NULL CHECK (
    outcome IN ('sent', 'blocked_disabled', 'rate_limited', 'provider_error')
  ),
  detail TEXT,
  recipient_domain TEXT,
  outbox_event_id TEXT,
  occurred_at TEXT NOT NULL
);
CREATE INDEX idx_email_send_log_occurred ON email_send_log(occurred_at);
CREATE INDEX idx_email_send_log_category ON email_send_log(category, occurred_at);

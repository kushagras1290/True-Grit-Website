-- 0112_experiments: A/B testing and experimentation framework.
--
-- Two tables: `experiments` holds the experiment definitions (key, variants,
-- allocation percentage, metric type, lifecycle status); `experiment_events`
-- holds the raw event log (exposure, conversion, intermediate metrics).
--
-- Variant assignment is hash-based and deterministic — no per-assignment write.
-- Events are appended here at key moments (variant shown, purchase completed,
-- add-to-cart, checkout-started) and aggregated on read for the stats engine.
--
-- The stats engine (services/experiments.py) computes two-proportion z-tests,
-- Welch's t-tests, power analysis, and mSPRT sequential testing on top of this
-- data — the "statistically significant" flag in the admin dashboard only
-- lights up when the sequential test confirms it, not on a naive peek.
--
-- D1-safe: no BEGIN TRANSACTION / SAVEPOINT, no TEMP tables.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS experiments (
  id          TEXT PRIMARY KEY,
  key         TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  status      TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN ('draft', 'running', 'completed', 'stopped')),
  -- JSON array: [{"key":"control","name":"Control"}, ...]
  variants         TEXT NOT NULL,
  allocation_pct   INTEGER NOT NULL DEFAULT 100
                     CHECK (allocation_pct BETWEEN 0 AND 100),
  -- 'conversion' (binary: did they buy?) or 'continuous' (order value, etc.)
  primary_metric   TEXT NOT NULL DEFAULT 'conversion'
                     CHECK (primary_metric IN ('conversion', 'continuous')),
  -- Pre-computed via power analysis; NULL means "run until manually stopped".
  target_sample_size INTEGER,
  started_at  TEXT,
  ended_at    TEXT,
  created_at  TEXT NOT NULL,
  created_by  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS experiment_events (
  id              TEXT PRIMARY KEY,
  experiment_key  TEXT NOT NULL,
  variant         TEXT NOT NULL,
  user_id         TEXT NOT NULL,
  -- 'exposure' (variant shown), 'conversion' (purchase completed),
  -- 'add_to_cart', 'checkout_started', or any custom intermediate event.
  event_type      TEXT NOT NULL,
  -- For continuous metrics: the measured value (e.g. order total in minor
  -- units). NULL for binary events.
  event_value     REAL,
  created_at      TEXT NOT NULL
);

-- Fast aggregation: GROUP BY experiment_key, variant, event_type.
CREATE INDEX IF NOT EXISTS idx_experiment_events_agg
  ON experiment_events (experiment_key, variant, event_type);

-- Dedup / per-user lookups: one exposure per user per experiment.
CREATE INDEX IF NOT EXISTS idx_experiment_events_user
  ON experiment_events (experiment_key, user_id, event_type);

-- Permission: who can manage experiments from the admin console.
INSERT OR IGNORE INTO permissions (id, key, description) VALUES
  ('prm_experiments_manage', 'experiments.manage', 'Manage A/B testing experiments and view results');

-- Grant to super_admin and admin roles (same pattern as analytics.view).
INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_super_admin', id FROM permissions
WHERE key = 'experiments.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_super_admin');

INSERT OR IGNORE INTO role_permissions (role_id, permission_id)
SELECT 'rol_admin', id FROM permissions
WHERE key = 'experiments.manage'
  AND EXISTS (SELECT 1 FROM roles WHERE id = 'rol_admin');

-- Seed the first experiment (draft — the admin starts it when ready).
INSERT OR IGNORE INTO experiments (
  id, key, name, description, status, variants, allocation_pct,
  primary_metric, target_sample_size, created_at, created_by, updated_at
) VALUES (
  'exp_00000000000000000000000001',
  'checkout_free_ship_msg',
  'Free-Shipping Threshold Messaging',
  'Test whether urgency framing ("You''re ₹X away from FREE delivery!") lifts conversion and average order value compared to the current static message ("Free delivery on orders above ₹1,500").',
  'draft',
  '[{"key":"control","name":"Control — static message"},{"key":"urgency","name":"Urgency — dynamic countdown"}]',
  100,
  'conversion',
  NULL,
  '2026-08-19T00:00:00Z',
  'system',
  '2026-08-19T00:00:00Z'
);

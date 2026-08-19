-- 0113_refund_orchestrator: deterministic fraud-scoring pipeline that
-- pre-screens customer return requests (services/refund_orchestrator/) and
-- auto-approves/escalates/denies them, writing real Razorpay refunds through
-- the same gateway path staff already use.
--
-- `refund_orchestrator_runs` is the durable, inspectable record of every
-- evaluation -- the admin Returns detail page reads it to show the risk
-- score and fired signals next to a return, and it is what makes an
-- automated decision auditable rather than a black box.
--
-- `usr_refund_orchestrator` is a synthetic, disabled staff account -- same
-- pattern as the `usr_author_*` bylines in migration 0050 -- so the pipeline
-- has a real `users.id` to write as `return_requests.resolved_by` and
-- `audit_logs.actor_user_id` without ever being a real login.
PRAGMA foreign_keys = ON;

CREATE TABLE refund_orchestrator_runs (
  id TEXT PRIMARY KEY,
  return_request_id TEXT NOT NULL,
  risk_score REAL NOT NULL,
  decision TEXT NOT NULL CHECK (decision IN ('auto_approve', 'escalate', 'auto_deny')),
  signals_json TEXT NOT NULL,
  rationale TEXT NOT NULL,
  created_at TEXT NOT NULL,
  FOREIGN KEY (return_request_id) REFERENCES return_requests(id) ON DELETE CASCADE
);

CREATE INDEX idx_refund_orchestrator_runs_return
  ON refund_orchestrator_runs(return_request_id);

INSERT OR IGNORE INTO users (
  id, email, display_name, user_type, status, created_at, updated_at
) VALUES (
  'usr_refund_orchestrator', 'refund-orchestrator@truegrit.invalid', 'True Grit Refund Agent',
  'staff', 'disabled', '2026-08-19T00:00:00Z', '2026-08-19T00:00:00Z'
);

-- Off by default -- a real financial/business-risk decision an operator
-- switches on deliberately, the same bucket `feature_settings.py` puts gift
-- cards, promotions and subscriptions in, not a permissive fallback.
INSERT OR IGNORE INTO app_settings (key, value, updated_at) VALUES
  ('commerce.refund_orchestrator.enabled', '0', '2026-08-19T00:00:00Z');

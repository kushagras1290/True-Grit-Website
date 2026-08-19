-- 0109_support_bot_deterministic: backing tables for the deterministic
-- storefront support bot (apps/api/src/truegrit_api/support_bot/).
--
-- The storefront bot no longer calls a language model. It classifies a message
-- against a fixed intent taxonomy, resolves the answer from live rows, and
-- renders a fixed template -- so it can only ever say something a row or a
-- template already contained. Two things that pipeline needs do not exist yet:
--
--   1. `support_bot_policy_facts` -- the standing facts a template interpolates
--      (return window, refund processing time, support hours). These are
--      deliberately seeded EMPTY. A blank fact makes the template that needs it
--      unrenderable, and an unrenderable template escalates to a human instead
--      of answering. That is the point: the bot must never state a policy
--      figure nobody configured, which is exactly the failure mode replacing
--      the model was meant to remove. An owner fills these in once from
--      Site Settings and the matching answers switch on.
--
--   2. `support_bot_escalations` -- every handover to a person, with the
--      message, what the classifier thought it might have been, and any order
--      context already resolved. Two jobs: the human picking it up does not
--      start cold, and the accumulated rows are the evidence for which
--      phrasings to add to the phrasebook next. Unrecognised questions are the
--      only signal this design has for improving its own coverage, so they are
--      recorded rather than counted.
--
-- Reads are gated on the existing `support_bot.manage` permission (0076); no
-- new permission is introduced for what is the same operator responsibility.
PRAGMA foreign_keys = ON;

CREATE TABLE support_bot_policy_facts (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL DEFAULT '',
  label TEXT NOT NULL,
  hint TEXT NOT NULL DEFAULT '',
  sort_order INTEGER NOT NULL DEFAULT 0,
  updated_at TEXT,
  updated_by TEXT,
  FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
);

-- Seeded with labels and hints only. `value` stays empty until an owner sets
-- it; see the header for why a blank value is a feature and not a gap.
INSERT INTO support_bot_policy_facts (key, label, hint, sort_order) VALUES
  ('return_window_days', 'Return window (days)', 'How many days after delivery a customer can start a return. Leave blank to send return-policy questions to a human.', 10),
  ('refund_processing_days', 'Refund processing time (days)', 'Working days between an approved return and the money reaching the customer.', 20),
  ('standard_delivery_days', 'Standard delivery time (days)', 'Typical door-to-door time for a normal order.', 30),
  ('free_delivery_threshold', 'Free delivery above', 'Order value that qualifies for free delivery, written as you want it shown, e.g. "Rs 999".', 40),
  ('delivery_fee', 'Standard delivery fee', 'Written as you want it shown, e.g. "Rs 49".', 50),
  ('cod_available', 'Cash on delivery offered', 'Enter yes or no. Blank sends the question to a human.', 60),
  ('international_shipping', 'Ships internationally', 'Enter yes or no. Blank sends the question to a human.', 70),
  ('support_email', 'Support email address', 'Shown when the bot hands a conversation over.', 80),
  ('support_phone', 'Support phone number', 'Optional. Leave blank if you do not offer phone support.', 90),
  ('support_hours', 'Support hours', 'e.g. "Mon-Sat, 9am-6pm IST". Shown alongside an escalation so the customer knows when to expect a reply.', 100);

CREATE TABLE support_bot_escalations (
  id TEXT PRIMARY KEY,
  created_at TEXT NOT NULL,
  -- Null for an anonymous visitor. The conversation is still worth keeping:
  -- most pre-purchase questions come from people who are not signed in.
  customer_user_id TEXT,
  -- The request id that produced this, so an escalation can be lined up with
  -- the structured logs for the same turn.
  request_id TEXT NOT NULL,
  message TEXT NOT NULL,
  intent TEXT NOT NULL,
  confidence REAL NOT NULL,
  -- Which classifier tier decided: 'rule', 'lexical', or 'guard'.
  tier TEXT NOT NULL,
  -- Why a person is needed, not what the message was about:
  -- 'policy' (the intent always escalates), 'low_confidence', 'ambiguous',
  -- 'guard' (refused and flagged), 'unconfigured' (a policy fact is blank),
  -- 'repeat' (the customer asked the same thing again after a clarification).
  reason TEXT NOT NULL,
  severity TEXT NOT NULL DEFAULT 'normal' CHECK (severity IN ('normal', 'high', 'critical')),
  -- What the classifier's runner-up intents were, as JSON. This is the column
  -- that tells an operator which phrasing to add to the phrasebook.
  alternatives_json TEXT,
  -- Order references, PIN codes and similar pulled out of the message.
  slots_json TEXT,
  -- Anything a resolver already fetched (the order row, the return row) so the
  -- human does not have to look it up again.
  context_json TEXT,
  status TEXT NOT NULL DEFAULT 'open'
    CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed')),
  resolved_at TEXT,
  resolved_by TEXT,
  resolution_note TEXT,
  FOREIGN KEY (customer_user_id) REFERENCES users(id) ON DELETE SET NULL,
  FOREIGN KEY (resolved_by) REFERENCES users(id) ON DELETE SET NULL
);

-- The queue view: open items, most severe first, oldest first within a
-- severity. Matches how the admin screen reads it.
CREATE INDEX idx_support_bot_escalations_queue
  ON support_bot_escalations(status, severity, created_at);

-- The improvement view: which intents keep escalating, and what the
-- unrecognised messages looked like.
CREATE INDEX idx_support_bot_escalations_intent
  ON support_bot_escalations(intent, created_at);

CREATE INDEX idx_support_bot_escalations_customer
  ON support_bot_escalations(customer_user_id, created_at);

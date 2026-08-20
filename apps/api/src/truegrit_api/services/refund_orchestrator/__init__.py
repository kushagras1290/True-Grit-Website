"""Deterministic, multi-stage refund orchestrator.

reader -> fraud_signals -> decision -> executor -> notifier. No Workers AI /
LLM call anywhere in the decision path: every outcome traces to a DB row and
a named, weighted rule. See `executor.run_refund_orchestrator` for the entry
point wired into the queue consumer, and `database/migrations/0113_refund_orchestrator.sql`
for the schema and feature-toggle default.
"""

from __future__ import annotations

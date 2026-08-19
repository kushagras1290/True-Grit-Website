"""Stage 4, and the pipeline's entry point: turn a decision into real writes.

Runs as a synthetic system `Principal`, built literally in code -- the same
approach `services.subscriptions._renewal_principal` uses to place unattended
renewal orders -- but explicitly granted the minimum staff permissions this
pipeline needs (`returns.view`, `returns.manage`, `orders.refund`) rather than
a customer's own. The backing `usr_refund_orchestrator` user row (migration
0113) is a real, disabled staff account, so every write this pipeline makes
is attributable in `return_requests.resolved_by` and `audit_logs` to a real,
never-loggable-in user -- distinguishable at a glance from a human decision.

Every code path here reuses the *existing* return-request service functions
(`decide_return_request`, `resolve_return_request`) rather than writing to
`return_requests`/`payments`/`payment_events` directly -- so a human
reviewing an auto-approved or auto-denied return in the admin Returns page
sees exactly the same audit trail shape a manually-resolved one has, and any
future change to that lifecycle logic (validation, audit fields) applies to
the orchestrator automatically instead of drifting out of sync.
"""

from __future__ import annotations

import json

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services.refund_orchestrator.decision import Decision, DecisionOutcome, decide
from truegrit_api.services.refund_orchestrator.fraud_signals import RiskAssessment, score_context
from truegrit_api.services.refund_orchestrator.notifier import notify_customer
from truegrit_api.services.refund_orchestrator.reader import RefundContext, gather_context
from truegrit_api.services.returns import decide_return_request, resolve_return_request
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

SYSTEM_ACTOR_USER_ID: str = "usr_refund_orchestrator"
_SYSTEM_ACTOR_PERMISSIONS = frozenset({"returns.view", "returns.manage", "orders.refund"})


def _system_principal() -> Principal:
    return Principal(
        user_id=SYSTEM_ACTOR_USER_ID,
        display_name="True Grit Refund Agent",
        email="refund-orchestrator@truegrit.invalid",
        user_type="staff",
        permissions=_SYSTEM_ACTOR_PERMISSIONS,
    )


async def _persist_run(
    db: Database,
    *,
    return_request_id: str,
    assessment: RiskAssessment,
    outcome: DecisionOutcome,
) -> None:
    signals_json = json.dumps(
        [
            {"id": hit.id, "label": hit.label, "weight": hit.weight, "rationale": hit.rationale}
            for hit in assessment.signals
        ]
    )
    await db.execute(
        "INSERT INTO refund_orchestrator_runs"
        " (id, return_request_id, risk_score, decision, signals_json, rationale, created_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            new_id("ror"),
            return_request_id,
            assessment.score,
            outcome.decision.value,
            signals_json,
            outcome.rationale,
            utc_now_iso(),
        ),
    )


async def run_refund_orchestrator(db: Database, return_request_id: str) -> DecisionOutcome:
    """The pipeline entry point: gather context, score it, decide, act,
    persist the run, and notify the customer if the outcome changes anything
    for them. Called from the queue consumer (`worker.py`'s `evaluate_refund`
    closure) once per return request, at most once per idempotency key --
    `process_queue_job` already guarantees that."""
    ctx: RefundContext = await gather_context(db, return_request_id)
    assessment = score_context(ctx)
    outcome = decide(ctx, assessment)
    actor = _system_principal()
    request_id = new_id("req")

    if outcome.decision == Decision.AUTO_APPROVE:
        await decide_return_request(db, actor, request_id, return_request_id, decision="approved")
        refund_amount = ctx.requested_refund_amount_minor
        assert refund_amount is not None  # decide() escalates otherwise
        await resolve_return_request(
            db,
            actor,
            request_id,
            return_request_id,
            resolution_type="refund",
            resolution_amount_minor=refund_amount,
            resolution_notes=f"Auto-approved by the refund agent. {outcome.rationale}",
        )
        await notify_customer(
            db, ctx=ctx, outcome=outcome, refunded_amount_minor=refund_amount
        )
    elif outcome.decision == Decision.AUTO_DENY:
        await decide_return_request(db, actor, request_id, return_request_id, decision="rejected")
        await notify_customer(db, ctx=ctx, outcome=outcome, refunded_amount_minor=None)
    else:
        await decide_return_request(
            db, actor, request_id, return_request_id, decision="under_review"
        )

    await _persist_run(
        db, return_request_id=return_request_id, assessment=assessment, outcome=outcome
    )
    return outcome

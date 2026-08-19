"""Stage 3: turn a risk assessment into one of three bands.

Biased toward escalation -- the same stance the deterministic support bot's
gate takes ("below threshold, escalate, never guess"), applied to money: a
real customer wrongly denied is a worse failure than a slower yes, so
nothing here auto-denies on a soft fraud score, only on an unambiguous
integrity violation (the payment is already fully refunded). Everything
that isn't a slam-dunk approve or a slam-dunk deny falls through to a human,
which is deliberately the majority path.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from truegrit_api.services.refund_orchestrator.fraud_signals import RiskAssessment
from truegrit_api.services.refund_orchestrator.reader import RefundContext

# A reasoned starting ceiling, not yet tuned against real outcomes -- see the
# module docstring in fraud_signals.py for how to re-derive it once real
# return data exists.
AUTO_APPROVE_MAX_SCORE: Final = 30


class Decision(StrEnum):
    AUTO_APPROVE = "auto_approve"
    ESCALATE = "escalate"
    AUTO_DENY = "auto_deny"


@dataclass(frozen=True)
class DecisionOutcome:
    decision: Decision
    rationale: str


def decide(ctx: RefundContext, assessment: RiskAssessment) -> DecisionOutcome:
    if assessment.already_refunded:
        return DecisionOutcome(
            decision=Decision.AUTO_DENY,
            rationale=(
                "This order's payment is already fully refunded; there is nothing left to pay out."
            ),
        )

    if not assessment.gateway_refundable:
        return DecisionOutcome(
            decision=Decision.ESCALATE,
            rationale=(
                "This payment method has no automatic gateway refund wired up, so a human"
                " has to arrange it."
            ),
        )

    if ctx.requested_refund_amount_minor is None:
        return DecisionOutcome(
            decision=Decision.ESCALATE,
            rationale="The customer didn't specify a refund amount, so a human needs to set one.",
        )

    if assessment.score <= AUTO_APPROVE_MAX_SCORE:
        return DecisionOutcome(
            decision=Decision.AUTO_APPROVE,
            rationale=(
                f"Risk score {assessment.score} is at or below the auto-approve ceiling of"
                f" {AUTO_APPROVE_MAX_SCORE}"
                + (
                    "."
                    if not assessment.signals
                    else f", with only minor signals ({len(assessment.signals)}) firing."
                )
            ),
        )

    return DecisionOutcome(
        decision=Decision.ESCALATE,
        rationale=(
            f"Risk score {assessment.score} is above the auto-approve ceiling of"
            f" {AUTO_APPROVE_MAX_SCORE} ({len(assessment.signals)} signal(s) fired); a human"
            " should review this one."
        ),
    )

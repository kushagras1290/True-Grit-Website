"""Deterministic, named fraud-risk signals for the refund orchestrator.

Every signal is an independently testable boolean check with a fixed weight
and a plain-language rationale -- no signal is a black box, and the sum is
never a "vibe." Weights and thresholds below are a reasoned starting point,
not yet tuned against real return data: if this pipeline runs for a while and
real outcomes are known (a customer who scored low turned out to be abusive,
one who scored high was legitimate), re-derive these the way
`support_bot/gate.py`'s threshold sweep was re-derived from measured
precision -- don't just leave them as launch guesses forever.

`score_context` never raises and never touches the database; it is pure
function of a `RefundContext`, which is what makes it unit-testable without
any fixtures beyond a dataclass literal.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final

from truegrit_api.services.refund_orchestrator.reader import RefundContext

# Razorpay and Stripe both have a real gateway-refund call wired up
# (`services.orders.refund_via_gateway`) -- Stripe's checkout flow doesn't
# exist yet (`config.py`'s `payment_stripe_visible` stays off until it does),
# so no `payments` row can have provider='stripe' today, but the moment it
# ships this needs no further change on the orchestrator side. PayPal is
# confirmed dead going forward and always escalates, the same as COD.
GATEWAY_REFUNDABLE_PROVIDERS: Final = frozenset({"razorpay", "stripe"})

_EVIDENCE_EXPECTED_REASON_CODES: Final = frozenset(
    {"damaged", "quality_issue", "not_as_described"}
)

# --- Weights (0-100 scale) --------------------------------------------------
# Chosen so no single soft signal alone reaches the escalate threshold
# (decision.py's AUTO_APPROVE ceiling), but two or more compounding does.
WEIGHT_HIGH_REFUND_VELOCITY: Final = 40
WEIGHT_HIGH_LIFETIME_REFUND_RATIO: Final = 35
WEIGHT_NEW_ACCOUNT_HIGH_VALUE: Final = 30
WEIGHT_MISSING_EVIDENCE: Final = 20
WEIGHT_NEAR_FULL_VALUE_REFUND: Final = 15
WEIGHT_MISMATCHED_ADDRESSES: Final = 10

# --- Thresholds --------------------------------------------------------------
HIGH_VELOCITY_THRESHOLD: Final = 3  # return requests in reader.py's 30-day window
HIGH_LIFETIME_RATIO_THRESHOLD: Final = 0.5
HIGH_LIFETIME_RATIO_MIN_ORDERS: Final = 2  # floor so a single order can't trigger it
NEAR_FULL_VALUE_RATIO: Final = 0.95
NEW_ACCOUNT_DAYS: Final = 7
NEW_ACCOUNT_VALUE_THRESHOLD_MINOR: Final = 5_000_00  # ₹5,000


@dataclass(frozen=True)
class SignalHit:
    id: str
    label: str
    weight: int
    rationale: str


@dataclass(frozen=True)
class RiskAssessment:
    score: int
    signals: tuple[SignalHit, ...]
    already_refunded: bool
    gateway_refundable: bool


def _account_age_days(created_at: str | None) -> float | None:
    if not created_at:
        return None
    try:
        created = datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    except ValueError:
        return None
    return (datetime.now(UTC) - created).total_seconds() / 86_400


def score_context(ctx: RefundContext) -> RiskAssessment:
    signals: list[SignalHit] = []

    if ctx.recent_return_count >= HIGH_VELOCITY_THRESHOLD:
        signals.append(
            SignalHit(
                id="HIGH_REFUND_VELOCITY",
                label="High refund velocity",
                weight=WEIGHT_HIGH_REFUND_VELOCITY,
                rationale=(
                    f"{ctx.recent_return_count} return requests from this customer in the"
                    f" last 30 days (threshold {HIGH_VELOCITY_THRESHOLD})."
                ),
            )
        )

    if (
        ctx.lifetime_order_count >= HIGH_LIFETIME_RATIO_MIN_ORDERS
        and ctx.lifetime_paid_minor > 0
        and (ctx.lifetime_refunded_minor / ctx.lifetime_paid_minor) > HIGH_LIFETIME_RATIO_THRESHOLD
    ):
        ratio_pct = round(100 * ctx.lifetime_refunded_minor / ctx.lifetime_paid_minor)
        signals.append(
            SignalHit(
                id="HIGH_LIFETIME_REFUND_RATIO",
                label="High lifetime refund ratio",
                weight=WEIGHT_HIGH_LIFETIME_REFUND_RATIO,
                rationale=(
                    f"{ratio_pct}% of this customer's lifetime spend across"
                    f" {ctx.lifetime_order_count} orders has come back as refunds"
                    f" (threshold {round(HIGH_LIFETIME_RATIO_THRESHOLD * 100)}%)."
                ),
            )
        )

    age_days = _account_age_days(ctx.account_created_at)
    if (
        age_days is not None
        and age_days < NEW_ACCOUNT_DAYS
        and ctx.order_total_minor >= NEW_ACCOUNT_VALUE_THRESHOLD_MINOR
    ):
        signals.append(
            SignalHit(
                id="NEW_ACCOUNT_HIGH_VALUE",
                label="New account, high-value order",
                weight=WEIGHT_NEW_ACCOUNT_HIGH_VALUE,
                rationale=(
                    f"Account is {age_days:.1f} days old (threshold {NEW_ACCOUNT_DAYS}) and the"
                    f" order total is {ctx.order_total_minor} minor units"
                    f" (threshold {NEW_ACCOUNT_VALUE_THRESHOLD_MINOR})."
                ),
            )
        )

    if ctx.reason_code in _EVIDENCE_EXPECTED_REASON_CODES and ctx.evidence_media_count == 0:
        signals.append(
            SignalHit(
                id="MISSING_EVIDENCE",
                label="No evidence attached",
                weight=WEIGHT_MISSING_EVIDENCE,
                rationale=(
                    f"Reason code '{ctx.reason_code}' typically has supporting photos, but no"
                    " evidence was attached to this request."
                ),
            )
        )

    if (
        ctx.requested_refund_amount_minor is not None
        and ctx.order_total_minor > 0
        and (ctx.requested_refund_amount_minor / ctx.order_total_minor) >= NEAR_FULL_VALUE_RATIO
    ):
        signals.append(
            SignalHit(
                id="NEAR_FULL_VALUE_REFUND",
                label="Near-full order value requested",
                weight=WEIGHT_NEAR_FULL_VALUE_REFUND,
                rationale=(
                    f"Requested refund is {ctx.requested_refund_amount_minor} of"
                    f" {ctx.order_total_minor} minor units"
                    f" (>={round(NEAR_FULL_VALUE_RATIO * 100)}% of the order total)."
                ),
            )
        )

    if (
        ctx.billing_address_json
        and ctx.delivery_address_json
        and ctx.billing_address_json != ctx.delivery_address_json
    ):
        signals.append(
            SignalHit(
                id="MISMATCHED_ADDRESSES",
                label="Billing and delivery address differ",
                weight=WEIGHT_MISMATCHED_ADDRESSES,
                rationale="The order's billing and delivery addresses are not the same.",
            )
        )

    score = min(100, sum(signal.weight for signal in signals))

    already_refunded = ctx.payment_status == "refunded" or (
        ctx.payment_amount_minor is not None
        and ctx.already_refunded_minor >= ctx.payment_amount_minor
    )
    gateway_refundable = ctx.payment_provider in GATEWAY_REFUNDABLE_PROVIDERS

    return RiskAssessment(
        score=score,
        signals=tuple(signals),
        already_refunded=already_refunded,
        gateway_refundable=gateway_refundable,
    )

"""Coverage matrix for the refund orchestrator's deterministic fraud signals
and decision bands -- the interview-defensible artifact for this piece: every
signal is exercised in isolation, and the score->band mapping is asserted
explicitly rather than trusted by inspection.

Pure unit tests: `RefundContext` is built as a plain dataclass literal, no
database involved, matching `score_context`/`decide`'s own purity.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta

from truegrit_api.services.refund_orchestrator.decision import (
    AUTO_APPROVE_MAX_SCORE,
    Decision,
    decide,
)
from truegrit_api.services.refund_orchestrator.fraud_signals import (
    HIGH_LIFETIME_RATIO_MIN_ORDERS,
    HIGH_LIFETIME_RATIO_THRESHOLD,
    HIGH_VELOCITY_THRESHOLD,
    NEAR_FULL_VALUE_RATIO,
    NEW_ACCOUNT_DAYS,
    NEW_ACCOUNT_VALUE_THRESHOLD_MINOR,
    score_context,
)
from truegrit_api.services.refund_orchestrator.reader import RefundContext


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _clean_ctx(**overrides: object) -> RefundContext:
    """A return request with no fraud signals of concern: an old account,
    first-ever return, modest partial refund, evidence attached, matching
    billing/delivery addresses, on a fully-refundable Razorpay payment."""
    base = RefundContext(
        return_request_id="ret_test",
        order_id="ord_test",
        customer_user_id="usr_test",
        reason_code="wrong_item",
        evidence_media_count=1,
        requested_refund_amount_minor=10_000,
        order_total_minor=50_000,
        billing_address_json='{"line1": "1 Main St"}',
        delivery_address_json='{"line1": "1 Main St"}',
        payment_provider="razorpay",
        payment_status="paid",
        payment_amount_minor=50_000,
        already_refunded_minor=0,
        account_created_at=_iso(datetime.now(UTC) - timedelta(days=365)),
        recent_return_count=0,
        lifetime_order_count=5,
        lifetime_paid_minor=250_000,
        lifetime_refunded_minor=0,
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_clean_context_has_no_signals_and_zero_score() -> None:
    assessment = score_context(_clean_ctx())
    assert assessment.signals == ()
    assert assessment.score == 0
    assert assessment.already_refunded is False
    assert assessment.gateway_refundable is True


def test_high_refund_velocity_fires_at_threshold() -> None:
    below = score_context(_clean_ctx(recent_return_count=HIGH_VELOCITY_THRESHOLD - 1))
    at = score_context(_clean_ctx(recent_return_count=HIGH_VELOCITY_THRESHOLD))
    assert "HIGH_REFUND_VELOCITY" not in [s.id for s in below.signals]
    assert "HIGH_REFUND_VELOCITY" in [s.id for s in at.signals]


def test_high_lifetime_refund_ratio_needs_the_minimum_order_floor() -> None:
    # A single order refunded in full would trip the ratio, but the floor
    # (HIGH_LIFETIME_RATIO_MIN_ORDERS) exists precisely to stop that.
    one_order = score_context(
        _clean_ctx(
            lifetime_order_count=1,
            lifetime_paid_minor=50_000,
            lifetime_refunded_minor=50_000,
        )
    )
    assert "HIGH_LIFETIME_REFUND_RATIO" not in [s.id for s in one_order.signals]

    enough_orders = score_context(
        _clean_ctx(
            lifetime_order_count=HIGH_LIFETIME_RATIO_MIN_ORDERS,
            lifetime_paid_minor=100_000,
            lifetime_refunded_minor=60_000,  # 60% > 50% threshold
        )
    )
    assert "HIGH_LIFETIME_REFUND_RATIO" in [s.id for s in enough_orders.signals]

    exactly_at_threshold = score_context(
        _clean_ctx(
            lifetime_order_count=HIGH_LIFETIME_RATIO_MIN_ORDERS,
            lifetime_paid_minor=100_000,
            lifetime_refunded_minor=int(100_000 * HIGH_LIFETIME_RATIO_THRESHOLD),
        )
    )
    assert "HIGH_LIFETIME_REFUND_RATIO" not in [s.id for s in exactly_at_threshold.signals]


def test_new_account_high_value_requires_both_conditions() -> None:
    new_but_cheap = score_context(
        _clean_ctx(
            account_created_at=_iso(datetime.now(UTC) - timedelta(days=1)),
            order_total_minor=NEW_ACCOUNT_VALUE_THRESHOLD_MINOR - 1,
        )
    )
    assert "NEW_ACCOUNT_HIGH_VALUE" not in [s.id for s in new_but_cheap.signals]

    old_but_expensive = score_context(
        _clean_ctx(
            account_created_at=_iso(datetime.now(UTC) - timedelta(days=NEW_ACCOUNT_DAYS + 1)),
            order_total_minor=NEW_ACCOUNT_VALUE_THRESHOLD_MINOR * 10,
        )
    )
    assert "NEW_ACCOUNT_HIGH_VALUE" not in [s.id for s in old_but_expensive.signals]

    new_and_expensive = score_context(
        _clean_ctx(
            account_created_at=_iso(datetime.now(UTC) - timedelta(days=1)),
            order_total_minor=NEW_ACCOUNT_VALUE_THRESHOLD_MINOR * 10,
        )
    )
    assert "NEW_ACCOUNT_HIGH_VALUE" in [s.id for s in new_and_expensive.signals]


def test_missing_evidence_only_matters_for_evidence_reason_codes() -> None:
    no_evidence_wrong_item = score_context(
        _clean_ctx(reason_code="wrong_item", evidence_media_count=0)
    )
    assert "MISSING_EVIDENCE" not in [s.id for s in no_evidence_wrong_item.signals]

    no_evidence_damaged = score_context(_clean_ctx(reason_code="damaged", evidence_media_count=0))
    assert "MISSING_EVIDENCE" in [s.id for s in no_evidence_damaged.signals]

    with_evidence_damaged = score_context(_clean_ctx(reason_code="damaged", evidence_media_count=2))
    assert "MISSING_EVIDENCE" not in [s.id for s in with_evidence_damaged.signals]


def test_near_full_value_refund_threshold() -> None:
    just_under = score_context(
        _clean_ctx(
            order_total_minor=100_000,
            requested_refund_amount_minor=int(100_000 * NEAR_FULL_VALUE_RATIO) - 1,
        )
    )
    assert "NEAR_FULL_VALUE_REFUND" not in [s.id for s in just_under.signals]

    at_threshold = score_context(
        _clean_ctx(
            order_total_minor=100_000,
            requested_refund_amount_minor=int(100_000 * NEAR_FULL_VALUE_RATIO),
        )
    )
    assert "NEAR_FULL_VALUE_REFUND" in [s.id for s in at_threshold.signals]


def test_mismatched_addresses_signal() -> None:
    mismatched = score_context(
        _clean_ctx(
            billing_address_json='{"line1": "1 Main St"}',
            delivery_address_json='{"line1": "2 Other Ave"}',
        )
    )
    assert "MISMATCHED_ADDRESSES" in [s.id for s in mismatched.signals]


def test_already_refunded_flag() -> None:
    fully_refunded_status = score_context(_clean_ctx(payment_status="refunded"))
    assert fully_refunded_status.already_refunded is True

    amount_exhausted = score_context(
        _clean_ctx(payment_amount_minor=50_000, already_refunded_minor=50_000)
    )
    assert amount_exhausted.already_refunded is True

    partially_refunded = score_context(
        _clean_ctx(
            payment_status="partially_refunded",
            payment_amount_minor=50_000,
            already_refunded_minor=10_000,
        )
    )
    assert partially_refunded.already_refunded is False


def test_gateway_refundable_for_razorpay_and_stripe_only() -> None:
    assert score_context(_clean_ctx(payment_provider="razorpay")).gateway_refundable is True
    # Stripe checkout doesn't exist yet, but the refund path is ready for it --
    # see services.payments.refund_stripe_payment and orders.refund_via_gateway.
    assert score_context(_clean_ctx(payment_provider="stripe")).gateway_refundable is True
    assert score_context(_clean_ctx(payment_provider="paypal")).gateway_refundable is False
    assert score_context(_clean_ctx(payment_provider="cod")).gateway_refundable is False
    assert score_context(_clean_ctx(payment_provider=None)).gateway_refundable is False


def test_multiple_signals_compound_and_cap_at_100() -> None:
    high_risk = score_context(
        _clean_ctx(
            recent_return_count=HIGH_VELOCITY_THRESHOLD,
            account_created_at=_iso(datetime.now(UTC) - timedelta(days=1)),
            order_total_minor=NEW_ACCOUNT_VALUE_THRESHOLD_MINOR * 10,
            reason_code="damaged",
            evidence_media_count=0,
            requested_refund_amount_minor=int(
                NEW_ACCOUNT_VALUE_THRESHOLD_MINOR * 10 * NEAR_FULL_VALUE_RATIO
            ),
            billing_address_json='{"line1": "1 Main St"}',
            delivery_address_json='{"line1": "2 Other Ave"}',
            lifetime_order_count=HIGH_LIFETIME_RATIO_MIN_ORDERS,
            lifetime_paid_minor=100_000,
            lifetime_refunded_minor=90_000,
        )
    )
    assert len(high_risk.signals) == 6
    assert high_risk.score == 100  # sum of all six weights exceeds 100, clamped


# --- Decision bands ----------------------------------------------------------


def test_decide_auto_denies_only_when_already_refunded() -> None:
    ctx = _clean_ctx(payment_status="refunded")
    outcome = decide(ctx, score_context(ctx))
    assert outcome.decision == Decision.AUTO_DENY


def test_decide_escalates_non_gateway_providers() -> None:
    for provider in ("cod", "paypal", None):
        ctx = _clean_ctx(payment_provider=provider)
        outcome = decide(ctx, score_context(ctx))
        assert outcome.decision == Decision.ESCALATE, provider


def test_decide_escalates_when_no_requested_amount() -> None:
    ctx = _clean_ctx(requested_refund_amount_minor=None)
    outcome = decide(ctx, score_context(ctx))
    assert outcome.decision == Decision.ESCALATE


def test_decide_auto_approves_low_risk_within_ceiling() -> None:
    ctx = _clean_ctx()
    outcome = decide(ctx, score_context(ctx))
    assert outcome.decision == Decision.AUTO_APPROVE


def test_decide_escalates_above_the_auto_approve_ceiling() -> None:
    ctx = _clean_ctx(
        recent_return_count=HIGH_VELOCITY_THRESHOLD,
        account_created_at=_iso(datetime.now(UTC) - timedelta(days=1)),
        order_total_minor=NEW_ACCOUNT_VALUE_THRESHOLD_MINOR * 10,
        requested_refund_amount_minor=10_000,
    )
    assessment = score_context(ctx)
    assert assessment.score > AUTO_APPROVE_MAX_SCORE
    outcome = decide(ctx, assessment)
    assert outcome.decision == Decision.ESCALATE

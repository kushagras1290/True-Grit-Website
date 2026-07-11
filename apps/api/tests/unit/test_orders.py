import pytest

from truegrit_api.domain.orders import (
    DELIVERY_TRANSITIONS,
    FULFILMENT_TRANSITIONS,
    ORDER_TRANSITIONS,
    PAYMENT_TRANSITIONS,
    assert_status_transition,
)
from truegrit_api.errors import ConflictError


def test_order_happy_path():
    assert_status_transition("order", ORDER_TRANSITIONS, "pending_payment", "confirmed")
    assert_status_transition("order", ORDER_TRANSITIONS, "confirmed", "processing")
    assert_status_transition("order", ORDER_TRANSITIONS, "processing", "completed")


def test_terminal_states_are_terminal():
    for terminal in ("completed", "cancelled"):
        with pytest.raises(ConflictError):
            assert_status_transition("order", ORDER_TRANSITIONS, terminal, "confirmed")


def test_payment_failure_can_retry():
    assert_status_transition("payment", PAYMENT_TRANSITIONS, "failed", "pending")
    with pytest.raises(ConflictError):
        assert_status_transition("payment", PAYMENT_TRANSITIONS, "refunded", "paid")


def test_fulfilment_never_skips_quality_check():
    with pytest.raises(ConflictError):
        assert_status_transition("fulfilment", FULFILMENT_TRANSITIONS, "packed", "dispatched")
    assert_status_transition("fulfilment", FULFILMENT_TRANSITIONS, "packed", "quality_checked")
    assert_status_transition("fulfilment", FULFILMENT_TRANSITIONS, "quality_checked", "dispatched")


def test_delivery_failed_can_recover():
    assert_status_transition("delivery", DELIVERY_TRANSITIONS, "delivery_failed", "in_transit")


def test_unknown_status_rejected():
    with pytest.raises(ConflictError):
        assert_status_transition("order", ORDER_TRANSITIONS, "shipped", "completed")

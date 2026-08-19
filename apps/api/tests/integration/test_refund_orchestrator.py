"""End-to-end coverage for the refund orchestrator pipeline and the real-money
bug fix it depends on (`resolve_return_request` now actually calls the
payment gateway instead of only writing a ledger row).

Uses the real seeded order `ord_1001` (customer `usr_cust_riya`, confirmed,
total 94800 minor units) from `database/seeds/development.sql`, the same
fixture `test_admin_management.py`'s refund tests build on.
"""

from __future__ import annotations

import asyncio
import json

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.feature_settings import update_storefront_settings
from truegrit_api.services.refund_orchestrator.executor import (
    SYSTEM_ACTOR_USER_ID,
    run_refund_orchestrator,
)
from truegrit_api.services.returns import (
    create_return_request,
    decide_return_request,
    resolve_return_request,
)
from truegrit_api.util.ids import new_id

_ORDER_ID = "ord_1001"
_CUSTOMER_ID = "usr_cust_riya"
_ORDER_TOTAL_MINOR = 94_800


def _staff_principal() -> Principal:
    return Principal(
        user_id="usr_admin",
        display_name="Owner",
        email="owner@truegrit.test",
        user_type="staff",
        permissions=frozenset({"returns.view", "returns.manage", "orders.refund"}),
    )


def _customer_principal() -> Principal:
    return Principal(
        user_id=_CUSTOMER_ID,
        display_name="Riya Nair",
        email="riya@example.test",
        user_type="customer",
    )


def _seed_paid_razorpay_payment(
    db: SQLiteDatabase, order_id: str, amount_minor: int, *, status: str = "paid"
) -> None:
    now = "2026-07-15T00:00:00Z"
    db._conn.execute(
        "INSERT INTO payments"
        " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
        "  status, created_at, updated_at)"
        " VALUES (?, ?, 'razorpay', 'pay_test123', ?, 'INR', ?, ?, ?)",
        (f"pay_{order_id}", order_id, amount_minor, status, now, now),
    )
    db._conn.commit()


def _seed_return_request(
    db: SQLiteDatabase,
    *,
    return_id: str,
    order_id: str = _ORDER_ID,
    customer_user_id: str = _CUSTOMER_ID,
    reason_code: str = "wrong_item",
    evidence_media_ids: list[str] | None = None,
    requested_refund_amount_minor: int | None = 10_000,
    status: str = "requested",
) -> None:
    now = "2026-08-19T00:00:00Z"
    db._conn.execute(
        "INSERT INTO return_requests"
        " (id, order_id, order_item_id, customer_user_id, reason_code, description,"
        "  evidence_media_ids_json, status, requested_refund_amount_minor,"
        "  requested_at, created_at, updated_at)"
        " VALUES (?, ?, NULL, ?, ?, 'Wrong item received in this order.', ?, ?, ?, ?, ?, ?)",
        (
            return_id,
            order_id,
            customer_user_id,
            reason_code,
            json.dumps(evidence_media_ids or []),
            status,
            requested_refund_amount_minor,
            now,
            now,
            now,
        ),
    )
    db._conn.commit()


async def _fake_refund(settings, *, payment_id, amount_minor, idempotency_key):
    assert payment_id == "pay_test123"
    return "rfnd_test123"


def test_auto_approve_calls_gateway_and_notifies(db: SQLiteDatabase, monkeypatch) -> None:
    async def scenario() -> None:
        monkeypatch.setattr("truegrit_api.services.orders.refund_razorpay_payment", _fake_refund)
        _seed_paid_razorpay_payment(db, _ORDER_ID, _ORDER_TOTAL_MINOR)
        _seed_return_request(
            db,
            return_id="ret_auto_approve",
            evidence_media_ids=["med_1"],
            requested_refund_amount_minor=10_000,
        )

        outcome = await run_refund_orchestrator(db, "ret_auto_approve")

        assert outcome.decision.value == "auto_approve"

        row = await db.fetch_one(
            "SELECT status, resolution_type, resolution_amount_minor, resolved_by"
            " FROM return_requests WHERE id = ?",
            ("ret_auto_approve",),
        )
        assert row is not None
        assert row["status"] == "refunded"
        assert row["resolution_type"] == "refund"
        assert row["resolution_amount_minor"] == 10_000
        assert row["resolved_by"] == SYSTEM_ACTOR_USER_ID

        payment = await db.fetch_one("SELECT status FROM payments WHERE order_id = ?", (_ORDER_ID,))
        assert payment is not None
        assert payment["status"] == "partially_refunded"

        event = await db.fetch_one(
            "SELECT pe.amount_minor FROM payment_events pe"
            " JOIN payments p ON p.id = pe.payment_id"
            " WHERE p.order_id = ? AND pe.event_type = 'refund'",
            (_ORDER_ID,),
        )
        assert event is not None
        assert event["amount_minor"] == 10_000

        ledger = await db.fetch_one(
            "SELECT amount_minor FROM order_adjustments"
            " WHERE order_id = ? AND adjustment_type = 'refund'",
            (_ORDER_ID,),
        )
        assert ledger is not None
        assert ledger["amount_minor"] == -10_000

        audit = await db.fetch_one(
            "SELECT id FROM audit_logs WHERE entity_id = ? AND action = 'order.refunded'",
            (_ORDER_ID,),
        )
        assert audit is not None

        run = await db.fetch_one(
            "SELECT decision, risk_score FROM refund_orchestrator_runs WHERE return_request_id = ?",
            ("ret_auto_approve",),
        )
        assert run is not None
        assert run["decision"] == "auto_approve"

        outbox = await db.fetch_one(
            "SELECT category FROM outbox_events WHERE category = 'refund_orchestrator'"
        )
        assert outbox is not None

    asyncio.run(scenario())


def test_escalate_leaves_under_review_and_moves_no_money(db: SQLiteDatabase, monkeypatch) -> None:
    async def scenario() -> None:
        monkeypatch.setattr("truegrit_api.services.orders.refund_razorpay_payment", _fake_refund)
        _seed_paid_razorpay_payment(db, _ORDER_ID, _ORDER_TOTAL_MINOR)
        # No requested amount -- decision.py always escalates this, since it
        # cannot safely determine a refund amount on its own.
        _seed_return_request(db, return_id="ret_escalate", requested_refund_amount_minor=None)

        outcome = await run_refund_orchestrator(db, "ret_escalate")

        assert outcome.decision.value == "escalate"

        row = await db.fetch_one(
            "SELECT status FROM return_requests WHERE id = ?", ("ret_escalate",)
        )
        assert row is not None
        assert row["status"] == "under_review"

        payment = await db.fetch_one("SELECT status FROM payments WHERE order_id = ?", (_ORDER_ID,))
        assert payment is not None
        assert payment["status"] == "paid"  # untouched

        run = await db.fetch_one(
            "SELECT decision FROM refund_orchestrator_runs WHERE return_request_id = ?",
            ("ret_escalate",),
        )
        assert run is not None
        assert run["decision"] == "escalate"

        # Escalation changes nothing customer-visible, so no email is queued.
        outbox = await db.fetch_one(
            "SELECT id FROM outbox_events"
            " WHERE aggregate_id = ? AND category = 'refund_orchestrator'",
            ("ret_escalate",),
        )
        assert outbox is None

    asyncio.run(scenario())


def test_auto_deny_when_payment_already_fully_refunded(db: SQLiteDatabase) -> None:
    async def scenario() -> None:
        _seed_paid_razorpay_payment(db, _ORDER_ID, _ORDER_TOTAL_MINOR, status="refunded")
        _seed_return_request(db, return_id="ret_auto_deny")

        outcome = await run_refund_orchestrator(db, "ret_auto_deny")

        assert outcome.decision.value == "auto_deny"

        row = await db.fetch_one(
            "SELECT status FROM return_requests WHERE id = ?", ("ret_auto_deny",)
        )
        assert row is not None
        assert row["status"] == "rejected"

        outbox = await db.fetch_one(
            "SELECT id FROM outbox_events"
            " WHERE aggregate_id = ? AND category = 'refund_orchestrator'",
            ("ret_auto_deny",),
        )
        assert outbox is not None  # denial is still communicated to the customer

    asyncio.run(scenario())


def test_cod_orders_always_escalate_regardless_of_risk_score(db: SQLiteDatabase) -> None:
    async def scenario() -> None:
        now = "2026-07-15T00:00:00Z"
        db._conn.execute(
            "INSERT INTO payments"
            " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
            "  status, created_at, updated_at)"
            " VALUES ('pay_cod_1001', ?, 'cod', NULL, ?, 'INR', 'paid', ?, ?)",
            (_ORDER_ID, _ORDER_TOTAL_MINOR, now, now),
        )
        db._conn.commit()
        _seed_return_request(
            db,
            return_id="ret_cod",
            evidence_media_ids=["med_1"],
            requested_refund_amount_minor=1_000,
        )

        outcome = await run_refund_orchestrator(db, "ret_cod")

        assert outcome.decision.value == "escalate"

    asyncio.run(scenario())


def test_create_return_request_enqueues_evaluation_only_when_enabled(db: SQLiteDatabase) -> None:
    async def scenario() -> None:
        result = await create_return_request(
            db,
            _customer_principal(),
            new_id("req"),
            order_id=_ORDER_ID,
            order_item_id=None,
            reason_code="wrong_item",
            description="Wrong item received, needs review.",
            requested_refund_amount_minor=5_000,
        )
        pending_before = await db.fetch_one(
            "SELECT id FROM outbox_events WHERE event_type = 'refund_orchestrator.evaluate.v1'"
            " AND aggregate_id = ?",
            (result["id"],),
        )
        assert pending_before is None  # feature toggle is off by default

        # Reject the first request so the order is eligible for a new one --
        # `create_return_request` refuses a second open request per order/item.
        await decide_return_request(
            db, _staff_principal(), new_id("req"), result["id"], decision="rejected"
        )

        await update_storefront_settings(
            db, _staff_principal(), new_id("req"), updates={"refund_orchestrator": True}
        )

        result2 = await create_return_request(
            db,
            _customer_principal(),
            new_id("req"),
            order_id=_ORDER_ID,
            order_item_id=None,
            reason_code="wrong_item",
            description="Second request after enabling the orchestrator.",
            requested_refund_amount_minor=5_000,
        )
        pending_after = await db.fetch_one(
            "SELECT id FROM outbox_events WHERE event_type = 'refund_orchestrator.evaluate.v1'"
            " AND aggregate_id = ?",
            (result2["id"],),
        )
        assert pending_after is not None

    asyncio.run(scenario())


def test_manual_resolve_as_refund_now_actually_calls_the_gateway(
    db: SQLiteDatabase, monkeypatch
) -> None:
    """Regression test for the bug this feature closes: resolving an approved
    return as 'refund' through the ordinary staff flow used to only write an
    `order_adjustments` ledger row and never call Razorpay. It must now go
    through the same gateway path `issue_refund` uses."""

    async def scenario() -> None:
        monkeypatch.setattr("truegrit_api.services.orders.refund_razorpay_payment", _fake_refund)
        _seed_paid_razorpay_payment(db, _ORDER_ID, _ORDER_TOTAL_MINOR)
        _seed_return_request(db, return_id="ret_manual", requested_refund_amount_minor=20_000)
        actor = _staff_principal()
        await decide_return_request(db, actor, new_id("req"), "ret_manual", decision="approved")

        await resolve_return_request(
            db,
            actor,
            new_id("req"),
            "ret_manual",
            resolution_type="refund",
            resolution_amount_minor=20_000,
            resolution_notes="Approved after phone call with customer.",
        )

        payment = await db.fetch_one("SELECT status FROM payments WHERE order_id = ?", (_ORDER_ID,))
        assert payment is not None
        assert payment["status"] == "partially_refunded"

        event = await db.fetch_one(
            "SELECT pe.amount_minor FROM payment_events pe"
            " JOIN payments p ON p.id = pe.payment_id"
            " WHERE p.order_id = ? AND pe.event_type = 'refund'",
            (_ORDER_ID,),
        )
        assert event is not None
        assert event["amount_minor"] == 20_000

        audit = await db.fetch_one(
            "SELECT id FROM audit_logs WHERE entity_id = ? AND action = 'order.refunded'",
            (_ORDER_ID,),
        )
        assert audit is not None

    asyncio.run(scenario())

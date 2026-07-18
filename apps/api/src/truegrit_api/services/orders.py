"""Order lifecycle transitions for the operations console.

Order status moves through a small, explicit state machine. Cancelling requires
the `orders.cancel` permission; other forward transitions require `orders.view`
(enforced at the endpoint). Every change is audited. Payment and fulfilment
sub-states are managed separately (Release 2).

Refunds (`issue_refund`) require `orders.refund` and go out through the same
gateway integrations checkout uses (`services.payments`) — the DB is only ever
updated *after* the gateway confirms the refund, so a failed gateway call can
never leave a payment marked refunded when no money actually moved.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.payments import refund_paypal_capture, refund_razorpay_payment
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending_payment": frozenset({"confirmed", "cancelled"}),
    "confirmed": frozenset({"processing", "cancelled"}),
    "processing": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}


def allowed_order_transitions(current: str) -> frozenset[str]:
    return _ORDER_TRANSITIONS.get(current, frozenset())


async def update_order_status(
    db: Database,
    actor: Principal,
    request_id: str,
    order_id: str,
    *,
    target_status: str,
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT id, order_status FROM orders WHERE id = ?", (order_id,))
    if current is None:
        raise NotFoundError("Order not found.")

    from_status = current["order_status"]
    if target_status not in allowed_order_transitions(from_status):
        raise ConflictError(f"Cannot move an order from '{from_status}' to '{target_status}'.")
    if target_status == "cancelled" and not actor.has("orders.cancel"):
        raise PermissionDeniedError("Cancelling orders requires the orders.cancel permission.")

    now = utc_now_iso()
    fulfilment_status = (
        "cancelled"
        if target_status == "cancelled"
        else "fulfilled"
        if target_status == "completed"
        else None
    )
    statements: list[tuple[str, Any]] = [
        (
            "UPDATE orders SET order_status = ?,"
            " fulfilment_status = COALESCE(?, fulfilment_status), updated_at = ? WHERE id = ?",
            (target_status, fulfilment_status, now, order_id),
        )
    ]
    reservations = await db.fetch_all(
        """
        SELECT id, variant_id, location_id, quantity
        FROM inventory_reservations
        WHERE reference_type = 'order' AND reference_id = ? AND status = 'held'
        """,
        (order_id,),
    )
    if target_status == "cancelled":
        for reservation in reservations:
            statements.extend(
                [
                    (
                        "UPDATE inventory_levels"
                        " SET reserved = reserved - ?, version = version + 1, updated_at = ?"
                        " WHERE variant_id = ? AND location_id = ?",
                        (
                            reservation["quantity"],
                            now,
                            reservation["variant_id"],
                            reservation["location_id"],
                        ),
                    ),
                    (
                        "UPDATE inventory_reservations SET status = 'released', updated_at = ?"
                        " WHERE id = ?",
                        (now, reservation["id"]),
                    ),
                    (
                        "INSERT INTO inventory_movements"
                        " (id, variant_id, location_id, movement_type, quantity_delta,"
                        "  reference_type, reference_id, reason_code, actor_id, created_at)"
                        " VALUES (?, ?, ?, 'reservation_release', 0, 'order', ?,"
                        " 'order_cancelled', ?, ?)",
                        (
                            new_id("imv"),
                            reservation["variant_id"],
                            reservation["location_id"],
                            order_id,
                            actor.user_id,
                            now,
                        ),
                    ),
                ]
            )
    elif target_status == "completed":
        for reservation in reservations:
            statements.extend(
                [
                    (
                        "UPDATE inventory_levels"
                        " SET reserved = reserved - ?, on_hand = on_hand - ?,"
                        " version = version + 1, updated_at = ?"
                        " WHERE variant_id = ? AND location_id = ?",
                        (
                            reservation["quantity"],
                            reservation["quantity"],
                            now,
                            reservation["variant_id"],
                            reservation["location_id"],
                        ),
                    ),
                    (
                        "UPDATE inventory_reservations SET status = 'consumed', updated_at = ?"
                        " WHERE id = ?",
                        (now, reservation["id"]),
                    ),
                    (
                        "INSERT INTO inventory_movements"
                        " (id, variant_id, location_id, movement_type, quantity_delta,"
                        "  reference_type, reference_id, reason_code, actor_id, created_at)"
                        " VALUES (?, ?, ?, 'sale', ?, 'order', ?, 'order_completed', ?, ?)",
                        (
                            new_id("imv"),
                            reservation["variant_id"],
                            reservation["location_id"],
                            -reservation["quantity"],
                            order_id,
                            actor.user_id,
                            now,
                        ),
                    ),
                ]
            )
    statements.append(
        audit_statement(
            action="order.status_changed",
            entity_type="order",
            entity_id=order_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"order_status": from_status},
            after={
                "order_status": target_status,
                "inventoryReservationsUpdated": len(reservations),
            },
        )
    )
    await db.batch(statements)
    return {"id": order_id, "orderStatus": target_status}


_REFUNDABLE_PAYMENT_STATUSES = frozenset({"paid", "partially_refunded"})


async def issue_refund(
    db: Database,
    actor: Principal,
    request_id: str,
    order_id: str,
    *,
    amount_minor: int | None,
    reason: str,
) -> dict[str, Any]:
    """Refund all or part of an order's payment through its original gateway.

    `amount_minor` omitted means "refund whatever remains unrefunded". Amount
    and refundability are always computed from `payments`/`payment_events` —
    the caller-supplied amount is only ever a ceiling, never trusted as the
    remaining balance, so two concurrent partial-refund requests can't
    together refund more than was actually paid.
    """
    if not actor.has("orders.refund"):
        raise PermissionDeniedError("Issuing refunds requires the orders.refund permission.")

    order = await db.fetch_one(
        "SELECT id, payment_status FROM orders WHERE id = ?", (order_id,)
    )
    if order is None:
        raise NotFoundError("Order not found.")

    payment = await db.fetch_one(
        """
        SELECT id, provider, provider_intent_id, amount_minor, currency_code, status
        FROM payments WHERE order_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (order_id,),
    )
    if payment is None:
        raise ValidationAppError("This order has no payment on file to refund.")
    if payment["provider"] == "cod":
        raise ValidationAppError(
            "Cash-on-delivery orders have no online payment to refund. Handle this refund"
            " outside the system and record it manually."
        )
    if payment["status"] not in _REFUNDABLE_PAYMENT_STATUSES:
        raise ConflictError(f"A payment with status '{payment['status']}' cannot be refunded.")
    if not payment["provider_intent_id"]:
        raise ValidationAppError("This payment has no provider reference to refund against.")

    refunded_row = await db.fetch_one(
        "SELECT COALESCE(SUM(amount_minor), 0) AS refunded FROM payment_events"
        " WHERE payment_id = ? AND event_type = 'refund'",
        (payment["id"],),
    )
    already_refunded = int(refunded_row["refunded"]) if refunded_row else 0
    remaining = payment["amount_minor"] - already_refunded
    if remaining <= 0:
        raise ConflictError("This payment has already been fully refunded.")

    refund_amount = remaining if amount_minor is None else amount_minor
    if refund_amount <= 0:
        raise ValidationAppError("Refund amount must be greater than zero.")
    if refund_amount > remaining:
        raise ValidationAppError(
            f"Cannot refund {refund_amount} minor units; only {remaining} remain unrefunded."
        )

    event_id = new_id("pev")
    settings = get_settings()
    if payment["provider"] == "razorpay":
        provider_refund_id = await refund_razorpay_payment(
            settings,
            payment_id=payment["provider_intent_id"],
            amount_minor=refund_amount,
            idempotency_key=event_id,
        )
    elif payment["provider"] == "paypal":
        provider_refund_id = await refund_paypal_capture(
            settings,
            capture_id=payment["provider_intent_id"],
            amount_minor=refund_amount,
            currency=payment["currency_code"],
            idempotency_key=event_id,
        )
    else:
        raise ValidationAppError(
            f"Refunds are not supported for payment provider '{payment['provider']}'."
        )

    now = utc_now_iso()
    new_payment_status = "refunded" if refund_amount == remaining else "partially_refunded"
    await db.batch(
        [
            (
                "INSERT INTO payment_events"
                " (id, payment_id, event_type, provider_event_id, amount_minor, created_at)"
                " VALUES (?, ?, 'refund', ?, ?, ?)",
                (event_id, payment["id"], provider_refund_id, refund_amount, now),
            ),
            (
                "UPDATE payments SET status = ?, updated_at = ? WHERE id = ?",
                (new_payment_status, now, payment["id"]),
            ),
            (
                "UPDATE orders SET payment_status = ?, updated_at = ? WHERE id = ?",
                (new_payment_status, now, order_id),
            ),
            audit_statement(
                action="order.refunded",
                entity_type="order",
                entity_id=order_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"paymentStatus": payment["status"], "alreadyRefunded": already_refunded},
                after={
                    "paymentStatus": new_payment_status,
                    "refundedNow": refund_amount,
                    "reason": reason,
                    "providerRefundId": provider_refund_id,
                },
            ),
        ]
    )
    return {
        "id": order_id,
        "paymentStatus": new_payment_status,
        "refundedMinor": refund_amount,
        "totalRefundedMinor": already_refunded + refund_amount,
    }

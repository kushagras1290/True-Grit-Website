"""Order lifecycle transitions for the operations console.

Order status moves through a small, explicit state machine. Cancelling requires
the `orders.cancel` permission; other forward transitions require `orders.view`
(enforced at the endpoint). Every change is audited. Payment and fulfilment
sub-states are managed separately (Release 2).
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, PermissionDeniedError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
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

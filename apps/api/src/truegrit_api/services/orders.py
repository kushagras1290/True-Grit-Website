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
    await db.batch(
        [
            (
                "UPDATE orders SET order_status = ?, updated_at = ? WHERE id = ?",
                (target_status, now, order_id),
            ),
            audit_statement(
                action="order.status_changed",
                entity_type="order",
                entity_id=order_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"order_status": from_status},
                after={"order_status": target_status},
            ),
        ]
    )
    return {"id": order_id, "orderStatus": target_status}

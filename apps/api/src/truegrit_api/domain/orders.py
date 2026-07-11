"""Order, payment, fulfilment, and delivery state machines.

Explicit transition maps only — no endpoint sets an arbitrary status. Each axis is
independent; overloading one status field for editorial, commercial, and inventory
state is forbidden by design.
"""

from __future__ import annotations

from truegrit_api.errors import ConflictError

ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    "pending_payment": frozenset({"confirmed", "cancelled"}),
    "confirmed": frozenset({"processing", "cancelled"}),
    "processing": frozenset({"completed", "cancelled"}),
    "completed": frozenset(),
    "cancelled": frozenset(),
}

PAYMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "not_required": frozenset(),
    "pending": frozenset({"authorized", "paid", "failed"}),
    "authorized": frozenset({"paid", "failed"}),
    "paid": frozenset({"partially_refunded", "refunded"}),
    "partially_refunded": frozenset({"refunded", "partially_refunded"}),
    "refunded": frozenset(),
    "failed": frozenset({"pending"}),
}

FULFILMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    "unfulfilled": frozenset({"reserved", "cancelled"}),
    "reserved": frozenset({"picking", "cancelled"}),
    "picking": frozenset({"packed", "cancelled"}),
    "packed": frozenset({"quality_checked", "cancelled"}),
    "quality_checked": frozenset({"dispatched"}),
    "dispatched": frozenset({"partially_fulfilled", "fulfilled"}),
    "partially_fulfilled": frozenset({"fulfilled"}),
    "fulfilled": frozenset(),
    "cancelled": frozenset(),
}

DELIVERY_TRANSITIONS: dict[str, frozenset[str]] = {
    "not_ready": frozenset({"awaiting_carrier"}),
    "awaiting_carrier": frozenset({"in_transit"}),
    "in_transit": frozenset({"out_for_delivery", "delivery_failed"}),
    "out_for_delivery": frozenset({"delivered", "delivery_failed"}),
    "delivered": frozenset({"returned"}),
    "delivery_failed": frozenset({"in_transit", "returned"}),
    "returned": frozenset(),
}


def assert_status_transition(
    axis: str, transitions: dict[str, frozenset[str]], current: str, target: str
) -> None:
    allowed = transitions.get(current)
    if allowed is None:
        raise ConflictError(f"Unknown {axis} status '{current}'.")
    if target not in transitions:
        raise ConflictError(f"Unknown {axis} status '{target}'.")
    if target not in allowed:
        raise ConflictError(f"{axis} status cannot move from '{current}' to '{target}'.")

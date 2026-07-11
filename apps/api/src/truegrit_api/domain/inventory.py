"""Inventory rules.

`available` is always derived (on_hand - reserved) and never stored editable.
Reservation uses a conditional update; the decision logic here is the pure rule
the SQL enforces, so both are tested against the same properties.
"""

from __future__ import annotations

from dataclasses import dataclass

from truegrit_api.errors import ValidationAppError

MOVEMENT_TYPES = frozenset(
    {
        "receipt",
        "sale",
        "reservation",
        "reservation_release",
        "shipment",
        "return",
        "manual_adjustment",
        "write_off",
        "correction",
    }
)

# Movements that must reduce stock (negative delta) or add stock (positive delta).
_NEGATIVE_ONLY = frozenset({"sale", "shipment", "write_off"})
_POSITIVE_ONLY = frozenset({"receipt", "return"})


@dataclass(frozen=True)
class InventoryLevel:
    on_hand: int
    reserved: int

    @property
    def available(self) -> int:
        return self.on_hand - self.reserved


def can_reserve(level: InventoryLevel, quantity: int) -> bool:
    """Mirror of the conditional SQL: (on_hand - reserved) >= quantity."""
    if quantity <= 0:
        raise ValidationAppError("Reservation quantity must be positive.")
    return level.available >= quantity


def reserve(level: InventoryLevel, quantity: int) -> InventoryLevel:
    if not can_reserve(level, quantity):
        raise ValidationAppError(
            "Insufficient stock to reserve.", details={"available": level.available}
        )
    return InventoryLevel(on_hand=level.on_hand, reserved=level.reserved + quantity)


def release(level: InventoryLevel, quantity: int) -> InventoryLevel:
    if quantity <= 0:
        raise ValidationAppError("Release quantity must be positive.")
    if quantity > level.reserved:
        raise ValidationAppError("Cannot release more than is reserved.")
    return InventoryLevel(on_hand=level.on_hand, reserved=level.reserved - quantity)


def validate_movement(movement_type: str, quantity_delta: int) -> None:
    if movement_type not in MOVEMENT_TYPES:
        raise ValidationAppError(f"Unknown movement type '{movement_type}'.")
    if quantity_delta == 0:
        raise ValidationAppError("Movement delta cannot be zero.")
    if movement_type in _NEGATIVE_ONLY and quantity_delta > 0:
        raise ValidationAppError(f"'{movement_type}' must reduce stock.")
    if movement_type in _POSITIVE_ONLY and quantity_delta < 0:
        raise ValidationAppError(f"'{movement_type}' must add stock.")


def availability_label(level: InventoryLevel, reorder_threshold: int) -> str:
    if level.available <= 0:
        return "out_of_stock"
    if level.available <= reorder_threshold:
        return "low_stock"
    return "in_stock"

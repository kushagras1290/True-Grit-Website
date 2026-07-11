"""Integer minor-unit money (ADR-006). ₹899.00 == 89900 INR paise.

Floating point never touches money. Percentages are basis points (10000 = 100%).
"""

from __future__ import annotations

from truegrit_api.errors import ValidationAppError

MAX_AMOUNT_MINOR = 10_000_000_000  # ₹100 crore guardrail


def validate_amount(amount_minor: int) -> int:
    if isinstance(amount_minor, bool) or not isinstance(amount_minor, int):
        raise ValidationAppError("Money amounts must be integers of minor units.")
    if amount_minor < 0:
        raise ValidationAppError("Money amounts cannot be negative.")
    if amount_minor > MAX_AMOUNT_MINOR:
        raise ValidationAppError("Money amount exceeds the supported range.")
    return amount_minor


def basis_points_discount(
    amount_minor: int, basis_points: int, maximum_discount_minor: int | None = None
) -> int:
    """Discount for a percentage expressed in basis points, rounded down, capped.

    The result never exceeds the eligible amount, so totals cannot go negative.
    """
    validate_amount(amount_minor)
    if not isinstance(basis_points, int) or not 0 <= basis_points <= 10_000:
        raise ValidationAppError("Percentage must be 0-10000 basis points.")
    discount = (amount_minor * basis_points) // 10_000
    if maximum_discount_minor is not None:
        discount = min(discount, validate_amount(maximum_discount_minor))
    return min(discount, amount_minor)


def apply_discount(amount_minor: int, discount_minor: int) -> int:
    """Subtract a fixed discount; the result is floored at zero, never negative."""
    validate_amount(amount_minor)
    validate_amount(discount_minor)
    return max(amount_minor - discount_minor, 0)


def line_total(unit_amount_minor: int, quantity: int) -> int:
    validate_amount(unit_amount_minor)
    if not isinstance(quantity, int) or quantity <= 0:
        raise ValidationAppError("Quantity must be a positive integer.")
    total = unit_amount_minor * quantity
    validate_amount(total)
    return total


def effective_unit_price(list_amount_minor: int, sale_amount_minor: int | None) -> int:
    """Resolve the effective price: an active sale price wins, never exceeding list."""
    validate_amount(list_amount_minor)
    if sale_amount_minor is None:
        return list_amount_minor
    validate_amount(sale_amount_minor)
    if sale_amount_minor > list_amount_minor:
        raise ValidationAppError("Sale price cannot exceed list price.")
    return sale_amount_minor

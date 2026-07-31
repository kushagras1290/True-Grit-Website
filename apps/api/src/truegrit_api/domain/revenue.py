"""Farm revenue arithmetic: the platform's cut, and how refunds land on a farm.

Integer minor units only, percentages in basis points (ADR-006 — see
`domain/money.py`). Nothing here touches the database; it is pure so the
money rules can be tested exhaustively and read in one place.

Two decisions are worth stating outright, because both are easy to get
subtly wrong and expensive when wrong:

**Rounding favours the farm.** The commission is rounded *down*, so any
fraction of a paisa that cannot be split falls to the farmer rather than the
platform. Over thousands of lines the platform gives up at most one minor
unit per payout, and the alternative — rounding the house's cut up — is the
kind of default that reads as sharp practice when a farmer audits it.

**Refunds are allocated pro-rata.** `order_adjustments` records a refund
against the *order*, not the line. On a single-farm order that distinction
does not matter, but on an order carrying two farms' goods there is no
stored fact saying whose product was sent back. Splitting the refund by each
farm's share of that order's goods value is the only attribution the data
supports. It is deliberately conservative in aggregate: every refunded paisa
is charged to someone, so the platform never pays out money it refunded.
"""

from __future__ import annotations

from typing import NamedTuple

from truegrit_api.errors import ValidationAppError

# 100% in basis points. A commission may legitimately be 0 (a farm charged
# nothing); it may never exceed the whole line.
MAX_COMMISSION_BPS = 10_000

# Guardrail mirroring `domain.money.MAX_AMOUNT_MINOR` (₹100 crore). A payout
# past this is a data fault, not a big month.
MAX_PAYOUT_MINOR = 10_000_000_000


class RevenueSplit(NamedTuple):
    """How one net-revenue figure divides between platform and farm."""

    net_revenue_minor: int
    commission_bps: int
    commission_minor: int
    payout_minor: int


def validate_commission_bps(basis_points: object) -> int:
    """A commission rate that is not an integer 0-10000 is rejected outright.

    `bool` is excluded explicitly: it is a subclass of `int` in Python, so
    `True` would otherwise sail through as 1 basis point.
    """
    if isinstance(basis_points, bool) or not isinstance(basis_points, int):
        raise ValidationAppError("Commission must be a whole number of basis points.")
    if not 0 <= basis_points <= MAX_COMMISSION_BPS:
        raise ValidationAppError("Commission must be between 0% and 100%.")
    return basis_points


def parse_commission_percent(percent: object) -> int:
    """Convert a UI percentage (`12.5`) to basis points (`1250`).

    The console talks in percent because that is what an operator reads on a
    contract; storage stays in basis points so nothing downstream sees a
    float. Two decimal places is the limit — a rate of 12.345% is far more
    likely to be a typo than an agreement.
    """
    if isinstance(percent, bool) or not isinstance(percent, (int, float)):
        raise ValidationAppError("Commission percentage must be a number.")
    if percent != percent or percent in (float("inf"), float("-inf")):  # NaN / infinity
        raise ValidationAppError("Commission percentage must be a real number.")
    scaled = round(float(percent) * 100)
    if abs(float(percent) * 100 - scaled) > 1e-6:
        raise ValidationAppError("Commission percentage supports at most two decimal places.")
    return validate_commission_bps(int(scaled))


def format_commission_percent(basis_points: int) -> float:
    """Basis points back to the percentage the console displays."""
    return validate_commission_bps(basis_points) / 100


def net_revenue(gross_minor: int, refunded_minor: int) -> int:
    """Revenue after refunds, floored at zero.

    A refund can exceed the goods value it is attached to (a goodwill refund
    covering delivery, say). Letting that go negative would mean a later line
    silently subsidising it, so the floor is applied per line and the excess
    is simply not clawed back from the farm.
    """
    _validate_minor(gross_minor, "Gross revenue")
    _validate_minor(refunded_minor, "Refunded amount")
    return max(gross_minor - refunded_minor, 0)


def split_revenue(net_revenue_minor: int, commission_bps: int) -> RevenueSplit:
    """Divide net revenue into the platform's cut and the farm's payout.

    The two always sum back to the input exactly — the payout is derived by
    subtraction, never by a second rounding, so no paisa can be created or
    lost between them.
    """
    _validate_minor(net_revenue_minor, "Net revenue")
    rate = validate_commission_bps(commission_bps)
    commission_minor = (net_revenue_minor * rate) // MAX_COMMISSION_BPS
    return RevenueSplit(
        net_revenue_minor=net_revenue_minor,
        commission_bps=rate,
        commission_minor=commission_minor,
        payout_minor=net_revenue_minor - commission_minor,
    )


def allocate_refund(order_refund_minor: int, line_gross_minor: int, order_gross_minor: int) -> int:
    """One line's share of an order-level refund, by value.

    Rounded down per line, so the allocated shares can total slightly less
    than the refund on an order that does not divide evenly. That residue
    stays with the platform rather than being charged to an arbitrary farm
    chosen by iteration order — under-charging a farm by a paisa is
    recoverable; over-charging a specific one because it sorted first is not
    defensible when asked about.
    """
    _validate_minor(order_refund_minor, "Order refund")
    _validate_minor(line_gross_minor, "Line gross")
    _validate_minor(order_gross_minor, "Order gross")
    if order_gross_minor <= 0 or order_refund_minor <= 0:
        return 0
    share = (order_refund_minor * line_gross_minor) // order_gross_minor
    # Capped by BOTH the line and the refund. The second cap is not redundant:
    # `order_gross_minor` is the sum of the order's lines, so a line larger
    # than it means the two were read inconsistently (a line edited mid-query,
    # a partial order total). Without this, one line could be charged more
    # than the entire refund.
    return min(share, line_gross_minor, order_refund_minor)


def _validate_minor(amount: object, label: str) -> int:
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise ValidationAppError(f"{label} must be an integer of minor units.")
    if amount < 0:
        raise ValidationAppError(f"{label} cannot be negative.")
    if amount > MAX_PAYOUT_MINOR:
        raise ValidationAppError(f"{label} exceeds the supported range.")
    return amount

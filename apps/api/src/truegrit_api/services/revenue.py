"""Farm revenue console: what each farm has earned, the platform's cut, and
issuing a payout.

The shape of the feature:

* **Summary** (`farm_revenue_summary`) — one row per farm: lifetime earnings,
  refunds, the commission rate in force, what has already been paid, and what
  is outstanding right now.
* **Detail** (`farm_revenue_detail`) — the same farm's individual order lines
  and its payout history, so a figure on the summary can always be traced to
  the orders behind it.
* **Rate** (`set_farm_commission`) — the per-farm cut, or the house default.
* **Payout** (`issue_farm_payout`) — settles every outstanding line for a farm
  in one ledger entry.

What "issue payment" does and does not do
-----------------------------------------
It records the payout, marks the lines settled so they can never be paid
twice, and writes an audit row. It does **not** move money: this deployment
has no disbursement rail (Razorpay here collects from customers; paying out
needs RazorpayX or a bank integration that is not configured). The operator
transfers the money and files the reference. `provider` /
`provider_reference` on `farm_payouts` are the seam for automating that
later. Everything user-facing says "record", never "sent" — a console that
claims money left the account when it did not is worse than no console.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.revenue import (
    allocate_refund,
    format_commission_percent,
    net_revenue,
    parse_commission_percent,
    split_revenue,
    validate_commission_bps,
)
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.revenue import RevenueRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

SETTING_COMMISSION_BPS = "revenue.commission_bps"

# Must match migration 0042. A missing or unreadable row resolves here rather
# than raising, so a hand-edited settings table cannot take the Revenue page
# down — but unlike a feature switch, the fallback is not "the permissive
# value": 15% is simply the shipped default.
DEFAULT_COMMISSION_BPS = 1500

_MAX_REFERENCE_LENGTH = 120
_MAX_NOTE_LENGTH = 500


async def load_default_commission_bps(db: Database) -> int:
    row = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = ?", (SETTING_COMMISSION_BPS,)
    )
    if row is None:
        return DEFAULT_COMMISSION_BPS
    try:
        return validate_commission_bps(int(str(row["value"]).strip()))
    except (ValueError, TypeError, ValidationAppError):
        return DEFAULT_COMMISSION_BPS


class _FarmTally:
    """Running totals for one farm while its order lines are walked."""

    __slots__ = (
        "currency",
        "gross",
        "order_ids",
        "outstanding_gross",
        "outstanding_items",
        "outstanding_refunded",
        "refunded",
    )

    def __init__(self) -> None:
        self.gross = 0
        self.refunded = 0
        self.currency: str | None = None
        self.outstanding_gross = 0
        self.outstanding_refunded = 0
        self.outstanding_items: list[dict[str, Any]] = []
        self.order_ids: set[str] = set()


def _tally_line(tally: _FarmTally, line: dict[str, Any]) -> dict[str, Any]:
    """Fold one order line into a farm's totals; returns the line's own figures."""
    gross = int(line["line_gross_minor"] or 0)
    line_refund = allocate_refund(
        int(line["order_refunded_minor"] or 0),
        gross,
        int(line["order_goods_minor"] or 0),
    )
    net = net_revenue(gross, line_refund)

    tally.gross += gross
    tally.refunded += line_refund
    tally.order_ids.add(str(line["order_id"]))
    if tally.currency is None:
        tally.currency = str(line["currency_code"] or "INR")

    settled = line["payout_id"] is not None
    if not settled:
        tally.outstanding_gross += gross
        tally.outstanding_refunded += line_refund
        tally.outstanding_items.append(
            {
                "order_item_id": str(line["order_item_id"]),
                "gross_minor": gross,
                "refunded_minor": line_refund,
                "net_minor": net,
                "currency_code": str(line["currency_code"] or "INR"),
            }
        )
    return {
        "gross_minor": gross,
        "refunded_minor": line_refund,
        "net_minor": net,
        "settled": settled,
    }


async def _tallies_by_farm(
    repository: RevenueRepository, farm_id: str | None = None
) -> tuple[dict[str, _FarmTally], list[tuple[dict[str, Any], dict[str, Any]]]]:
    """Walk every earning line once, folding it into its farm's totals.

    Returns the per-farm tallies plus (line, figures) pairs, so a caller that
    needs the detailed breakdown does not re-run the arithmetic.
    """
    tallies: dict[str, _FarmTally] = {}
    detailed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for line in await repository.lines(farm_id):
        tally = tallies.setdefault(str(line["farm_id"]), _FarmTally())
        detailed.append((line, _tally_line(tally, line)))
    return tallies, detailed


def _farm_row(
    farm: dict[str, Any],
    tally: _FarmTally | None,
    paid: dict[str, int] | None,
    default_bps: int,
) -> dict[str, Any]:
    tally = tally or _FarmTally()
    paid = paid or {"paid_minor": 0, "commission_minor": 0, "payout_count": 0}
    override_bps = farm["commission_bps"]
    effective_bps = validate_commission_bps(
        int(override_bps) if override_bps is not None else default_bps
    )

    lifetime_net = net_revenue(tally.gross, tally.refunded)
    lifetime = split_revenue(lifetime_net, effective_bps)
    outstanding_net = net_revenue(tally.outstanding_gross, tally.outstanding_refunded)
    outstanding = split_revenue(outstanding_net, effective_bps)

    return {
        "farmId": str(farm["id"]),
        "farmName": farm["name"],
        "farmSlug": farm["slug"],
        "farmerName": farm["farmer_name"] or "",
        "region": farm["region"] or "",
        "status": farm["status"],
        "currencyCode": tally.currency or "INR",
        "ownerUserId": farm["owner_user_id"],
        "ownerName": farm["owner_name"] or "",
        "ownerEmail": farm["owner_email"] or "",
        # `commissionBps` is what is actually applied; `commissionSource` tells
        # the console whether that came from this farm or the house default, so
        # an operator can see at a glance which farms are on bespoke terms.
        "commissionBps": effective_bps,
        "commissionPercent": format_commission_percent(effective_bps),
        "commissionSource": "farm" if override_bps is not None else "default",
        "orderCount": len(tally.order_ids),
        "grossMinor": tally.gross,
        "refundedMinor": tally.refunded,
        "netRevenueMinor": lifetime_net,
        "commissionMinor": lifetime.commission_minor,
        "farmEarningsMinor": lifetime.payout_minor,
        "paidOutMinor": paid["paid_minor"],
        "payoutCount": paid["payout_count"],
        "outstandingItemCount": len(tally.outstanding_items),
        "outstandingGrossMinor": tally.outstanding_gross,
        "outstandingRefundedMinor": tally.outstanding_refunded,
        "outstandingNetMinor": outstanding_net,
        "outstandingCommissionMinor": outstanding.commission_minor,
        # The number the "Issue payment" button pays.
        "outstandingPayoutMinor": outstanding.payout_minor,
    }


async def farm_revenue_summary(db: Database) -> dict[str, Any]:
    repository = RevenueRepository(db)
    default_bps = await load_default_commission_bps(db)
    farms = await repository.list_farms()
    tallies, _ = await _tallies_by_farm(repository)
    paid_by_farm = await repository.payout_totals_by_farm()

    rows = [
        _farm_row(
            farm,
            tallies.get(str(farm["id"])),
            paid_by_farm.get(str(farm["id"])),
            default_bps,
        )
        for farm in farms
    ]
    return {
        "defaultCommissionBps": default_bps,
        "defaultCommissionPercent": format_commission_percent(default_bps),
        "farms": rows,
        "totals": {
            "grossMinor": sum(row["grossMinor"] for row in rows),
            "refundedMinor": sum(row["refundedMinor"] for row in rows),
            "netRevenueMinor": sum(row["netRevenueMinor"] for row in rows),
            "commissionMinor": sum(row["commissionMinor"] for row in rows),
            "farmEarningsMinor": sum(row["farmEarningsMinor"] for row in rows),
            "paidOutMinor": sum(row["paidOutMinor"] for row in rows),
            "outstandingPayoutMinor": sum(row["outstandingPayoutMinor"] for row in rows),
        },
    }


async def farm_revenue_detail(db: Database, farm_id: str) -> dict[str, Any]:
    repository = RevenueRepository(db)
    farm = await repository.get_farm(farm_id)
    if farm is None:
        raise NotFoundError("Farm not found.")

    default_bps = await load_default_commission_bps(db)
    tallies, detailed = await _tallies_by_farm(repository, farm_id)
    paid_by_farm = await repository.payout_totals_by_farm()
    summary = _farm_row(farm, tallies.get(farm_id), paid_by_farm.get(farm_id), default_bps)

    lines = [
        {
            "orderItemId": str(line["order_item_id"]),
            "orderId": str(line["order_id"]),
            "orderReference": line["public_reference"],
            "orderedAt": line["placed_at"] or line["order_created_at"],
            "productName": line["product_name"],
            "variantName": line["variant_name"],
            "quantity": int(line["quantity"] or 0),
            "currencyCode": line["currency_code"] or "INR",
            "grossMinor": figures["gross_minor"],
            "refundedMinor": figures["refunded_minor"],
            "netMinor": figures["net_minor"],
            "settled": figures["settled"],
            "payoutId": line["payout_id"],
        }
        for line, figures in detailed
    ]

    payouts = [_payout_row(row) for row in await repository.payouts(farm_id)]
    return {"summary": summary, "lines": lines, "payouts": payouts}


def _payout_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "farmId": row["farm_id"],
        "farmName": row["farm_name"],
        "currencyCode": row["currency_code"],
        "grossMinor": int(row["gross_minor"]),
        "refundedMinor": int(row["refunded_minor"]),
        "netRevenueMinor": int(row["net_revenue_minor"]),
        "commissionBps": int(row["commission_bps"]),
        "commissionPercent": format_commission_percent(int(row["commission_bps"])),
        "commissionMinor": int(row["commission_minor"]),
        "payoutMinor": int(row["payout_minor"]),
        "itemCount": int(row["item_count"]),
        "status": row["status"],
        "reference": row["reference"] or "",
        "note": row["note"] or "",
        "provider": row["provider"] or "",
        "providerReference": row["provider_reference"] or "",
        "paidToUserId": row["paid_to_user_id"],
        "paidToName": row["paid_to_name"] or "",
        "createdAt": row["created_at"],
        "createdByName": row["created_by_name"] or "Unknown",
    }


async def list_payouts(db: Database, limit: int = 100) -> dict[str, Any]:
    rows = await RevenueRepository(db).payouts(limit=limit)
    return {"items": [_payout_row(row) for row in rows]}


async def set_default_commission(
    db: Database, principal: Principal, request_id: str, *, percent: float
) -> dict[str, Any]:
    """Set the house commission rate applied to farms without an override."""
    basis_points = parse_commission_percent(percent)
    now = utc_now_iso()
    previous = await load_default_commission_bps(db)

    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (SETTING_COMMISSION_BPS, str(basis_points), now, principal.user_id),
            ),
            audit_statement(
                action="revenue.default_commission_changed",
                entity_type="app_setting",
                entity_id=SETTING_COMMISSION_BPS,
                actor_id=principal.user_id,
                request_id=request_id,
                created_at=now,
                before={"commissionBps": previous},
                after={"commissionBps": basis_points},
            ),
        ]
    )
    return {
        "defaultCommissionBps": basis_points,
        "defaultCommissionPercent": format_commission_percent(basis_points),
    }


async def set_farm_commission(
    db: Database, principal: Principal, request_id: str, *, farm_id: str, percent: float | None
) -> dict[str, Any]:
    """Set or clear one farm's commission override.

    `percent=None` clears the override and returns the farm to the house
    default. That is distinct from `percent=0`, which charges the farm nothing
    — collapsing the two would make "no special terms" unexpressable.
    """
    repository = RevenueRepository(db)
    farm = await repository.get_farm(farm_id)
    if farm is None:
        raise NotFoundError("Farm not found.")

    basis_points = None if percent is None else parse_commission_percent(percent)
    now = utc_now_iso()

    await db.batch(
        [
            (
                "UPDATE farms SET commission_bps = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                (basis_points, now, principal.user_id, farm_id),
            ),
            audit_statement(
                action="revenue.farm_commission_changed",
                entity_type="farm",
                entity_id=farm_id,
                actor_id=principal.user_id,
                request_id=request_id,
                created_at=now,
                before={"commissionBps": farm["commission_bps"]},
                after={"commissionBps": basis_points},
            ),
        ]
    )

    default_bps = await load_default_commission_bps(db)
    effective = basis_points if basis_points is not None else default_bps
    return {
        "farmId": farm_id,
        "commissionBps": effective,
        "commissionPercent": format_commission_percent(effective),
        "commissionSource": "farm" if basis_points is not None else "default",
    }


async def issue_farm_payout(
    db: Database,
    principal: Principal,
    request_id: str,
    *,
    farm_id: str,
    reference: str = "",
    note: str = "",
    expected_payout_minor: int | None = None,
) -> dict[str, Any]:
    """Settle every outstanding order line for one farm as a single payout.

    `expected_payout_minor` is the amount the operator saw on screen. If the
    balance moved between the page loading and the button being pressed — a
    refund landing, another admin paying out first — the request is rejected
    rather than quietly paying a different number than the one that was
    approved.

    Double payment is prevented by the database, not by this check: every line
    is inserted into `farm_payout_items`, whose primary key is the order line
    itself. Two concurrent clicks cannot both succeed, because the second
    batch violates that key and rolls back whole.
    """
    repository = RevenueRepository(db)
    farm = await repository.get_farm(farm_id)
    if farm is None:
        raise NotFoundError("Farm not found.")

    reference = reference.strip()[:_MAX_REFERENCE_LENGTH]
    note = note.strip()[:_MAX_NOTE_LENGTH]

    default_bps = await load_default_commission_bps(db)
    tallies, _ = await _tallies_by_farm(repository, farm_id)
    tally = tallies.get(farm_id)
    if tally is None or not tally.outstanding_items:
        raise ConflictError("This farm has nothing outstanding to pay.")

    currencies = {item["currency_code"] for item in tally.outstanding_items}
    if len(currencies) > 1:
        # No cross-currency payout is defensible without a stored FX rate, and
        # inventing one here would put an unauditable number in the ledger.
        raise ValidationAppError(
            "This farm has revenue in more than one currency; pay each out separately."
        )
    currency = currencies.pop()

    override_bps = farm["commission_bps"]
    effective_bps = validate_commission_bps(
        int(override_bps) if override_bps is not None else default_bps
    )
    outstanding_net = net_revenue(tally.outstanding_gross, tally.outstanding_refunded)
    split = split_revenue(outstanding_net, effective_bps)

    if expected_payout_minor is not None and expected_payout_minor != split.payout_minor:
        raise ConflictError(
            "The outstanding balance changed since this page was loaded. Reload and try again."
        )

    payout_id = new_id("fpo")
    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        (
            "INSERT INTO farm_payouts"
            " (id, farm_id, currency_code, gross_minor, refunded_minor, net_revenue_minor,"
            "  commission_bps, commission_minor, payout_minor, item_count, status,"
            "  reference, note, paid_to_user_id, created_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'recorded', ?, ?, ?, ?, ?)",
            (
                payout_id,
                farm_id,
                currency,
                tally.outstanding_gross,
                tally.outstanding_refunded,
                outstanding_net,
                effective_bps,
                split.commission_minor,
                split.payout_minor,
                len(tally.outstanding_items),
                reference or None,
                note or None,
                farm["owner_user_id"],
                now,
                principal.user_id,
            ),
        )
    ]
    statements.extend(
        (
            "INSERT INTO farm_payout_items"
            " (order_item_id, payout_id, farm_id, gross_minor, refunded_minor, net_minor)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                item["order_item_id"],
                payout_id,
                farm_id,
                item["gross_minor"],
                item["refunded_minor"],
                item["net_minor"],
            ),
        )
        for item in tally.outstanding_items
    )
    statements.append(
        audit_statement(
            action="revenue.payout_issued",
            entity_type="farm",
            entity_id=farm_id,
            actor_id=principal.user_id,
            request_id=request_id,
            created_at=now,
            after={
                "payoutId": payout_id,
                "currencyCode": currency,
                "grossMinor": tally.outstanding_gross,
                "refundedMinor": tally.outstanding_refunded,
                "netRevenueMinor": outstanding_net,
                "commissionBps": effective_bps,
                "commissionMinor": split.commission_minor,
                "payoutMinor": split.payout_minor,
                "itemCount": len(tally.outstanding_items),
                "reference": reference,
                "paidToUserId": farm["owner_user_id"],
            },
        )
    )

    try:
        await db.batch(statements)
    except Exception as exc:
        # The only expected failure is the primary-key clash on
        # `farm_payout_items` from a concurrent payout. Anything else is a
        # genuine fault, but either way no money should be reported as paid.
        if _is_unique_violation(exc):
            raise ConflictError(
                "Another payout for this farm was recorded first. Reload to see it."
            ) from exc
        raise

    return {
        "payoutId": payout_id,
        "farmId": farm_id,
        "farmName": farm["name"],
        "currencyCode": currency,
        "grossMinor": tally.outstanding_gross,
        "refundedMinor": tally.outstanding_refunded,
        "netRevenueMinor": outstanding_net,
        "commissionBps": effective_bps,
        "commissionPercent": format_commission_percent(effective_bps),
        "commissionMinor": split.commission_minor,
        "payoutMinor": split.payout_minor,
        "itemCount": len(tally.outstanding_items),
        "reference": reference,
        "paidToUserId": farm["owner_user_id"],
        "paidToName": farm["owner_name"] or "",
        "createdAt": now,
    }


def _is_unique_violation(exc: Exception) -> bool:
    """True for a primary-key/unique clash, on either SQLite or D1.

    D1 surfaces constraint failures as a generic error carrying the SQLite
    message, so matching the text is the only portable signal available.
    """
    message = str(exc).lower()
    return "unique" in message or "primary key" in message or "constraint failed" in message

"""Farm revenue and payout queries — parameterized SQL only.

Every read here is bounded and flat. Revenue pages are opened by an owner
looking at the whole marketplace at once, so a per-farm follow-up query would
put this on the same CPU cliff that took the sitemap down (see
`services/site_documents.py`): one aggregate query covers all farms.

The eligibility rule is defined once, in `_ELIGIBLE_ORDER_SQL`, and reused by
every query in this module. Revenue that a summary counts but a payout does
not (or the reverse) would show an operator a balance they can never pay out,
so the two must never drift.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

# An order line counts towards a farm once the customer's money is actually in:
# payment captured, order not cancelled. `pending_payment` and cancelled orders
# are excluded, so an abandoned checkout never shows up as a farm's earnings.
_ELIGIBLE_ORDER_SQL = (
    "o.payment_status IN ('paid', 'partially_refunded') AND o.order_status != 'cancelled'"
)

# Refunds are recorded against the order in `order_adjustments`. Summed per
# order here, then allocated across that order's farm lines by value — see
# `domain.revenue.allocate_refund` for why that is the only defensible split.
_ORDER_REFUNDS_SQL = """
  SELECT order_id, SUM(ABS(amount_minor)) AS refunded_minor
  FROM order_adjustments
  WHERE adjustment_type = 'refund'
  GROUP BY order_id
"""

# One row per (farm, order line) that has earned money, with the order's total
# goods value and refund alongside so the caller can apportion without a second
# round trip. `already_paid` marks lines a payout has already settled.
_FARM_LINE_SQL = f"""
SELECT
  oi.id AS order_item_id,
  p.farm_id AS farm_id,
  o.id AS order_id,
  o.public_reference,
  o.currency_code,
  o.placed_at,
  o.created_at AS order_created_at,
  oi.product_name,
  oi.variant_name,
  oi.quantity,
  oi.line_total_minor AS line_gross_minor,
  COALESCE(ord_totals.order_goods_minor, 0) AS order_goods_minor,
  COALESCE(refunds.refunded_minor, 0) AS order_refunded_minor,
  fpi.payout_id AS payout_id
FROM order_items oi
JOIN orders o ON o.id = oi.order_id
JOIN products p ON p.id = oi.product_id
LEFT JOIN ({_ORDER_REFUNDS_SQL}) refunds ON refunds.order_id = o.id
LEFT JOIN (
  SELECT oi2.order_id, SUM(oi2.line_total_minor) AS order_goods_minor
  FROM order_items oi2
  GROUP BY oi2.order_id
) ord_totals ON ord_totals.order_id = o.id
LEFT JOIN farm_payout_items fpi ON fpi.order_item_id = oi.id
WHERE p.farm_id IS NOT NULL AND {_ELIGIBLE_ORDER_SQL}
"""


class RevenueRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_farms(self) -> list[dict[str, Any]]:
        """Every non-archived farm with its commission override and owner.

        Archived farms are excluded from the console list but never from the
        payout path — money already earned stays payable after a farm is
        retired, which is why `lines_for_farm` does not filter on status.
        """
        return await self._db.fetch_all(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.status,
                   f.commission_bps,
                   fm.user_id AS owner_user_id,
                   u.display_name AS owner_name,
                   u.email AS owner_email
            FROM farms f
            LEFT JOIN farm_members fm ON fm.farm_id = f.id
            LEFT JOIN users u ON u.id = fm.user_id AND u.deleted_at IS NULL
            WHERE f.status != 'archived'
            GROUP BY f.id
            ORDER BY f.name
            """
        )

    async def get_farm(self, farm_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.status,
                   f.commission_bps,
                   fm.user_id AS owner_user_id,
                   u.display_name AS owner_name,
                   u.email AS owner_email
            FROM farms f
            LEFT JOIN farm_members fm ON fm.farm_id = f.id
            LEFT JOIN users u ON u.id = fm.user_id AND u.deleted_at IS NULL
            WHERE f.id = ?
            GROUP BY f.id
            """,
            (farm_id,),
        )

    async def lines(self, farm_id: str | None = None) -> list[dict[str, Any]]:
        """Earning order lines, for every farm or one of them.

        Returned unaggregated because refund apportionment happens per line in
        `domain.revenue` — pushing that into SQL would bury the one piece of
        arithmetic most likely to be questioned by a farmer inside a query.
        """
        if farm_id is None:
            return await self._db.fetch_all(f"{_FARM_LINE_SQL} ORDER BY p.farm_id, o.created_at")
        return await self._db.fetch_all(
            f"{_FARM_LINE_SQL} AND p.farm_id = ? ORDER BY o.created_at DESC",
            (farm_id,),
        )

    async def payouts(self, farm_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        where = "WHERE fp.farm_id = ?" if farm_id else ""
        params: tuple[Any, ...] = (farm_id, limit) if farm_id else (limit,)
        return await self._db.fetch_all(
            f"""
            SELECT fp.id, fp.farm_id, f.name AS farm_name, fp.currency_code,
                   fp.gross_minor, fp.refunded_minor, fp.net_revenue_minor,
                   fp.commission_bps, fp.commission_minor, fp.payout_minor,
                   fp.item_count, fp.status, fp.reference, fp.note,
                   fp.provider, fp.provider_reference,
                   fp.paid_to_user_id, payee.display_name AS paid_to_name,
                   fp.created_at, fp.created_by,
                   actor.display_name AS created_by_name
            FROM farm_payouts fp
            JOIN farms f ON f.id = fp.farm_id
            LEFT JOIN users payee ON payee.id = fp.paid_to_user_id
            LEFT JOIN users actor ON actor.id = fp.created_by
            {where}
            ORDER BY fp.created_at DESC
            LIMIT ?
            """,
            params,
        )

    async def payout_totals_by_farm(self) -> dict[str, dict[str, int]]:
        """Lifetime paid-out totals per farm, for the summary table."""
        rows = await self._db.fetch_all(
            """
            SELECT farm_id,
                   SUM(payout_minor) AS paid_minor,
                   SUM(commission_minor) AS commission_minor,
                   COUNT(*) AS payout_count
            FROM farm_payouts
            WHERE status = 'recorded'
            GROUP BY farm_id
            """
        )
        return {
            str(row["farm_id"]): {
                "paid_minor": int(row["paid_minor"] or 0),
                "commission_minor": int(row["commission_minor"] or 0),
                "payout_count": int(row["payout_count"] or 0),
            }
            for row in rows
        }

    async def payout_line_items(self, payout_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT fpi.order_item_id, fpi.gross_minor, fpi.refunded_minor, fpi.net_minor,
                   oi.product_name, oi.variant_name, oi.quantity,
                   o.public_reference, o.created_at AS order_created_at
            FROM farm_payout_items fpi
            JOIN order_items oi ON oi.id = fpi.order_item_id
            JOIN orders o ON o.id = oi.order_id
            WHERE fpi.payout_id = ?
            ORDER BY o.created_at DESC
            """,
            (payout_id,),
        )

"""Read-only aggregation queries for the owner analytics dashboard (migration
0065). Every figure is computed live from `orders`/`order_items` -- there is
no separate analytics table to fall out of sync with the orders themselves.

Cancelled orders are excluded everywhere here: an order that never happened
is not revenue, the same reasoning `CatalogueRepository.list_bestsellers`
already applies to "real sales" rankings.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

_TOP_PRODUCTS_LIMIT = 10


class AnalyticsRepository:
    def __init__(self, db: Database):
        self._db = db

    async def overview(self, *, from_date: str, to_date: str) -> dict[str, Any]:
        row = await self._db.fetch_one(
            """
            SELECT
              COALESCE(SUM(total_minor), 0) AS revenue_minor,
              COUNT(*) AS order_count
            FROM orders
            WHERE order_status != 'cancelled'
              AND DATE(COALESCE(placed_at, created_at)) BETWEEN ? AND ?
            """,
            (from_date, to_date),
        )
        return dict(row) if row else {"revenue_minor": 0, "order_count": 0}

    async def new_customers(self, *, from_date: str, to_date: str) -> int:
        """Customers whose *first ever* order (any status, any date) falls
        inside this range -- a returning customer's order in-range does not
        count, however revenue-positive it was."""
        row = await self._db.fetch_one(
            """
            SELECT COUNT(*) AS new_customers
            FROM (
              SELECT customer_user_id,
                     MIN(DATE(COALESCE(placed_at, created_at))) AS first_order_date
              FROM orders
              WHERE customer_user_id IS NOT NULL
              GROUP BY customer_user_id
              HAVING first_order_date BETWEEN ? AND ?
            )
            """,
            (from_date, to_date),
        )
        return int(row["new_customers"]) if row else 0

    async def revenue_by_day(self, *, from_date: str, to_date: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT
              DATE(COALESCE(placed_at, created_at)) AS day,
              SUM(total_minor) AS revenue_minor,
              COUNT(*) AS order_count
            FROM orders
            WHERE order_status != 'cancelled'
              AND DATE(COALESCE(placed_at, created_at)) BETWEEN ? AND ?
            GROUP BY day
            ORDER BY day
            """,
            (from_date, to_date),
        )

    async def top_products(self, *, from_date: str, to_date: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT
              oi.product_id,
              oi.product_name,
              SUM(oi.quantity) AS units_sold,
              SUM(oi.line_total_minor) AS revenue_minor
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.order_status != 'cancelled'
              AND DATE(COALESCE(o.placed_at, o.created_at)) BETWEEN ? AND ?
            GROUP BY oi.product_id, oi.product_name
            ORDER BY revenue_minor DESC
            LIMIT ?
            """,
            (from_date, to_date, _TOP_PRODUCTS_LIMIT),
        )

    async def status_breakdown(self, *, from_date: str, to_date: str) -> list[dict[str, Any]]:
        """Every status, including cancelled -- unlike the revenue figures
        above, this view exists specifically to show how much is cancelled,
        so excluding it here would hide the one thing it is for."""
        return await self._db.fetch_all(
            """
            SELECT order_status, COUNT(*) AS order_count
            FROM orders
            WHERE DATE(COALESCE(placed_at, created_at)) BETWEEN ? AND ?
            GROUP BY order_status
            ORDER BY order_count DESC
            """,
            (from_date, to_date),
        )

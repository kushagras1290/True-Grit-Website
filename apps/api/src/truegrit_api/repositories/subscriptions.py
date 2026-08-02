"""Read-only queries for customer subscriptions (migration 0064). Writes live
in `services.subscriptions`, matching every other repository in this
codebase.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

_SUMMARY_COLUMNS = """
  s.id, s.customer_user_id, s.variant_id, s.quantity, s.frequency, s.status,
  s.address_id, s.next_order_date, s.last_order_id, s.created_at, s.updated_at,
  s.cancelled_at,
  v.name AS variant_name, v.sku,
  p.id AS product_id, p.name AS product_name, p.slug AS product_slug,
  COALESCE('/media/' || m.object_key, NULLIF(p.image_url, '')) AS image_url,
  (
    SELECT vp.list_amount_minor FROM variant_prices vp
    WHERE vp.variant_id = s.variant_id AND vp.status = 'active'
    ORDER BY vp.starts_at DESC LIMIT 1
  ) AS unit_price_minor,
  u.display_name AS customer_name, u.email AS customer_email
"""

_SUMMARY_JOINS = """
  FROM subscriptions s
  JOIN product_variants v ON v.id = s.variant_id
  JOIN products p ON p.id = v.product_id
  LEFT JOIN media_assets m ON m.id = p.primary_media_id
  JOIN users u ON u.id = s.customer_user_id
"""


class SubscriptionRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_for_customer(
        self, customer_user_id: str, *, status: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE s.customer_user_id = ? AND (? IS NULL OR s.status = ?)
            ORDER BY s.created_at DESC
            """,
            (customer_user_id, status, status),
        )

    async def get_owned(self, subscription_id: str, customer_user_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE s.id = ? AND s.customer_user_id = ?
            """,
            (subscription_id, customer_user_id),
        )

    async def get_by_id(self, subscription_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE s.id = ?
            """,
            (subscription_id,),
        )

    async def list_admin(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE (? IS NULL OR s.status = ?)
            ORDER BY s.next_order_date, s.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (status, status, limit, max(offset, 0)),
        )

    async def count_admin(self, *, status: str | None = None) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM subscriptions WHERE (? IS NULL OR status = ?)",
            (status, status),
        )
        return int(row["total"]) if row else 0

    async def list_due(self, *, as_of_date: str, limit: int = 200) -> list[dict[str, Any]]:
        """Active subscriptions due on or before `as_of_date` (an ISO date),
        oldest-due first -- the renewal job's own read. Capped at `limit` per
        call so one enormous backlog (a cron that missed several days) cannot
        blow a single Worker invocation's CPU budget; the job re-queries on
        its next run and simply catches up further.
        """
        return await self._db.fetch_all(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE s.status = 'active' AND s.next_order_date <= ?
            ORDER BY s.next_order_date, s.created_at
            LIMIT ?
            """,
            (as_of_date, limit),
        )

    async def get_address(self, address_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, recipient_name, phone_e164, line1, line2, city, state,
                   postal_code, country_code
            FROM addresses
            WHERE id = ? AND archived_at IS NULL
            """,
            (address_id,),
        )

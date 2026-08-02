"""Reads over `promotions`, `promotion_rules`, `promotion_actions`, `coupons`
and `coupon_redemptions` (migration 0005, extended by 0060).

A promotion with no coupons is automatic -- it applies to every eligible cart
with no code. One or more coupons make it code-gated. Writes (create/update/
archive a promotion, issue/revoke a coupon) live in `services.promotions`;
this repository is read-only, matching the split used everywhere else.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database


class PromotionRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self,
        *,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Every promotion, newest-created first, with its coupon and
        redemption counts so the list doesn't need a second round trip per
        row."""
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = "AND p.name LIKE ?"
            params.append(f"%{search}%")
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT p.id, p.name, p.status, p.priority, p.starts_at, p.ends_at,
                   p.stacking_policy, p.usage_limit_total, p.usage_limit_per_customer,
                   p.headline, p.description, p.created_at, p.updated_at,
                   (SELECT COUNT(*) FROM coupons c WHERE c.promotion_id = p.id) AS coupon_count,
                   (SELECT COUNT(*) FROM coupon_redemptions cr
                     JOIN coupons c2 ON c2.id = cr.coupon_id
                    WHERE c2.promotion_id = p.id) AS redemption_count
            FROM promotions p
            WHERE (? IS NULL OR p.status = ?)
            {search_clause}
            ORDER BY p.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def count_admin(self, *, status: str | None = None, search: str | None = None) -> int:
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = "AND name LIKE ?"
            params.append(f"%{search}%")
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM promotions"
            f" WHERE (? IS NULL OR status = ?){search_clause}",
            tuple(params),
        )
        return int(row["total"]) if row else 0

    async def get_by_id(self, promotion_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one("SELECT * FROM promotions WHERE id = ?", (promotion_id,))

    async def get_rule(self, promotion_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT * FROM promotion_rules WHERE promotion_id = ? ORDER BY id LIMIT 1",
            (promotion_id,),
        )

    async def get_action(self, promotion_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT * FROM promotion_actions WHERE promotion_id = ? ORDER BY id LIMIT 1",
            (promotion_id,),
        )

    async def list_coupons(self, promotion_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT c.id, c.code, c.active, c.created_at,
                   (SELECT COUNT(*) FROM coupon_redemptions cr
                     WHERE cr.coupon_id = c.id) AS redemption_count
            FROM coupons c
            WHERE c.promotion_id = ?
            ORDER BY c.created_at DESC
            """,
            (promotion_id,),
        )

    async def get_coupon_by_code(self, code: str) -> dict[str, Any] | None:
        """Case-insensitive (the column is `COLLATE NOCASE`), joined with its
        promotion so the checkout resolver never needs a second query."""
        return await self._db.fetch_one(
            """
            SELECT c.id AS coupon_id, c.code, c.active AS coupon_active, c.promotion_id,
                   p.status, p.starts_at, p.ends_at, p.usage_limit_total,
                   p.usage_limit_per_customer, p.headline, p.description
            FROM coupons c
            JOIN promotions p ON p.id = c.promotion_id
            WHERE c.code = ?
            """,
            (code,),
        )

    async def count_redemptions(
        self, coupon_id: str, *, customer_user_id: str | None = None
    ) -> int:
        if customer_user_id is None:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) AS total FROM coupon_redemptions WHERE coupon_id = ?",
                (coupon_id,),
            )
        else:
            row = await self._db.fetch_one(
                "SELECT COUNT(*) AS total FROM coupon_redemptions"
                " WHERE coupon_id = ? AND customer_user_id = ?",
                (coupon_id, customer_user_id),
            )
        return int(row["total"]) if row else 0

    async def list_active_automatic(self, now: str) -> list[dict[str, Any]]:
        """Promotions with no coupon attached (so they need no code), active
        and within their window, best priority first -- the pool `rule` mode
        (homepage banner, and checkout when no code was entered) picks from."""
        return await self._db.fetch_all(
            """
            SELECT p.id, p.name, p.headline, p.description
            FROM promotions p
            WHERE p.status = 'active'
              AND (p.starts_at IS NULL OR p.starts_at <= ?)
              AND (p.ends_at IS NULL OR p.ends_at > ?)
              AND NOT EXISTS (SELECT 1 FROM coupons c WHERE c.promotion_id = p.id)
            ORDER BY p.priority DESC, p.created_at DESC
            """,
            (now, now),
        )

"""Read-only queries for customer wishlists (`wishlists`/`wishlist_items`,
shipped dormant in migration 0005, activated in 0079). Writes live in
`services.wishlist`, matching every other repository in this codebase.

Product-level, not variant-level -- `wishlist_items.product_id` is the shape
0005 shipped with, and it fits the storefront's product-card UI directly (a
shop grid card is one product, not a variant picker). Price/image shown for
a saved item come from that product's first active variant by sort_order,
the same "representative variant" idiom `repositories.admin.search_products`
already uses for its SKU column.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

_SUMMARY_COLUMNS = """
  wi.product_id, wi.added_at,
  p.name AS product_name, p.slug AS product_slug,
  COALESCE('/media/' || m.object_key, NULLIF(p.image_url, '')) AS image_url,
  fv.id AS variant_id, fv.name AS variant_name, fv.sku,
  vp.list_amount_minor AS unit_price_minor, vp.currency_code
"""

_SUMMARY_JOINS = """
  FROM wishlist_items wi
  JOIN wishlists w ON w.id = wi.wishlist_id
  JOIN products p ON p.id = wi.product_id
  LEFT JOIN media_assets m ON m.id = p.primary_media_id
  LEFT JOIN product_variants fv ON fv.id = (
    SELECT v.id FROM product_variants v
    WHERE v.product_id = p.id AND v.status = 'active'
    ORDER BY v.sort_order LIMIT 1
  )
  LEFT JOIN variant_prices vp ON vp.variant_id = fv.id AND vp.status = 'active'
"""


class WishlistRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_wishlist_id(self, user_id: str) -> str | None:
        row = await self._db.fetch_one("SELECT id FROM wishlists WHERE user_id = ?", (user_id,))
        return row["id"] if row else None

    async def list_for_customer(self, user_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            f"""
            SELECT {_SUMMARY_COLUMNS}
            {_SUMMARY_JOINS}
            WHERE w.user_id = ?
            ORDER BY wi.added_at DESC
            """,
            (user_id,),
        )

    async def product_ids_for_customer(self, user_id: str) -> list[str]:
        rows = await self._db.fetch_all(
            """
            SELECT wi.product_id FROM wishlist_items wi
            JOIN wishlists w ON w.id = wi.wishlist_id
            WHERE w.user_id = ?
            """,
            (user_id,),
        )
        return [row["product_id"] for row in rows]

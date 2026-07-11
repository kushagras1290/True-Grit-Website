"""Admin list queries — server pagination, never the whole catalogue."""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

MAX_PAGE_SIZE = 100


class AdminRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_products(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        return await self._db.fetch_all(
            """
            SELECT
              p.id, p.name, p.status, p.updated_at,
              u.display_name AS updated_by,
              COALESCE(f.name, b.name, '') AS farm_name,
              (SELECT v.sku FROM product_variants v
                WHERE v.product_id = p.id ORDER BY v.sort_order LIMIT 1) AS sku,
              (SELECT GROUP_CONCAT(c.name, ', ') FROM product_categories pc
                JOIN categories c ON c.id = pc.category_id
                WHERE pc.product_id = p.id) AS categories,
              (SELECT MIN(vp.list_amount_minor) FROM product_variants v
                JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
                WHERE v.product_id = p.id) AS min_price_minor,
              (SELECT MAX(vp.list_amount_minor) FROM product_variants v
                JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
                WHERE v.product_id = p.id) AS max_price_minor,
              (SELECT COALESCE(SUM(il.on_hand - il.reserved), 0) FROM product_variants v
                JOIN inventory_levels il ON il.variant_id = v.id
                WHERE v.product_id = p.id) AS available_stock
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN brands b ON b.id = p.brand_id
            LEFT JOIN users u ON u.id = p.updated_by
            WHERE p.archived_at IS NULL
            ORDER BY p.updated_at DESC, p.name
            LIMIT ? OFFSET ?
            """,
            (limit, max(offset, 0)),
        )

    async def list_categories(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), MAX_PAGE_SIZE)
        return await self._db.fetch_all(
            """
            SELECT
              c.id, c.name, c.slug, c.visibility, c.status, c.updated_at,
              parent.name AS parent_name,
              (SELECT COUNT(*) FROM product_categories pc WHERE pc.category_id = c.id)
                AS product_count
            FROM categories c
            LEFT JOIN categories parent ON parent.id = c.parent_id
            WHERE c.archived_at IS NULL
            ORDER BY c.sort_order, c.name
            LIMIT ? OFFSET ?
            """,
            (limit, max(offset, 0)),
        )

    async def list_inventory(self, limit: int = 100, offset: int = 0) -> list[dict[str, Any]]:
        limit = min(max(limit, 1), 200)
        return await self._db.fetch_all(
            """
            SELECT
              il.variant_id, p.name AS product_name, v.name AS variant_name, v.sku,
              loc.name AS location_name, il.on_hand, il.reserved,
              il.reorder_threshold, il.updated_at
            FROM inventory_levels il
            JOIN product_variants v ON v.id = il.variant_id
            JOIN products p ON p.id = v.product_id
            JOIN inventory_locations loc ON loc.id = il.location_id
            ORDER BY (il.on_hand - il.reserved - il.reorder_threshold) ASC, p.name
            LIMIT ? OFFSET ?
            """,
            (limit, max(offset, 0)),
        )

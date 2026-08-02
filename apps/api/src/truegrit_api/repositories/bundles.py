"""Read-only queries for product bundles (migration 0062). Writes live in
`services.bundles`, matching every other repository in this codebase.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database


class BundleRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self, *, limit: int = 50, offset: int = 0, status: str | None = None
    ) -> list[dict[str, Any]]:
        where = "WHERE (? IS NULL OR b.status = ?)"
        rows = await self._db.fetch_all(
            f"""
            SELECT b.id, b.name, b.slug, b.description, b.status, b.bundle_price_minor,
                   b.image_url, b.image_alt, b.created_at, b.updated_at,
                   (SELECT COUNT(*) FROM bundle_items bi WHERE bi.bundle_id = b.id) AS item_count
            FROM bundles b
            {where}
            ORDER BY b.name
            LIMIT ? OFFSET ?
            """,
            (status, status, limit, max(offset, 0)),
        )
        return rows

    async def count_admin(self, *, status: str | None = None) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM bundles WHERE (? IS NULL OR status = ?)",
            (status, status),
        )
        return int(row["total"]) if row else 0

    async def get_by_id(self, bundle_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, name, slug, description, status, bundle_price_minor,
                   image_url, image_alt, created_at, updated_at
            FROM bundles WHERE id = ?
            """,
            (bundle_id,),
        )

    async def get_by_slug(self, slug: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, name, slug, description, status, bundle_price_minor,
                   image_url, image_alt, created_at, updated_at
            FROM bundles WHERE slug = ?
            """,
            (slug,),
        )

    async def list_items(self, bundle_id: str) -> list[dict[str, Any]]:
        """A bundle's items with enough product/variant/price context to
        render a shop card or an admin edit form without a second round trip
        per item."""
        return await self._db.fetch_all(
            """
            SELECT bi.id, bi.variant_id, bi.quantity, bi.sort_order,
                   v.name AS variant_name, v.sku,
                   p.id AS product_id, p.name AS product_name, p.slug AS product_slug,
                   COALESCE(
                     '/media/' || m.object_key,
                     NULLIF(p.image_url, '')
                   ) AS image_url,
                   (
                     SELECT vp.list_amount_minor FROM variant_prices vp
                     WHERE vp.variant_id = bi.variant_id AND vp.status = 'active'
                     ORDER BY vp.starts_at DESC LIMIT 1
                   ) AS unit_price_minor
            FROM bundle_items bi
            JOIN product_variants v ON v.id = bi.variant_id
            JOIN products p ON p.id = v.product_id
            LEFT JOIN media_assets m ON m.id = p.primary_media_id
            WHERE bi.bundle_id = ?
            ORDER BY bi.sort_order, bi.id
            """,
            (bundle_id,),
        )

    async def list_active(self, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT id, name, slug, description, bundle_price_minor, image_url, image_alt
            FROM bundles
            WHERE status = 'active'
            ORDER BY name
            LIMIT ? OFFSET ?
            """,
            (limit, max(offset, 0)),
        )

    async def list_active_matching_variants(self, variant_ids: list[str]) -> list[dict[str, Any]]:
        """Active bundles whose *entire* item list is drawn from
        `variant_ids` -- a bundle needing even one variant the cart does not
        have can never match, so that is filtered here; the caller still has
        to confirm quantities (this only proves membership, not enough of
        each). Returns each candidate with its items attached.
        """
        if not variant_ids:
            return []
        placeholders = ", ".join("?" for _ in variant_ids)
        bundle_rows = await self._db.fetch_all(
            f"""
            SELECT b.id, b.name, b.bundle_price_minor
            FROM bundles b
            WHERE b.status = 'active'
              AND EXISTS (SELECT 1 FROM bundle_items bi WHERE bi.bundle_id = b.id)
              AND NOT EXISTS (
                SELECT 1 FROM bundle_items bi
                WHERE bi.bundle_id = b.id AND bi.variant_id NOT IN ({placeholders})
              )
            """,
            tuple(variant_ids),
        )
        if not bundle_rows:
            return []
        bundle_ids = [row["id"] for row in bundle_rows]
        item_placeholders = ", ".join("?" for _ in bundle_ids)
        item_rows = await self._db.fetch_all(
            f"""
            SELECT bundle_id, variant_id, quantity
            FROM bundle_items
            WHERE bundle_id IN ({item_placeholders})
            """,
            tuple(bundle_ids),
        )
        items_by_bundle: dict[str, list[dict[str, Any]]] = {}
        for row in item_rows:
            items_by_bundle.setdefault(row["bundle_id"], []).append(row)
        return [
            {**row, "items": items_by_bundle.get(row["id"], [])} for row in bundle_rows
        ]

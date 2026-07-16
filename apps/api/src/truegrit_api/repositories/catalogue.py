"""Catalogue repository — parameterized SQL only, rows mapped to DTO dicts.

Availability is always derived from inventory (on_hand - reserved); price comes
from the active price row for the variant and market. Client-sent prices are
never trusted anywhere in the system.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.domain.inventory import InventoryLevel, availability_label
from truegrit_api.domain.rules import compile_rule
from truegrit_api.platform.database import Database

_PRODUCT_BASE_SQL = """
SELECT
  p.id, p.name, p.slug, p.short_description, p.product_type, p.status,
  p.seo_title, p.seo_description, p.image_url,
  f.name AS farm_name, f.slug AS farm_slug, f.region AS farm_region,
  m.alt_text AS image_alt
FROM products p
LEFT JOIN farms f ON f.id = p.farm_id
LEFT JOIN media_assets m ON m.id = p.primary_media_id
"""


class CatalogueRepository:
    def __init__(self, db: Database):
        self._db = db

    async def _variants_for(self, product_ids: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not product_ids:
            return {}
        placeholders = ", ".join("?" for _ in product_ids)
        rows = await self._db.fetch_all(
            f"""
            SELECT
              v.id, v.product_id, v.name, v.sku, v.sort_order,
              vp.list_amount_minor, vp.sale_amount_minor,
              COALESCE(SUM(il.on_hand - il.reserved), 0) AS available,
              COALESCE(MIN(il.reorder_threshold), 0) AS reorder_threshold
            FROM product_variants v
            LEFT JOIN variant_prices vp
              ON vp.variant_id = v.id AND vp.status = 'active'
            LEFT JOIN inventory_levels il ON il.variant_id = v.id
            WHERE v.product_id IN ({placeholders}) AND v.status = 'active'
            GROUP BY v.id
            ORDER BY v.product_id, v.sort_order
            """,
            product_ids,
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["product_id"], []).append(row)
        return grouped

    async def _certifications_for(self, product_ids: list[str]) -> dict[str, str]:
        if not product_ids:
            return {}
        placeholders = ", ".join("?" for _ in product_ids)
        rows = await self._db.fetch_all(
            f"""
            SELECT pc.product_id, c.name
            FROM product_certifications pc
            JOIN certifications c ON c.id = pc.certification_id
            WHERE pc.product_id IN ({placeholders}) AND pc.claim_review_state = 'approved'
            ORDER BY c.name
            """,
            product_ids,
        )
        certifications: dict[str, str] = {}
        for row in rows:
            certifications.setdefault(row["product_id"], row["name"])
        return certifications

    async def _tags_for(self, product_ids: list[str]) -> dict[str, list[str]]:
        if not product_ids:
            return {}
        placeholders = ", ".join("?" for _ in product_ids)
        rows = await self._db.fetch_all(
            f"""
            SELECT pt.product_id, t.label
            FROM product_tags pt
            JOIN tags t ON t.id = pt.tag_id
            WHERE pt.product_id IN ({placeholders})
            ORDER BY t.label
            """,
            product_ids,
        )
        tags: dict[str, list[str]] = {}
        for row in rows:
            tags.setdefault(row["product_id"], []).append(row["label"])
        return tags

    def _variant_summary(self, row: dict[str, Any]) -> dict[str, Any]:
        level = InventoryLevel(on_hand=max(int(row["available"]), 0), reserved=0)
        return {
            "id": row["id"],
            "name": row["name"],
            "sku": row["sku"],
            "list_minor": int(row["list_amount_minor"] or 0),
            "sale_minor": row["sale_amount_minor"],
            "availability": availability_label(level, int(row["reorder_threshold"])),
        }

    def _summarize(
        self,
        row: dict[str, Any],
        variants: list[dict[str, Any]],
        certification: str,
        tags: list[str],
    ) -> dict[str, Any]:
        variant_summaries = [self._variant_summary(entry) for entry in variants]
        lead = variant_summaries[0] if variant_summaries else None
        statuses = [entry["availability"] for entry in variant_summaries]
        if "in_stock" in statuses:
            availability = "in_stock"
        elif "low_stock" in statuses:
            availability = "low_stock"
        else:
            availability = "out_of_stock"
        return {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "farm_name": row["farm_name"] or "",
            "region": row["farm_region"] or "",
            "certification": certification,
            "price_minor": lead["list_minor"] if lead else 0,
            "sale_minor": lead["sale_minor"] if lead else None,
            "currency_code": "INR",
            "unit_label": lead["name"] if lead else "",
            "availability": availability,
            "tags": tags,
            "image_url": row["image_url"],
            "image_alt": row["image_alt"] or row["name"],
            "_variants": variant_summaries,
            "_farm_slug": row["farm_slug"] or "",
            "_short_description": row["short_description"] or "",
        }

    async def _assemble(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        ids = [row["id"] for row in rows]
        variants = await self._variants_for(ids)
        certifications = await self._certifications_for(ids)
        tags = await self._tags_for(ids)
        return [
            self._summarize(
                row,
                variants.get(row["id"], []),
                certifications.get(row["id"], ""),
                tags.get(row["id"], []),
            )
            for row in rows
        ]

    async def list_published_by_rule(self, rule_json: dict[str, Any]) -> list[dict[str, Any]]:
        compiled = compile_rule(rule_json)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published' AND {compiled.where_sql}"
            f" ORDER BY {compiled.order_sql} LIMIT ?",
            [*compiled.params, compiled.limit],
        )
        return await self._assemble(rows)

    async def list_all_published(self, limit: int = 200) -> list[dict[str, Any]]:
        """Every published product, newest first. Backs the storefront's shop
        grid, so it reflects admin publishes without any per-category rule."""
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published'"
            " ORDER BY p.updated_at DESC, p.name LIMIT ?",
            (limit,),
        )
        return await self._assemble(rows)

    async def list_published_by_category(self, category_id: str) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            f"""
            {_PRODUCT_BASE_SQL}
            JOIN product_categories pc ON pc.product_id = p.id
            WHERE pc.category_id = ? AND p.status = 'published'
            ORDER BY pc.sort_order, p.name
            LIMIT 200
            """,
            (category_id,),
        )
        return await self._assemble(rows)

    async def list_published_by_slugs(self, slugs: list[str]) -> list[dict[str, Any]]:
        if not slugs:
            return []
        placeholders = ", ".join("?" for _ in slugs)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published' AND p.slug IN ({placeholders})",
            slugs,
        )
        summaries = await self._assemble(rows)
        order = {slug: index for index, slug in enumerate(slugs)}
        return sorted(summaries, key=lambda item: order.get(item["slug"], len(order)))

    async def get_published_detail(self, slug: str) -> dict[str, Any] | None:
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.slug = ? AND p.status = 'published' LIMIT 1",
            (slug,),
        )
        if not rows:
            return None
        summary = (await self._assemble(rows))[0]
        row = rows[0]

        related = await self._db.fetch_all(
            """
            SELECT p2.slug
            FROM product_categories pc1
            JOIN product_categories pc2 ON pc2.category_id = pc1.category_id
            JOIN products p2 ON p2.id = pc2.product_id
            WHERE pc1.product_id = ? AND p2.id <> ? AND p2.status = 'published'
            ORDER BY pc2.sort_order
            LIMIT 4
            """,
            (row["id"], row["id"]),
        )

        farm = await self._db.fetch_one(
            "SELECT name, region FROM farms WHERE slug = ?", (summary["_farm_slug"],)
        )
        farm_name = farm["name"] if farm else summary["farm_name"]

        detail = dict(summary)
        detail.update(
            {
                "short_description": summary["_short_description"],
                "overview": summary["_short_description"],
                "farm_slug": summary["_farm_slug"],
                "storage_guidance": "",
                "harvest_note": "",
                "growing_method": "",
                "variants": summary["_variants"],
                "traceability": [
                    {"label": "Farm", "detail": f"{farm_name} — {summary['region']}"},
                    {"label": "Certification", "detail": summary["certification"] or "In review"},
                    {
                        "label": "Quality check",
                        "detail": "Checked at the fulfilment centre before dispatch",
                    },
                    {"label": "Delivery", "detail": "Shipped with full lot traceability"},
                ],
                "related_slugs": [entry["slug"] for entry in related],
                "seo": {
                    "title": row["seo_title"] or row["name"],
                    "description": row["seo_description"] or summary["_short_description"],
                    "canonical_path": f"/product/{row['slug']}",
                    "indexing": "index",
                },
            }
        )
        for key in ("_variants", "_farm_slug", "_short_description"):
            detail.pop(key, None)
        return detail

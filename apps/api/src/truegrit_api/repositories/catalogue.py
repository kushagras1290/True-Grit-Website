"""Catalogue repository — parameterized SQL only, rows mapped to DTO dicts.

Availability is always derived from inventory (on_hand - reserved); price comes
from the active price row for the variant and market. Client-sent prices are
never trusted anywhere in the system.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.domain.inventory import InventoryLevel, availability_label
from truegrit_api.domain.rules import MAX_LIMIT as RULE_MAX_LIMIT
from truegrit_api.domain.rules import compile_rule
from truegrit_api.domain.sitemap import SITEMAP_MAX_URLS
from truegrit_api.platform.database import Database

# Static category assignment has no owner-configured rule ceiling, so it
# borrows the rule engine's own pool cap for consistency between the two
# assignment modes (see `compile_rule`'s `limit`, which defaults this same way).
_STATIC_CATEGORY_POOL_LIMIT = RULE_MAX_LIMIT

_PRODUCT_BASE_SQL = """
SELECT
  p.id, p.name, p.slug, p.short_description, p.product_type, p.status,
  p.seo_title, p.seo_description, p.return_eligible,
  COALESCE(
    '/media/' || m.object_key,
    NULLIF(p.image_url, ''),
    (
      SELECT c.hero_image_url
      FROM product_categories pc
      JOIN categories c ON c.id = pc.category_id
      WHERE pc.product_id = p.id AND NULLIF(c.hero_image_url, '') IS NOT NULL
      ORDER BY pc.is_primary DESC, pc.sort_order, c.sort_order
      LIMIT 1
    )
  ) AS image_url,
  f.name AS farm_name, f.slug AS farm_slug, f.region AS farm_region,
  COALESCE(NULLIF(p.image_alt, ''), m.alt_text) AS image_alt
FROM products p
LEFT JOIN farms f ON f.id = p.farm_id
LEFT JOIN media_assets m ON m.id = p.primary_media_id
"""


def geo_release_clause(
    country: str | None,
    alias: str = "p",
    *,
    table: str = "product_release_countries",
    id_column: str = "product_id",
) -> tuple[str, list[Any]]:
    """SQL fragment limiting rows to entities released in `country`.

    Entities are either released globally or to an explicit country list, in a
    `{table}(id_column, country_code)` side table alongside a `release_scope`
    column on the entity itself — the same shape for products
    (`product_release_countries`) and categories (`category_release_countries`).
    When no country is known (internal callers, older clients) nothing is
    filtered — the storefront always forwards the visitor's country, so public
    surfaces stay geo-locked there.
    """
    if not country:
        return "", []
    return (
        f" AND ({alias}.release_scope = 'global' OR EXISTS ("
        f"SELECT 1 FROM {table} rc"
        f" WHERE rc.{id_column} = {alias}.id AND rc.country_code = ?))",
        [country],
    )


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

    async def list_published_by_rule(
        self,
        rule_json: dict[str, Any],
        *,
        country: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Products matching a category's rule, one page at a time.

        `compiled.limit` (the rule's own `"limit"` field, e.g. 96) caps the
        *total eligible pool* the category will ever surface — a merchandising
        ceiling set by the category editor. `limit`/`offset` page through that
        pool for display; they are a different concept and never widen it.
        Returns `(page_of_products, total_eligible)` where `total_eligible` is
        the actual match count clamped to the pool ceiling, so callers can
        compute real page counts without a second round trip.
        """
        compiled = compile_rule(rule_json)
        geo_sql, geo_params = geo_release_clause(country)
        count_row = await self._db.fetch_one(
            f"SELECT COUNT(*) AS cnt FROM products p"
            f" WHERE p.status = 'published' AND {compiled.where_sql}{geo_sql}",
            [*compiled.params, *geo_params],
        )
        total = min(int(count_row["cnt"]) if count_row else 0, compiled.limit)
        safe_offset = max(offset, 0)
        if safe_offset >= total:
            return [], total
        page_limit = min(max(limit, 1), total - safe_offset)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published' AND {compiled.where_sql}"
            f"{geo_sql} ORDER BY {compiled.order_sql} LIMIT ? OFFSET ?",
            [*compiled.params, *geo_params, page_limit, safe_offset],
        )
        return await self._assemble(rows), total

    async def list_all_published(
        self, *, limit: int = 200, offset: int = 0, country: str | None = None
    ) -> tuple[list[dict[str, Any]], int]:
        """Every published product, newest first, one page at a time. Backs
        the storefront's shop grid, so it reflects admin publishes without any
        per-category rule. Returns `(page_of_products, total_published)`."""
        geo_sql, geo_params = geo_release_clause(country)
        count_row = await self._db.fetch_one(
            f"SELECT COUNT(*) AS cnt FROM products p WHERE p.status = 'published'{geo_sql}",
            geo_params,
        )
        total = int(count_row["cnt"]) if count_row else 0
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published'{geo_sql}"
            " ORDER BY p.updated_at DESC, p.name LIMIT ? OFFSET ?",
            (*geo_params, max(limit, 1), max(offset, 0)),
        )
        return await self._assemble(rows), total

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + updated_at for every indexable published product.

        Deliberately not `list_all_published`: that assembles variants,
        prices, inventory and tags across four queries to build storefront
        cards. A sitemap needs two columns, and paying the card cost for
        every product at once overran the Worker CPU budget, which is what
        made `/sitemaps/products` return 500 and the storefront publish an
        empty urlset in its place. `noindex` products are excluded — listing
        a URL whose own page tells crawlers not to index it is a
        contradiction that costs crawl budget.
        """
        return await self._db.fetch_all(
            "SELECT slug, updated_at FROM products"
            " WHERE status = 'published' AND indexing_policy = 'index'"
            " ORDER BY updated_at DESC, slug LIMIT ?",
            (limit,),
        )

    async def list_published_by_category(
        self,
        category_id: str,
        *,
        country: str | None = None,
        limit: int = 24,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Products statically assigned to a category, one page at a time.
        Returns `(page_of_products, total_eligible)`, `total_eligible` clamped
        to `_STATIC_CATEGORY_POOL_LIMIT` for parity with the rule-based path."""
        geo_sql, geo_params = geo_release_clause(country)
        count_row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS cnt
            FROM products p
            JOIN product_categories pc ON pc.product_id = p.id
            WHERE pc.category_id = ? AND p.status = 'published'{geo_sql}
            """,
            (category_id, *geo_params),
        )
        matched = int(count_row["cnt"]) if count_row else 0
        total = min(matched, _STATIC_CATEGORY_POOL_LIMIT)
        safe_offset = max(offset, 0)
        if safe_offset >= total:
            return [], total
        page_limit = min(max(limit, 1), total - safe_offset)
        rows = await self._db.fetch_all(
            f"""
            {_PRODUCT_BASE_SQL}
            JOIN product_categories pc ON pc.product_id = p.id
            WHERE pc.category_id = ? AND p.status = 'published'{geo_sql}
            ORDER BY pc.sort_order, p.name
            LIMIT ? OFFSET ?
            """,
            (category_id, *geo_params, page_limit, safe_offset),
        )
        return await self._assemble(rows), total

    async def list_published_by_slugs(
        self, slugs: list[str], country: str | None = None
    ) -> list[dict[str, Any]]:
        if not slugs:
            return []
        placeholders = ", ".join("?" for _ in slugs)
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published'"
            f" AND p.slug IN ({placeholders}){geo_sql}",
            (*slugs, *geo_params),
        )
        summaries = await self._assemble(rows)
        order = {slug: index for index, slug in enumerate(slugs)}
        return sorted(summaries, key=lambda item: order.get(item["slug"], len(order)))

    async def list_highlighted(self, country: str | None = None) -> list[dict[str, Any]]:
        """The owner-curated highlight slots, in curated order. Published and
        geo-visible products only, so a swap in the admin is all it takes."""
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"""
            {_PRODUCT_BASE_SQL}
            JOIN highlighted_products hp ON hp.product_id = p.id
            WHERE p.status = 'published'{geo_sql}
            ORDER BY hp.sort_order, p.name
            LIMIT 12
            """,
            geo_params,
        )
        return await self._assemble(rows)

    async def get_published_detail(
        self, slug: str, country: str | None = None
    ) -> dict[str, Any] | None:
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.slug = ? AND p.status = 'published'{geo_sql} LIMIT 1",
            (slug, *geo_params),
        )
        if not rows:
            return None
        summary = (await self._assemble(rows))[0]
        row = rows[0]

        # Owner-curated links fill the "goes well with" slots first; only when
        # the owner has linked nothing do we fall back to same-category picks.
        related_geo_sql, related_geo_params = geo_release_clause(country, alias="p2")
        related = await self._db.fetch_all(
            f"""
            SELECT p2.slug
            FROM product_links pl
            JOIN products p2 ON p2.id = pl.linked_product_id
            WHERE pl.product_id = ? AND p2.status = 'published'{related_geo_sql}
            ORDER BY pl.sort_order
            LIMIT 8
            """,
            (row["id"], *related_geo_params),
        )
        if not related:
            related = await self._db.fetch_all(
                f"""
                SELECT p2.slug
                FROM product_categories pc1
                JOIN product_categories pc2 ON pc2.category_id = pc1.category_id
                JOIN products p2 ON p2.id = pc2.product_id
                WHERE pc1.product_id = ? AND p2.id <> ? AND p2.status = 'published'
                {related_geo_sql}
                ORDER BY pc2.sort_order
                LIMIT 4
                """,
                (row["id"], row["id"], *related_geo_params),
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
                "return_eligible": bool(row["return_eligible"]),
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

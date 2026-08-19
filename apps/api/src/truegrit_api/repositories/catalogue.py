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
from truegrit_api.repositories.entity_translations import EntityTranslationRepository
from truegrit_api.services.price_adjustments import apply_percent, resolve_adjustments

# Static category assignment has no owner-configured rule ceiling, so it
# borrows the rule engine's own pool cap for consistency between the two
# assignment modes (see `compile_rule`'s `limit`, which defaults this same way).
_STATIC_CATEGORY_POOL_LIMIT = RULE_MAX_LIMIT

_PRODUCT_BASE_SQL = """
SELECT
  p.id, p.name, p.slug, p.short_description, p.product_type, p.status,
  p.seo_title, p.seo_description, p.return_eligible, p.accepts_orders,
  p.payments_override, p.harvest_note, p.growing_method, p.storage_guidance,
  COALESCE(
    '/media/' || m.object_key,
    NULLIF(p.image_url, '')
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


def tag_filter_clause(tag_keys: list[str], alias: str = "p") -> tuple[str, list[Any]]:
    """SQL fragment narrowing rows to products carrying ANY of `tag_keys`
    (e.g. dietary filters: "Vegan" OR "Gluten Free" both count as a match,
    matching how a shopper picking either checkbox expects broader results,
    not a product carrying every selected diet at once)."""
    if not tag_keys:
        return "", []
    placeholders = ", ".join("?" for _ in tag_keys)
    return (
        f" AND {alias}.id IN (SELECT pt.product_id FROM product_tags pt"
        f" JOIN tags t ON t.id = pt.tag_id WHERE t.key IN ({placeholders}))",
        list(tag_keys),
    )


def certification_filter_clause(cert_slugs: list[str], alias: str = "p") -> tuple[str, list[Any]]:
    """SQL fragment narrowing rows to products carrying ANY of `cert_slugs`
    among their *approved* certifications -- same OR-within-facet semantics
    as `tag_filter_clause`."""
    if not cert_slugs:
        return "", []
    placeholders = ", ".join("?" for _ in cert_slugs)
    return (
        f" AND {alias}.id IN (SELECT pc.product_id FROM product_certifications pc"
        f" JOIN certifications c ON c.id = pc.certification_id"
        f" WHERE pc.claim_review_state = 'approved' AND c.slug IN ({placeholders}))",
        list(cert_slugs),
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
              v.id, v.product_id, v.name, v.sku, v.sort_order, v.is_default,
              vp.list_amount_minor, vp.sale_amount_minor,
              COALESCE(SUM(il.on_hand - il.reserved), 0) AS available,
              COALESCE(MIN(il.reorder_threshold), 0) AS reorder_threshold
            FROM product_variants v
            LEFT JOIN variant_prices vp
              ON vp.variant_id = v.id AND vp.status = 'active'
            LEFT JOIN inventory_levels il ON il.variant_id = v.id
            WHERE v.product_id IN ({placeholders}) AND v.status = 'active'
            GROUP BY v.id
            -- The customer-facing initial variant selection (product.tsx)
            -- just takes the first entry in this list, so the explicit
            -- default (migration 0100) has to sort first here too.
            ORDER BY v.product_id, v.is_default DESC, v.sort_order, v.name
            """,
            product_ids,
        )
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in rows:
            grouped.setdefault(row["product_id"], []).append(row)
        return grouped

    async def _certifications_for(self, product_ids: list[str]) -> dict[str, list[str]]:
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
        certifications: dict[str, list[str]] = {}
        for row in rows:
            certifications.setdefault(row["product_id"], []).append(row["name"])
        return certifications

    async def _ratings_for(self, product_ids: list[str]) -> dict[str, dict[str, Any]]:
        """Average and count over *approved* reviews only, per product --
        pending/rejected/removed reviews never influence the public rating."""
        if not product_ids:
            return {}
        placeholders = ", ".join("?" for _ in product_ids)
        rows = await self._db.fetch_all(
            f"""
            SELECT product_id, COUNT(*) AS count, AVG(rating) AS average
            FROM reviews
            WHERE product_id IN ({placeholders}) AND status = 'approved'
            GROUP BY product_id
            """,
            product_ids,
        )
        return {row["product_id"]: row for row in rows}

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

    def _variant_summary(self, row: dict[str, Any], percent: int) -> dict[str, Any]:
        level = InventoryLevel(on_hand=max(int(row["available"]), 0), reserved=0)
        list_minor = int(row["list_amount_minor"] or 0)
        return {
            "id": row["id"],
            "name": row["name"],
            "sku": row["sku"],
            "list_minor": list_minor,
            "sale_minor": row["sale_amount_minor"],
            # Only set when an active rule actually changes this visitor's
            # price -- absent, not zero, so the storefront can tell "no
            # adjustment" apart from "adjusted to the same amount".
            "adjusted_minor": apply_percent(list_minor, percent) if percent else None,
            "availability": availability_label(level, int(row["reorder_threshold"])),
        }

    def _summarize(
        self,
        row: dict[str, Any],
        variants: list[dict[str, Any]],
        certifications: list[str],
        tags: list[str],
        percent: int,
        rating: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        variant_summaries = [self._variant_summary(entry, percent) for entry in variants]
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
            "certifications": certifications,
            "price_minor": lead["list_minor"] if lead else 0,
            "sale_minor": lead["sale_minor"] if lead else None,
            "adjusted_minor": lead["adjusted_minor"] if lead else None,
            "currency_code": "INR",
            "unit_label": lead["name"] if lead else "",
            "availability": availability,
            "tags": tags,
            "image_url": row["image_url"],
            "image_alt": row["image_alt"] or row["name"],
            "accepts_orders": bool(row["accepts_orders"]),
            "payments_override": row["payments_override"],
            "lead_variant_id": lead["id"] if lead else None,
            "rating_average": round(float(rating["average"]), 1) if rating else 0.0,
            "rating_count": int(rating["count"]) if rating else 0,
            "_variants": variant_summaries,
            "_farm_slug": row["farm_slug"] or "",
            "_short_description": row["short_description"] or "",
        }

    async def _assemble(
        self,
        rows: list[dict[str, Any]],
        country: str | None = None,
        *,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        ids = [row["id"] for row in rows]
        variants = await self._variants_for(ids)
        certifications = await self._certifications_for(ids)
        tags = await self._tags_for(ids)
        adjustments = await resolve_adjustments(self._db, ids, country)
        ratings = await self._ratings_for(ids)
        summaries = [
            self._summarize(
                row,
                variants.get(row["id"], []),
                certifications.get(row["id"], []),
                tags.get(row["id"], []),
                adjustments.get(row["id"], 0),
                ratings.get(row["id"]),
            )
            for row in rows
        ]
        return await self._translate_summaries(summaries, locale)

    async def _translate_summaries(
        self, summaries: list[dict[str, Any]], locale: str | None
    ) -> list[dict[str, Any]]:
        """Swap in a translated `name`/`short_description` (migration 0068)
        over each summary's English values, in one batched lookup -- the same
        reasoning `CategoryRepository._translate_rows` follows."""
        if not locale or locale == "en" or not summaries:
            return summaries
        fields_by_id = await EntityTranslationRepository(self._db).get_fields_map(
            "product", [summary["id"] for summary in summaries], locale
        )
        if not fields_by_id:
            return summaries
        translated = []
        for summary in summaries:
            fields = fields_by_id.get(summary["id"])
            if not fields:
                translated.append(summary)
                continue
            translated.append(
                {
                    **summary,
                    "name": fields.get("name") or summary["name"],
                    "farm_name": fields.get("farm_name") or summary["farm_name"],
                    "region": fields.get("region") or summary["region"],
                    "image_alt": fields.get("image_alt") or summary["image_alt"],
                    "_short_description": fields.get("short_description")
                    or summary["_short_description"],
                }
            )
        return translated

    async def list_published_by_rule(
        self,
        rule_json: dict[str, Any],
        *,
        country: str | None = None,
        limit: int = 24,
        offset: int = 0,
        locale: str | None = None,
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
        return await self._assemble(rows, country, locale=locale), total

    async def list_all_published(
        self,
        *,
        limit: int = 200,
        offset: int = 0,
        country: str | None = None,
        locale: str | None = None,
        diet_keys: list[str] | None = None,
        certification_slugs: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Every published product, newest first, one page at a time. Backs
        the storefront's shop grid, so it reflects admin publishes without any
        per-category rule. Returns `(page_of_products, total_published)`."""
        geo_sql, geo_params = geo_release_clause(country)
        diet_sql, diet_params = tag_filter_clause(diet_keys or [])
        cert_sql, cert_params = certification_filter_clause(certification_slugs or [])
        extra_sql = geo_sql + diet_sql + cert_sql
        extra_params = [*geo_params, *diet_params, *cert_params]
        count_row = await self._db.fetch_one(
            f"SELECT COUNT(*) AS cnt FROM products p WHERE p.status = 'published'{extra_sql}",
            extra_params,
        )
        total = int(count_row["cnt"]) if count_row else 0
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published'{extra_sql}"
            " ORDER BY p.updated_at DESC, p.name LIMIT ? OFFSET ?",
            (*extra_params, max(limit, 1), max(offset, 0)),
        )
        return await self._assemble(rows, country, locale=locale), total

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
        locale: str | None = None,
        diet_keys: list[str] | None = None,
        certification_slugs: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Products statically assigned to a category, one page at a time.
        Returns `(page_of_products, total_eligible)`, `total_eligible` clamped
        to `_STATIC_CATEGORY_POOL_LIMIT` for parity with the rule-based path."""
        geo_sql, geo_params = geo_release_clause(country)
        diet_sql, diet_params = tag_filter_clause(diet_keys or [])
        cert_sql, cert_params = certification_filter_clause(certification_slugs or [])
        extra_sql = geo_sql + diet_sql + cert_sql
        extra_params = [*geo_params, *diet_params, *cert_params]
        count_row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS cnt
            FROM products p
            JOIN product_categories pc ON pc.product_id = p.id
            WHERE pc.category_id = ? AND p.status = 'published'{extra_sql}
            """,
            (category_id, *extra_params),
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
            WHERE pc.category_id = ? AND p.status = 'published'{extra_sql}
            ORDER BY pc.sort_order, p.name
            LIMIT ? OFFSET ?
            """,
            (category_id, *extra_params, page_limit, safe_offset),
        )
        return await self._assemble(rows, country, locale=locale), total

    async def list_filter_facets(self) -> dict[str, list[dict[str, Any]]]:
        """The full vocabulary for the shop grid's dietary/certification
        filters -- every `tag_group = 'diet'` tag and every certification,
        not just ones currently assigned to a published product, so a
        just-added diet tag with no products yet still shows up as a
        selectable (if momentarily empty) filter option."""
        diet_rows = await self._db.fetch_all(
            "SELECT key, label FROM tags WHERE tag_group = 'diet' ORDER BY label"
        )
        certification_rows = await self._db.fetch_all(
            "SELECT slug, name FROM certifications ORDER BY name"
        )
        return {"diet_tags": diet_rows, "certifications": certification_rows}

    async def list_published_by_slugs(
        self, slugs: list[str], country: str | None = None, *, locale: str | None = None
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
        summaries = await self._assemble(rows, country, locale=locale)
        order = {slug: index for index, slug in enumerate(slugs)}
        return sorted(summaries, key=lambda item: order.get(item["slug"], len(order)))

    async def list_bestsellers(
        self,
        *,
        limit: int = 8,
        exclude_slugs: list[str] | None = None,
        category_slug: str | None = None,
        country: str | None = None,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        """Real sellers, ranked by total quantity sold on non-cancelled
        orders -- nothing here is curated, so there is no list for an editor
        to keep stocked or let go stale. `exclude_slugs` lets a caller
        already showing a product (a basket's line items, a product detail
        page) drop it from its own "you might also like" row."""
        exclusions = exclude_slugs or []
        exclude_sql = ""
        params: list[Any] = []
        if exclusions:
            placeholders = ", ".join("?" for _ in exclusions)
            exclude_sql = (
                " AND NOT EXISTS (SELECT 1 FROM products ep"
                f" WHERE ep.id = oi.product_id AND ep.slug IN ({placeholders}))"
            )
            params.extend(exclusions)
        category_sql = ""
        if category_slug:
            category_sql = (
                " AND EXISTS (SELECT 1 FROM product_categories pc"
                " JOIN categories c ON c.id = pc.category_id"
                " WHERE pc.product_id = oi.product_id AND c.slug = ?)"
            )
            params.append(category_slug)
        params.append(max(limit, 1))
        ranked = await self._db.fetch_all(
            f"""
            SELECT oi.product_id, SUM(oi.quantity) AS total_qty
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.order_status != 'cancelled' AND oi.product_id IS NOT NULL
            {exclude_sql}{category_sql}
            GROUP BY oi.product_id
            ORDER BY total_qty DESC
            LIMIT ?
            """,
            tuple(params),
        )
        return await self._resolve_ranked(
            [row["product_id"] for row in ranked], country=country, locale=locale
        )

    async def list_also_bought(
        self,
        product_id: str,
        *,
        limit: int = 6,
        country: str | None = None,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        """Products that show up in the same orders as `product_id`, most
        frequent first -- real co-purchase counts (market-basket analysis),
        not a curated "goes well with" list. Empty for a product with no
        order history yet; the caller renders nothing rather than a section
        with an empty story to tell."""
        ranked = await self._db.fetch_all(
            """
            SELECT oi2.product_id, COUNT(DISTINCT oi1.order_id) AS co_count
            FROM order_items oi1
            JOIN order_items oi2
              ON oi2.order_id = oi1.order_id AND oi2.product_id != oi1.product_id
            JOIN orders o ON o.id = oi1.order_id
            WHERE oi1.product_id = ? AND o.order_status != 'cancelled'
              AND oi2.product_id IS NOT NULL
            GROUP BY oi2.product_id
            ORDER BY co_count DESC
            LIMIT ?
            """,
            (product_id, max(limit, 1)),
        )
        return await self._resolve_ranked(
            [row["product_id"] for row in ranked], country=country, locale=locale
        )

    async def _resolve_ranked(
        self,
        product_ids: list[str],
        *,
        country: str | None = None,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        """Turn a ranked list of product ids into full, published,
        geo-visible `ProductSummary` rows, preserving rank order -- the same
        "resolve then reorder" shape `list_published_by_slugs` uses, since a
        plain `IN (...)` gives no ordering guarantee of its own."""
        if not product_ids:
            return []
        placeholders = ", ".join("?" for _ in product_ids)
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.status = 'published'"
            f" AND p.id IN ({placeholders}){geo_sql}",
            (*product_ids, *geo_params),
        )
        summaries = await self._assemble(rows, country, locale=locale)
        order = {product_id: index for index, product_id in enumerate(product_ids)}
        return sorted(summaries, key=lambda item: order.get(item["id"], len(order)))

    async def resolve_ranked_product_ids(
        self,
        product_ids: list[str],
        *,
        country: str | None = None,
        locale: str | None = None,
    ) -> list[dict[str, Any]]:
        """Public service boundary for pre-ranked recommendation rollups."""
        return await self._resolve_ranked(product_ids, country=country, locale=locale)

    async def list_highlighted(
        self, country: str | None = None, *, limit: int = 12, locale: str | None = None
    ) -> list[dict[str, Any]]:
        """The owner-curated highlight slots, in curated order. Published and
        geo-visible products only, so a swap in the admin is all it takes.
        `limit` is the admin-adjustable curated-list cap
        (`load_curated_max_items`), not a hardcoded row count -- the caller
        resolves it."""
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"""
            {_PRODUCT_BASE_SQL}
            JOIN highlighted_products hp ON hp.product_id = p.id
            WHERE p.status = 'published'{geo_sql}
            ORDER BY hp.sort_order, p.name
            LIMIT ?
            """,
            (*geo_params, max(limit, 1)),
        )
        return await self._assemble(rows, country, locale=locale)

    async def get_published_detail(
        self, slug: str, country: str | None = None, *, locale: str | None = None
    ) -> dict[str, Any] | None:
        geo_sql, geo_params = geo_release_clause(country)
        rows = await self._db.fetch_all(
            f"{_PRODUCT_BASE_SQL} WHERE p.slug = ? AND p.status = 'published'{geo_sql} LIMIT 1",
            (slug, *geo_params),
        )
        if not rows:
            return None
        summary = (await self._assemble(rows, country, locale=locale))[0]
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

        farm_name = summary["farm_name"]

        translated_fields: dict[str, Any] = {}
        if locale and locale != "en":
            saved = await EntityTranslationRepository(self._db).get("product", row["id"], locale)
            if saved:
                translated_fields = saved["fields"]

        detail = dict(summary)
        detail.update(
            {
                "short_description": summary["_short_description"],
                "overview": summary["_short_description"],
                "farm_slug": summary["_farm_slug"],
                "storage_guidance": translated_fields.get("storage_guidance")
                or row["storage_guidance"]
                or "",
                "harvest_note": translated_fields.get("harvest_note") or row["harvest_note"] or "",
                "growing_method": translated_fields.get("growing_method")
                or row["growing_method"]
                or "",
                "variants": summary["_variants"],
                "traceability": [
                    {"label": "Farm", "detail": f"{farm_name} — {summary['region']}"},
                    {
                        "label": "Certification",
                        "detail": ", ".join(summary["certifications"]) or "In review",
                    },
                    {
                        "label": "Quality check",
                        "detail": "Checked at the fulfilment centre before dispatch",
                    },
                    {"label": "Delivery", "detail": "Shipped with full lot traceability"},
                ],
                "related_slugs": [entry["slug"] for entry in related],
                "return_eligible": bool(row["return_eligible"]),
                "seo": {
                    # `summary["name"]` carries the saved translation; `row`
                    # is the raw English record, so reading the name from it
                    # here left a translated product page under an English
                    # browser title.
                    "title": translated_fields.get("seo_title")
                    or row["seo_title"]
                    or summary["name"],
                    "description": translated_fields.get("seo_description")
                    or row["seo_description"]
                    or summary["_short_description"],
                    "canonical_path": f"/product/{row['slug']}",
                    "indexing": "index",
                },
            }
        )
        for key in ("_variants", "_farm_slug", "_short_description"):
            detail.pop(key, None)
        detail["images"] = await self.list_images(row["id"])
        return detail

    async def list_images(self, product_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT id, image_url, image_alt, sort_order FROM product_images"
            " WHERE product_id = ? ORDER BY sort_order, id",
            (product_id,),
        )

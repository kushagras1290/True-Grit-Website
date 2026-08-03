#!/usr/bin/env python3
"""Generate the no-API storefront catalogue from the development database seed.

The checked-in JSON keeps demo mode useful without making TypeScript fixtures a
second hand-maintained catalogue. Run ``corepack pnpm catalogue:fixtures``
whenever catalogue seed data changes.
"""

from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "database" / "migrations"
SEED = ROOT / "database" / "seeds" / "development.sql"
OUTPUT = ROOT / "packages" / "contracts" / "src" / "catalogue.generated.json"


def availability(available: int, reorder_threshold: int) -> str:
    if available <= 0:
        return "out_of_stock"
    if available <= reorder_threshold:
        return "low_stock"
    return "in_stock"


def load_database() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    for migration in sorted(MIGRATIONS.glob("*.sql")):
        connection.executescript(migration.read_text(encoding="utf-8"))
    connection.executescript(SEED.read_text(encoding="utf-8"))
    return connection


def category_rows(connection: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT c.id, c.name, c.slug, c.short_description, c.theme_key,
               c.season_label, c.hero_image_url, c.parent_id, c.level,
               c.sort_order, COALESCE(parent.sort_order, c.sort_order) AS root_order,
               COUNT(DISTINCT CASE WHEN p.status = 'published' THEN p.id END) AS product_count
        FROM categories c
        LEFT JOIN categories parent ON parent.id = c.parent_id
        LEFT JOIN product_categories pc ON pc.category_id = c.id
        LEFT JOIN products p ON p.id = pc.product_id
        WHERE c.status = 'published' AND c.visibility = 'public'
        GROUP BY c.id
        ORDER BY root_order, c.level, c.sort_order, c.name
        """
    ).fetchall()
    return [
        {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "shortDescription": row["short_description"]
            or f"Shop {row['name'].lower()}.",
            "themeKey": row["theme_key"] or "forest",
            "seasonLabel": row["season_label"],
            "imageUrl": row["hero_image_url"],
            "productCount": row["product_count"],
            "parentId": row["parent_id"],
            "level": row["level"],
        }
        for row in rows
    ]


def product_rows(
    connection: sqlite3.Connection,
) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    category_products: dict[str, list[str]] = defaultdict(list)
    product_categories: dict[str, list[str]] = defaultdict(list)
    assignments = connection.execute(
        """
        SELECT c.slug AS category_slug, p.id AS product_id, p.slug AS product_slug,
               pc.is_primary, pc.sort_order
        FROM product_categories pc
        JOIN categories c ON c.id = pc.category_id
        JOIN products p ON p.id = pc.product_id
        WHERE c.status = 'published' AND c.visibility = 'public'
          AND p.status = 'published'
        ORDER BY c.slug, pc.is_primary DESC, pc.sort_order, p.name
        """
    ).fetchall()
    for row in assignments:
        category_products[row["category_slug"]].append(row["product_slug"])
        product_categories[row["product_id"]].append(row["category_slug"])

    certifications: dict[str, str] = {}
    for row in connection.execute(
        """
        SELECT pc.product_id, c.name
        FROM product_certifications pc
        JOIN certifications c ON c.id = pc.certification_id
        WHERE pc.claim_review_state = 'approved'
        ORDER BY c.name
        """
    ):
        certifications.setdefault(row["product_id"], row["name"])

    tags: dict[str, list[str]] = defaultdict(list)
    for row in connection.execute(
        """
        SELECT pt.product_id, t.label
        FROM product_tags pt JOIN tags t ON t.id = pt.tag_id
        ORDER BY t.label
        """
    ):
        tags[row["product_id"]].append(row["label"])

    variants: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in connection.execute(
        """
        SELECT v.id, v.product_id, v.name, v.sku, v.sort_order,
               COALESCE(vp.list_amount_minor, 0) AS list_amount_minor,
               vp.sale_amount_minor,
               COALESCE(SUM(il.on_hand - il.reserved), 0) AS available,
               COALESCE(MIN(il.reorder_threshold), 0) AS reorder_threshold
        FROM product_variants v
        LEFT JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
        LEFT JOIN inventory_levels il ON il.variant_id = v.id
        WHERE v.status = 'active'
        GROUP BY v.id
        ORDER BY v.product_id, v.sort_order, v.name
        """
    ):
        variants[row["product_id"]].append(
            {
                "id": row["id"],
                "name": row["name"],
                "sku": row["sku"],
                "listMinor": row["list_amount_minor"],
                "saleMinor": row["sale_amount_minor"],
                "adjustedMinor": None,
                "availability": availability(
                    row["available"], row["reorder_threshold"]
                ),
            }
        )

    rows = connection.execute(
        """
        SELECT p.id, p.name, p.slug, p.short_description, p.seo_title,
               p.seo_description, p.indexing_policy, p.return_eligible,
               p.accepts_orders, f.name AS farm_name, f.slug AS farm_slug,
               f.region, COALESCE(NULLIF(p.image_alt, ''), m.alt_text, p.name) AS image_alt,
               COALESCE(
                 CASE WHEN m.object_key IS NOT NULL THEN '/media/' || m.object_key END,
                 NULLIF(p.image_url, '')
               ) AS image_url
        FROM products p
        LEFT JOIN farms f ON f.id = p.farm_id
        LEFT JOIN media_assets m ON m.id = p.primary_media_id
        WHERE p.status = 'published'
        ORDER BY p.updated_at DESC, p.name
        """
    ).fetchall()

    products: list[dict[str, Any]] = []
    for row in rows:
        product_variants = variants[row["id"]]
        lead = product_variants[0] if product_variants else None
        statuses = {variant["availability"] for variant in product_variants}
        overall_availability = (
            "in_stock"
            if "in_stock" in statuses
            else "low_stock"
            if "low_stock" in statuses
            else "out_of_stock"
        )
        assigned_slugs = product_categories[row["id"]]
        related: list[str] = []
        for category_slug in assigned_slugs:
            for candidate in category_products[category_slug]:
                if candidate != row["slug"] and candidate not in related:
                    related.append(candidate)
                if len(related) == 4:
                    break
            if len(related) == 4:
                break

        description = (
            row["short_description"] or f"{row['name']} selected for everyday use."
        )
        certification = certifications.get(row["id"], "Producer verified")
        products.append(
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "priceMinor": lead["listMinor"] if lead else 0,
                "saleMinor": lead["saleMinor"] if lead else None,
                "unitLabel": lead["name"] if lead else "",
                "availability": overall_availability,
                "tags": tags[row["id"]],
                "imageUrl": row["image_url"],
                "imageAlt": row["image_alt"],
                "acceptsOrders": bool(row["accepts_orders"]),
                "leadVariantId": lead["id"] if lead else None,
                "leadSku": lead["sku"] if lead else "",
                "variants": product_variants,
                "shortDescription": description,
                "certification": certification,
                "relatedSlugs": related,
                "returnEligible": bool(row["return_eligible"]),
                "seoTitle": row["seo_title"] or row["name"],
                "seoDescription": row["seo_description"] or description,
                "indexing": row["indexing_policy"],
            }
        )
    return products, dict(category_products)


def main() -> int:
    connection = load_database()
    categories = category_rows(connection)
    products, category_products = product_rows(connection)
    payload = {
        "generatedFrom": "database/seeds/development.sql",
        "categories": categories,
        "products": products,
        "categoryProducts": category_products,
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"wrote {OUTPUT.relative_to(ROOT)}: "
        f"{len(categories)} categories, {len(products)} products"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

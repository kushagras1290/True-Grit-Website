#!/usr/bin/env python3
"""Validate D1 migrations against a clean SQLite database.

Mirrors what `wrangler d1 migrations apply --local` will do, without requiring
Cloudflare credentials. Applies every migration in order, runs foreign-key and
integrity checks, then applies the development seed.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MIGRATIONS = ROOT / "database" / "migrations"
SEED = ROOT / "database" / "seeds" / "development.sql"


def main() -> int:
    migrations = sorted(MIGRATIONS.glob("*.sql"))
    if not migrations:
        print("No migrations found", file=sys.stderr)
        return 1

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")

    for migration in migrations:
        sql = migration.read_text(encoding="utf-8")
        try:
            conn.executescript(sql)
        except sqlite3.Error as exc:
            print(f"FAILED {migration.name}: {exc}", file=sys.stderr)
            return 1
        print(f"applied {migration.name}")

    violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
    if violations:
        print(f"foreign_key_check violations: {violations}", file=sys.stderr)
        return 1

    integrity = conn.execute("PRAGMA integrity_check;").fetchone()
    if integrity != ("ok",):
        print(f"integrity_check failed: {integrity}", file=sys.stderr)
        return 1

    # Migration 0056 is deliberately customer-facing data, not development
    # fixture content. Prove the products exist before development.sql runs.
    migrated_customer_categories = conn.execute(
        "SELECT COUNT(*) FROM categories"
        " WHERE id LIKE 'cat_complete_%' OR id LIKE 'cat_mass_%'"
    ).fetchone()[0]
    migrated_customer_products = conn.execute(
        "SELECT COUNT(*) FROM products"
        " WHERE id LIKE 'prd_complete_%' OR id LIKE 'prd_mass_%'"
    ).fetchone()[0]
    if migrated_customer_categories != 108 or migrated_customer_products != 1152:
        print(
            "customer catalogue must be migration-backed before seed data runs: "
            f"found {migrated_customer_categories} categories and "
            f"{migrated_customer_products} products",
            file=sys.stderr,
        )
        return 1

    if SEED.exists():
        try:
            conn.executescript(SEED.read_text(encoding="utf-8"))
        except sqlite3.Error as exc:
            print(f"FAILED seed {SEED.name}: {exc}", file=sys.stderr)
            return 1
        print(f"applied seed {SEED.name}")

        violations = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if violations:
            print(f"seed foreign_key_check violations: {violations}", file=sys.stderr)
            return 1

        # Demo and review environments need a market broad enough to exercise
        # category navigation, pagination, search, inventory and checkout. Keep
        # the catalogue expansion complete rather than allowing rows that look
        # published but cannot actually be found or purchased.
        published_categories = conn.execute(
            "SELECT COUNT(*) FROM categories"
            " WHERE status = 'published' AND visibility = 'public'"
        ).fetchone()[0]
        published_products = conn.execute(
            "SELECT COUNT(*) FROM products WHERE status = 'published'"
        ).fetchone()[0]
        if published_categories < 242:
            print(
                f"expected at least 242 published categories, found {published_categories}",
                file=sys.stderr,
            )
            return 1
        if published_products < 1957:
            print(
                f"expected at least 1957 published products, found {published_products}",
                file=sys.stderr,
            )
            return 1

        catalogue_integrity_checks = {
            "category assignment": (
                "SELECT COUNT(*) FROM products p WHERE p.status = 'published'"
                " AND NOT EXISTS (SELECT 1 FROM product_categories pc"
                " WHERE pc.product_id = p.id)"
            ),
            "active variant": (
                "SELECT COUNT(*) FROM products p WHERE p.status = 'published'"
                " AND NOT EXISTS (SELECT 1 FROM product_variants v"
                " WHERE v.product_id = p.id AND v.status = 'active')"
            ),
            "active price": (
                "SELECT COUNT(*) FROM products p WHERE p.status = 'published'"
                " AND NOT EXISTS (SELECT 1 FROM product_variants v"
                " JOIN variant_prices vp ON vp.variant_id = v.id"
                " AND vp.status = 'active' WHERE v.product_id = p.id"
                " AND v.status = 'active')"
            ),
            "inventory": (
                "SELECT COUNT(*) FROM products p WHERE p.status = 'published'"
                " AND NOT EXISTS (SELECT 1 FROM product_variants v"
                " JOIN inventory_levels il ON il.variant_id = v.id"
                " WHERE v.product_id = p.id AND v.status = 'active')"
            ),
            "search index": (
                "SELECT COUNT(*) FROM products p WHERE p.status = 'published'"
                " AND NOT EXISTS (SELECT 1 FROM search_products s"
                " WHERE s.product_id = p.id)"
            ),
        }
        for requirement, query in catalogue_integrity_checks.items():
            missing = conn.execute(query).fetchone()[0]
            if missing:
                print(
                    f"{missing} published products lack {requirement}", file=sys.stderr
                )
                return 1

        # The editorial library deliberately matches the original visible
        # volume, but every family now has a reader job and quality floor.
        # These checks prevent the old cosmetic three-title generator (or a
        # one-author content dump) from quietly returning.
        articles = conn.execute(
            "SELECT a.id, a.title, a.slug, a.reading_minutes, a.author_user_id, v.content_json"
            " FROM articles a JOIN article_versions v ON v.id = a.published_version_id"
            " WHERE a.status = 'published' ORDER BY a.id"
        ).fetchall()
        if len(articles) != 201:
            print(f"expected 201 useful articles, found {len(articles)}", file=sys.stderr)
            return 1
        if len({row[1] for row in articles}) != len(articles) or len(
            {row[2] for row in articles}
        ) != len(articles):
            print("published article titles and slugs must be unique", file=sys.stderr)
            return 1
        author_count = len({row[4] for row in articles if row[4]})
        if author_count < 5:
            print(f"expected at least 5 article authors, found {author_count}", file=sys.stderr)
            return 1

        for article_id, title, _slug, reading_minutes, _author_id, raw_content in articles:
            if article_id == "art_millets" or article_id.startswith(
                ("art_library_", "art_expansion_")
            ):
                print(f"legacy generated article survived: {article_id}", file=sys.stderr)
                return 1
            content = json.loads(raw_content)
            blocks = content.get("blocks", [])
            faq_items = [
                item
                for block in blocks
                if block.get("type") == "faq"
                for item in block.get("props", {}).get("items", [])
            ]
            prose = [
                paragraph
                for block in blocks
                if block.get("type") == "rich_text"
                for paragraph in block.get("props", {}).get("paragraphs", [])
            ] + [str(item.get("answer", "")) for item in faq_items]
            word_count = len(" ".join(prose).split())
            if article_id.startswith("art_guide_"):
                quality_floor = (5, 350, 6)
            elif article_id.startswith("art_field_"):
                quality_floor = (5, 180, 4)
            elif article_id.startswith("art_case_"):
                quality_floor = (5, 180, 3)
            else:
                print(f"unexpected published article family: {article_id}", file=sys.stderr)
                return 1
            min_faq, min_words, min_minutes = quality_floor
            if (
                len(faq_items) < min_faq
                or word_count < min_words
                or reading_minutes < min_minutes
            ):
                print(f"article is too thin to publish: {title}", file=sys.stderr)
                return 1

        discussions = conn.execute(
            "SELECT id, title, body, author_user_id FROM discussions"
            " WHERE status = 'visible' ORDER BY id"
        ).fetchall()
        if len(discussions) != 200:
            print(f"expected 200 useful discussions, found {len(discussions)}", file=sys.stderr)
            return 1
        if any(row[0].startswith("dsc_expansion_") for row in discussions):
            print("legacy generated discussion survived", file=sys.stderr)
            return 1
        editorial_discussions = [
            row for row in discussions if row[0].startswith("dsc_editorial_")
        ]
        if len(editorial_discussions) != 100:
            print(
                f"expected 100 evidence-led discussions, found {len(editorial_discussions)}",
                file=sys.stderr,
            )
            return 1
        if any(len(row[2].split()) < 45 for row in editorial_discussions):
            print("editorial discussion prompt is too thin", file=sys.stderr)
            return 1
        if len({row[3] for row in discussions}) < 8:
            print("discussion library does not have enough distinct authors", file=sys.stderr)
            return 1

        home_content = conn.execute(
            "SELECT content_json FROM page_versions WHERE id ="
            " (SELECT published_version_id FROM pages WHERE id = 'pag_home')"
        ).fetchone()
        home_blocks = json.loads(home_content[0]).get("blocks", []) if home_content else []
        hero = next((block for block in home_blocks if block.get("type") == "hero"), None)
        slides = hero.get("props", {}).get("slides", []) if hero else []
        if len(slides) != 12:
            print(f"expected 12 homepage banners, found {len(slides)}", file=sys.stderr)
            return 1
        for slide in slides:
            image_url = str(slide.get("imageUrl", ""))
            asset = ROOT / "apps" / "storefront" / "public" / image_url.lstrip("/")
            if not image_url.startswith("/banners/home/") or not asset.is_file():
                print(f"missing homepage banner asset: {image_url}", file=sys.stderr)
                return 1

        category_banner_count = conn.execute(
            "SELECT COUNT(*) FROM categories"
            " WHERE status = 'published' AND hero_image_url LIKE '/banners/categories/%'"
        ).fetchone()[0]
        if category_banner_count < 30:
            print(
                f"expected category banner coverage, found {category_banner_count}",
                file=sys.stderr,
            )
            return 1

        customer_catalogue_departments = (
            "farm-fresh-proteins",
            "pasta-noodles-couscous",
            "soups-stocks-preserved",
            "juices-water-functional",
            "chocolate-confectionery",
            "regional-indian-pantry",
            "free-from-special-diet",
            "baby-care-parenting",
            "family-wellness-care",
            "kitchen-dining-storage",
            "bulk-refill-value",
            "meal-boxes-subscriptions",
        )
        for department_slug in customer_catalogue_departments:
            expected_url = f"/banners/categories/{department_slug}.webp"
            category = conn.execute(
                "SELECT hero_image_url FROM categories"
                " WHERE slug = ? AND status = 'published'",
                (department_slug,),
            ).fetchone()
            asset = ROOT / "apps" / "storefront" / "public" / expected_url.lstrip("/")
            if not category or category[0] != expected_url or not asset.is_file():
                print(
                    f"missing customer catalogue banner: {expected_url}",
                    file=sys.stderr,
                )
                return 1

    tables = conn.execute(
        "SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    ).fetchone()[0]
    print(f"OK: {len(migrations)} migrations, {tables} tables, foreign keys clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

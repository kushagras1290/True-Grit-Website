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

    # Cloud environments apply migrations without development.sql. They must
    # still have an owner for ADMIN_LOGIN_* to adopt, and that owner must hold
    # every permission that existed before the super-admin role was created.
    owner_count = conn.execute(
        "SELECT COUNT(*) FROM users u"
        " JOIN user_roles ur ON ur.user_id = u.id"
        " JOIN roles r ON r.id = ur.role_id"
        " WHERE u.user_type = 'staff' AND u.status = 'active'"
        " AND r.key = 'super_admin'"
    ).fetchone()[0]
    permission_count = conn.execute("SELECT COUNT(*) FROM permissions").fetchone()[0]
    owner_grant_count = conn.execute(
        "SELECT COUNT(*) FROM role_permissions rp"
        " JOIN roles r ON r.id = rp.role_id"
        " WHERE r.key = 'super_admin'"
    ).fetchone()[0]
    if owner_count < 1 or owner_grant_count != permission_count:
        print(
            "migration-only database must contain an active, fully granted super admin: "
            f"owners={owner_count}, grants={owner_grant_count}, permissions={permission_count}",
            file=sys.stderr,
        )
        return 1

    # The preferred image-backed catalogue is production data now, not a
    # fixture-only fallback. Prove the requested public count exists before
    # development.sql runs so a deployment cannot silently ship an empty shop.
    migrated_customer_categories = conn.execute(
        "SELECT COUNT(*) FROM categories"
        " WHERE status = 'published' AND visibility = 'public'"
    ).fetchone()[0]
    migrated_customer_products = conn.execute(
        "SELECT COUNT(*) FROM products WHERE status = 'published'"
    ).fetchone()[0]
    if migrated_customer_categories != 216 or migrated_customer_products != 1500:
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
        if published_categories != 216:
            print(
                f"expected 216 published categories, found {published_categories}",
                file=sys.stderr,
            )
            return 1
        if published_products != 1500:
            print(
                f"expected 1500 published products, found {published_products}",
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

        misleading_product_images = conn.execute(
            "SELECT COUNT(*) FROM products WHERE status = 'published'"
            " AND image_url LIKE '/banners/categories/%'"
        ).fetchone()[0]
        if misleading_product_images:
            print(
                f"{misleading_product_images} products use category artwork as a product image",
                file=sys.stderr,
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
        if len(articles) != 351:
            print(
                f"expected 351 useful articles, found {len(articles)}", file=sys.stderr
            )
            return 1
        if len({row[1] for row in articles}) != len(articles) or len(
            {row[2] for row in articles}
        ) != len(articles):
            print("published article titles and slugs must be unique", file=sys.stderr)
            return 1
        author_count = len({row[4] for row in articles if row[4]})
        if author_count < 5:
            print(
                f"expected at least 5 article authors, found {author_count}",
                file=sys.stderr,
            )
            return 1

        for (
            article_id,
            title,
            _slug,
            reading_minutes,
            _author_id,
            raw_content,
        ) in articles:
            if article_id == "art_millets" or article_id.startswith(
                ("art_library_", "art_expansion_")
            ):
                print(
                    f"legacy generated article survived: {article_id}", file=sys.stderr
                )
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
            elif article_id.startswith("art_practical_"):
                quality_floor = (5, 190, 6)
            elif article_id.startswith("art_fieldbook_"):
                quality_floor = (5, 175, 5)
            else:
                print(
                    f"unexpected published article family: {article_id}",
                    file=sys.stderr,
                )
                return 1
            min_faq, min_words, min_minutes = quality_floor
            if (
                len(faq_items) < min_faq
                or word_count < min_words
                or reading_minutes < min_minutes
            ):
                print(f"article is too thin to publish: {title}", file=sys.stderr)
                return 1

        recipes = conn.execute(
            "SELECT r.id, r.title, r.slug, rv.content_json,"
            " (SELECT COUNT(*) FROM recipe_ingredients ri WHERE ri.recipe_id = r.id)"
            " FROM recipes r JOIN recipe_versions rv ON rv.id = r.published_version_id"
            " WHERE r.status = 'published' ORDER BY r.id"
        ).fetchall()
        if len(recipes) != 551:
            print(f"expected 551 useful recipes, found {len(recipes)}", file=sys.stderr)
            return 1
        if len({row[1] for row in recipes}) != len(recipes) or len(
            {row[2] for row in recipes}
        ) != len(recipes):
            print("published recipe titles and slugs must be unique", file=sys.stderr)
            return 1
        practical_recipes = [
            row for row in recipes if row[0].startswith("rcp_practical_")
        ]
        if len(practical_recipes) != 250:
            print(
                f"expected 250 new practical recipes, found {len(practical_recipes)}",
                file=sys.stderr,
            )
            return 1
        for recipe_id, title, _slug, raw_content, ingredient_count in practical_recipes:
            content = json.loads(raw_content)
            steps = content.get("steps", [])
            if len(steps) != 6 or ingredient_count < 6:
                print(
                    f"recipe is not executable: {title} ({recipe_id})", file=sys.stderr
                )
                return 1
            if any(len(str(step).split()) < 8 for step in steps):
                print(
                    f"recipe step is too vague: {title} ({recipe_id})", file=sys.stderr
                )
                return 1

        discussions = conn.execute(
            "SELECT id, title, body, author_user_id FROM discussions"
            " WHERE status = 'visible' ORDER BY id"
        ).fetchall()
        if len(discussions) != 400:
            print(
                f"expected 400 useful discussions, found {len(discussions)}",
                file=sys.stderr,
            )
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
        practical_discussions = [
            row for row in discussions if row[0].startswith("dsc_practical_")
        ]
        if len(practical_discussions) != 200:
            print(
                f"expected 200 new practical discussions, found {len(practical_discussions)}",
                file=sys.stderr,
            )
            return 1
        if any(len(row[2].split()) < 55 for row in practical_discussions):
            print("practical discussion prompt is too thin", file=sys.stderr)
            return 1
        if len({row[3] for row in discussions}) < 8:
            print(
                "discussion library does not have enough distinct authors",
                file=sys.stderr,
            )
            return 1

        expanded_product_variant_gaps = conn.execute(
            "SELECT COUNT(*) FROM products p"
            " WHERE p.status = 'published'"
            " AND ("
            "   (SELECT COUNT(*) FROM product_variants v"
            "    WHERE v.product_id = p.id AND v.status = 'active') NOT BETWEEN 2 AND 5"
            "   OR EXISTS (SELECT 1 FROM product_variants v"
            "       WHERE v.product_id = p.id AND v.status = 'active'"
            "       AND NOT EXISTS (SELECT 1 FROM variant_prices vp"
            "         WHERE vp.variant_id = v.id AND vp.status = 'active'))"
            "   OR EXISTS (SELECT 1 FROM product_variants v"
            "       WHERE v.product_id = p.id AND v.status = 'active'"
            "       AND NOT EXISTS (SELECT 1 FROM inventory_levels il"
            "         WHERE il.variant_id = v.id))"
            " )"
        ).fetchone()[0]
        if expanded_product_variant_gaps:
            print(
                f"{expanded_product_variant_gaps} customer products fall outside 2-5 buyable variants",
                file=sys.stderr,
            )
            return 1

        home_content = conn.execute(
            "SELECT content_json FROM page_versions WHERE id ="
            " (SELECT published_version_id FROM pages WHERE id = 'pag_home')"
        ).fetchone()
        home_blocks = (
            json.loads(home_content[0]).get("blocks", []) if home_content else []
        )
        hero = next(
            (block for block in home_blocks if block.get("type") == "hero"), None
        )
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
        if category_banner_count != published_categories:
            print(
                "every public category must have a banner: "
                f"found {category_banner_count} for {published_categories}",
                file=sys.stderr,
            )
            return 1

        visible_image_urls = conn.execute(
            "SELECT DISTINCT image_url, 'product' AS image_kind FROM products"
            " WHERE status = 'published' AND NULLIF(TRIM(image_url), '') IS NOT NULL"
            " UNION SELECT DISTINCT hero_image_url, 'category' AS image_kind FROM categories"
            " WHERE status = 'published' AND visibility = 'public'"
            " AND NULLIF(TRIM(hero_image_url), '') IS NOT NULL"
        ).fetchall()
        for image_url, image_kind in visible_image_urls:
            asset = ROOT / "apps" / "storefront" / "public" / image_url.lstrip("/")
            expected_prefix = (
                "/products/" if image_kind == "product" else "/banners/categories/"
            )
            if not image_url.startswith(expected_prefix) or not asset.is_file():
                print(f"missing catalogue image asset: {image_url}", file=sys.stderr)
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
            category = conn.execute(
                "SELECT hero_image_url FROM categories"
                " WHERE slug = ? AND status = 'published'",
                (department_slug,),
            ).fetchone()
            if not category:
                print(
                    f"missing customer catalogue department: {department_slug}",
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

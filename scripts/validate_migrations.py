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

        # Editorial fixtures are intentionally small and substantive. These
        # checks prevent the old Cartesian-product blog generator (or another
        # batch of three-paragraph filler) from quietly returning.
        articles = conn.execute(
            "SELECT a.id, a.title, a.reading_minutes, v.content_json"
            " FROM articles a JOIN article_versions v ON v.id = a.published_version_id"
            " WHERE a.status = 'published' ORDER BY a.id"
        ).fetchall()
        if len(articles) != 7:
            print(f"expected 7 curated articles, found {len(articles)}", file=sys.stderr)
            return 1
        for article_id, title, reading_minutes, raw_content in articles:
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
            if len(faq_items) < 5 or len(" ".join(prose).split()) < 350 or reading_minutes < 6:
                print(f"article is too thin to publish: {title}", file=sys.stderr)
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

    tables = conn.execute(
        "SELECT count(*) FROM sqlite_schema WHERE type = 'table' AND name NOT LIKE 'sqlite_%';"
    ).fetchone()[0]
    print(f"OK: {len(migrations)} migrations, {tables} tables, foreign keys clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

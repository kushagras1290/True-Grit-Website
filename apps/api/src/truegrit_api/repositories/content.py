"""Content repositories: categories, pages, navigation, search."""

from __future__ import annotations

import json
import re
from typing import Any

from truegrit_api.platform.database import Database


class CategoryRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, name, slug, short_description, hero_eyebrow, hero_title,
                   hero_description, theme_key, season_label, product_assignment_mode,
                   product_rule_json, seo_title, seo_description, updated_at
            FROM categories
            WHERE slug = ? AND status = 'published' AND visibility = 'public'
            """,
            (slug,),
        )

    async def list_published(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT c.id, c.name, c.slug, c.short_description, c.theme_key, c.season_label,
                   (SELECT COUNT(*) FROM product_categories pc
                     JOIN products p ON p.id = pc.product_id
                    WHERE pc.category_id = c.id AND p.status = 'published') AS product_count
            FROM categories c
            WHERE c.status = 'published' AND c.visibility = 'public'
            ORDER BY c.sort_order, c.name
            """
        )

    async def get_by_id(self, category_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT * FROM categories WHERE id = ? AND archived_at IS NULL",
            (category_id,),
        )

    async def next_version_number(self, category_id: str) -> int:
        row = await self._db.fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) AS max_version"
            " FROM category_versions WHERE category_id = ?",
            (category_id,),
        )
        return int(row["max_version"]) + 1 if row else 1


class PageRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        page = await self._db.fetch_one(
            """
            SELECT p.id, p.slug, p.title, p.seo_title, p.seo_description,
                   p.indexing_policy, v.content_json
            FROM pages p
            JOIN page_versions v ON v.id = p.published_version_id
            WHERE p.slug = ? AND p.status = 'published'
            """,
            (slug,),
        )
        if page is None:
            return None
        content = json.loads(page["content_json"])
        return {
            "id": page["id"],
            "slug": page["slug"],
            "title": page["title"],
            "blocks": [block for block in content.get("blocks", []) if block.get("enabled", True)],
            "seo": {
                "title": page["seo_title"] or page["title"],
                "description": page["seo_description"] or "",
                "canonical_path": "/" if page["slug"] == "home" else f"/{page['slug']}",
                "indexing": page["indexing_policy"],
            },
        }


class NavigationRepository:
    def __init__(self, db: Database):
        self._db = db

    async def menu(self, key: str) -> list[dict[str, str]]:
        rows = await self._db.fetch_all(
            """
            SELECT ni.label, ni.destination_type, ni.destination_reference
            FROM navigation_items ni
            JOIN navigation_menus nm ON nm.id = ni.menu_id
            WHERE nm.key = ? AND ni.visible = 1 AND ni.parent_id IS NULL
            ORDER BY ni.sort_order
            """,
            (key,),
        )
        items: list[dict[str, str]] = []
        for row in rows:
            if row["destination_type"] == "category":
                path = f"/category/{row['destination_reference']}"
            elif row["destination_type"] == "internal_path":
                path = row["destination_reference"]
            else:
                path = row["destination_reference"]
            if not path.startswith("/"):
                continue  # external destinations are not rendered in primary navigation
            items.append({"label": row["label"], "path": path})
        return items

    async def active_announcement(self) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT message, destination_path AS path FROM announcements"
            " WHERE active = 1 ORDER BY updated_at DESC LIMIT 1"
        )


_FTS_SANITIZE = re.compile(r"[^\w\s-]", re.UNICODE)


class SearchRepository:
    def __init__(self, db: Database):
        self._db = db

    async def _expand_terms(self, query: str) -> list[str]:
        terms = [term for term in _FTS_SANITIZE.sub(" ", query).split() if len(term) >= 2][:6]
        if not terms:
            return []
        expanded = list(terms)
        placeholders = ", ".join("?" for _ in terms)
        rows = await self._db.fetch_all(
            f"SELECT synonym FROM search_synonyms WHERE term IN ({placeholders})",
            [term.lower() for term in terms],
        )
        expanded.extend(row["synonym"] for row in rows)
        return expanded

    async def search(self, query: str, limit: int = 20) -> dict[str, Any]:
        terms = await self._expand_terms(query)
        if not terms:
            return {"query": query, "total": 0, "groups": []}
        match = " OR ".join(f'"{term}"*' for term in terms)

        product_rows = await self._db.fetch_all(
            "SELECT product_id AS id, name, slug FROM search_products"
            " WHERE search_products MATCH ? LIMIT ?",
            (match, limit),
        )
        content_rows = await self._db.fetch_all(
            "SELECT entity_type, entity_id AS id, title AS name, slug FROM search_content"
            " WHERE search_content MATCH ? LIMIT ?",
            (match, limit),
        )

        groups: list[dict[str, Any]] = []
        if product_rows:
            groups.append(
                {
                    "group": "products",
                    "items": [
                        {"id": row["id"], "name": row["name"], "path": f"/product/{row['slug']}"}
                        for row in product_rows
                    ],
                }
            )
        content_paths = {"article": "/journal/", "recipe": "/recipes/", "farm": "/farms/"}
        for entity_type, base_path in content_paths.items():
            matched = [row for row in content_rows if row["entity_type"] == entity_type]
            if matched:
                groups.append(
                    {
                        "group": f"{entity_type}s",
                        "items": [
                            {"id": row["id"], "name": row["name"], "path": base_path + row["slug"]}
                            for row in matched
                        ],
                    }
                )

        total = sum(len(group["items"]) for group in groups)
        return {"query": query, "total": total, "groups": groups}


class AuditRepository:
    def __init__(self, db: Database):
        self._db = db

    async def recent(self, limit: int = 50) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT a.id, COALESCE(u.display_name, 'system') AS actor_name, a.action,
                   a.entity_type, a.entity_id, a.request_id, a.created_at
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.actor_user_id
            ORDER BY a.created_at DESC
            LIMIT ?
            """,
            (min(max(limit, 1), 200),),
        )

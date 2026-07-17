"""Content repositories: categories, pages, navigation, search."""

from __future__ import annotations

import json
import re
from typing import Any

from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import geo_release_clause


class CategoryRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, name, slug, short_description, hero_eyebrow, hero_title,
                   hero_description, theme_key, season_label, product_assignment_mode,
                   product_rule_json, seo_title, seo_description, hero_image_url,
                   hero_image_alt, updated_at
            FROM categories
            WHERE slug = ? AND status = 'published' AND visibility = 'public'
            """,
            (slug,),
        )

    async def list_published(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT c.id, c.name, c.slug, c.short_description, c.theme_key, c.season_label,
                   c.hero_image_url,
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
            SELECT p.id, p.slug, p.title, p.seo_title, p.seo_description, p.seo_keywords,
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
                "keywords": page["seo_keywords"],
                "canonical_path": "/" if page["slug"] == "home" else f"/{page['slug']}",
                "indexing": page["indexing_policy"],
            },
        }


class FarmRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.story_json,
                   f.established_year, f.seo_title, f.seo_description,
                   (
                     SELECT c.name
                     FROM farm_certifications fc
                     JOIN certifications c ON c.id = fc.certification_id
                     WHERE fc.farm_id = f.id AND fc.verification_status = 'verified'
                     ORDER BY fc.valid_until DESC
                     LIMIT 1
                   ) AS certification
            FROM farms f
            WHERE f.status = 'published'
            ORDER BY f.name
            """
        )
        return [await self._detail_from_row(row) for row in rows]

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.story_json,
                   f.established_year, f.seo_title, f.seo_description,
                   (
                     SELECT c.name
                     FROM farm_certifications fc
                     JOIN certifications c ON c.id = fc.certification_id
                     WHERE fc.farm_id = f.id AND fc.verification_status = 'verified'
                     ORDER BY fc.valid_until DESC
                     LIMIT 1
                   ) AS certification
            FROM farms f
            WHERE f.slug = ? AND f.status = 'published'
            """,
            (slug,),
        )
        if row is None:
            return None
        return await self._detail_from_row(row)

    async def _detail_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        story = json.loads(row["story_json"] or "{}")
        if not isinstance(story, dict):
            story = {}
        summary = str(story.get("summary") or "")
        body = str(story.get("body") or summary)
        methods = story.get("methods")
        product_rows = await self._db.fetch_all(
            "SELECT slug FROM products WHERE farm_id = ? AND status = 'published' ORDER BY name",
            (row["id"],),
        )
        return {
            "id": row["id"],
            "name": row["name"],
            "slug": row["slug"],
            "farmer_name": row["farmer_name"] or "",
            "region": row["region"] or "",
            "summary": summary,
            "certification": row["certification"] or "Verified farm",
            "established_year": int(row["established_year"] or 0),
            "story": body,
            "methods": [str(method) for method in methods] if isinstance(methods, list) else [],
            "product_slugs": [entry["slug"] for entry in product_rows],
            "seo": {
                "title": row["seo_title"] or row["name"],
                "description": row["seo_description"] or summary,
                "canonical_path": f"/farms/{row['slug']}",
                "indexing": "index",
            },
        }


class RecipeRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT id, title, slug, excerpt, prep_minutes, cook_minutes, servings,
                   dietary_tags_json, published_version_id, seo_title, seo_description
            FROM recipes
            WHERE status = 'published'
            ORDER BY published_at DESC, title
            """
        )
        return [await self._detail_from_row(row) for row in rows]

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT id, title, slug, excerpt, prep_minutes, cook_minutes, servings,
                   dietary_tags_json, published_version_id, seo_title, seo_description
            FROM recipes
            WHERE slug = ? AND status = 'published'
            """,
            (slug,),
        )
        if row is None:
            return None
        return await self._detail_from_row(row)

    async def _detail_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        version = None
        if row["published_version_id"]:
            version = await self._db.fetch_one(
                "SELECT content_json FROM recipe_versions WHERE id = ?",
                (row["published_version_id"],),
            )
        content = json.loads(version["content_json"]) if version else {}
        ingredients = await self._db.fetch_all(
            """
            SELECT ri.label, ri.quantity_text, p.slug AS product_slug
            FROM recipe_ingredients ri
            LEFT JOIN products p ON p.id = ri.product_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.sort_order, ri.label
            """,
            (row["id"],),
        )
        tags = json.loads(row["dietary_tags_json"] or "[]")
        steps = content.get("steps") if isinstance(content, dict) else []
        return {
            "id": row["id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"] or "",
            "prep_minutes": int(row["prep_minutes"] or 0),
            "cook_minutes": int(row["cook_minutes"] or 0),
            "servings": int(row["servings"] or 0),
            "dietary_tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
            "ingredients": [
                {
                    "label": entry["label"],
                    "quantity_text": entry["quantity_text"] or "",
                    "product_slug": entry["product_slug"],
                }
                for entry in ingredients
            ],
            "steps": [str(step) for step in steps] if isinstance(steps, list) else [],
            "seo": {
                "title": row["seo_title"] or row["title"],
                "description": row["seo_description"] or row["excerpt"] or "",
                "canonical_path": f"/recipes/{row['slug']}",
                "indexing": "index",
            },
        }


class ArticleRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT a.id, a.title, a.slug, a.excerpt, a.reading_minutes, a.published_at,
                   a.published_version_id, a.seo_title, a.seo_description,
                   COALESCE(u.display_name, 'True Grit') AS author_name
            FROM articles a
            LEFT JOIN users u ON u.id = a.author_user_id
            WHERE a.status = 'published'
            ORDER BY a.published_at DESC, a.title
            """
        )
        return [await self._detail_from_row(row) for row in rows]

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT a.id, a.title, a.slug, a.excerpt, a.reading_minutes, a.published_at,
                   a.published_version_id, a.seo_title, a.seo_description,
                   COALESCE(u.display_name, 'True Grit') AS author_name
            FROM articles a
            LEFT JOIN users u ON u.id = a.author_user_id
            WHERE a.slug = ? AND a.status = 'published'
            """,
            (slug,),
        )
        if row is None:
            return None
        return await self._detail_from_row(row)

    async def _detail_from_row(self, row: dict[str, Any]) -> dict[str, Any]:
        version = None
        if row["published_version_id"]:
            version = await self._db.fetch_one(
                "SELECT content_json FROM article_versions WHERE id = ?",
                (row["published_version_id"],),
            )
        content = json.loads(version["content_json"]) if version else {}
        body = content.get("body") if isinstance(content, dict) else []
        return {
            "id": row["id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"] or "",
            "author_name": row["author_name"],
            "published_at": row["published_at"] or "",
            "reading_minutes": int(row["reading_minutes"] or 1),
            "body": [str(paragraph) for paragraph in body] if isinstance(body, list) else [],
            "pull_quote": content.get("pullQuote") if isinstance(content, dict) else None,
            "seo": {
                "title": row["seo_title"] or row["title"],
                "description": row["seo_description"] or row["excerpt"] or "",
                "canonical_path": f"/journal/{row['slug']}",
                "indexing": "index",
            },
        }


class SiteDocumentRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get(self, key: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT key, content, content_type, updated_at FROM site_documents WHERE key = ?",
            (key,),
        )

    async def list(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT key, content, content_type, updated_at FROM site_documents ORDER BY key"
        )


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
        normalized = _FTS_SANITIZE.sub(" ", query).lower()
        terms = [term for term in normalized.split() if len(term) >= 2][:6]
        if not terms:
            return []
        # Synonyms expand in both directions: a query for "ragi" should also
        # match "finger millet", and a query phrased as "finger millet" (the
        # synonym, possibly multi-word) should match "ragi". The table is tiny,
        # so scan it rather than juggle phrase placeholders.
        expanded = list(terms)
        rows = await self._db.fetch_all("SELECT term, synonym FROM search_synonyms")
        for row in rows:
            term = row["term"].lower()
            synonym = row["synonym"].lower()
            if term in terms and synonym not in expanded:
                expanded.append(synonym)
            if synonym in normalized and term not in expanded:
                expanded.append(term)
        return expanded

    async def search(
        self, query: str, limit: int = 20, country: str | None = None
    ) -> dict[str, Any]:
        terms = await self._expand_terms(query)
        if not terms:
            return {"query": query, "total": 0, "groups": []}
        match = " OR ".join(f'"{term}"*' for term in terms)

        # Products are searched against the live catalogue (not the FTS shadow
        # table, which only the seed populates) so results always reflect what
        # is actually published — and only what is released in the visitor's
        # country.
        term_clause = " OR ".join(
            "(p.name LIKE ? OR p.slug LIKE ? OR p.short_description LIKE ?"
            " OR f.name LIKE ? OR t.label LIKE ?)"
            for _ in terms
        )
        term_params: list[Any] = []
        for term in terms:
            like = f"%{term}%"
            term_params.extend([like, like, like, like, like])
        geo_sql, geo_params = geo_release_clause(country)
        product_rows = await self._db.fetch_all(
            f"""
            SELECT DISTINCT p.id, p.name, p.slug
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN product_tags pt ON pt.product_id = p.id
            LEFT JOIN tags t ON t.id = pt.tag_id
            WHERE p.status = 'published' AND ({term_clause}){geo_sql}
            ORDER BY p.name
            LIMIT ?
            """,
            (*term_params, *geo_params, limit),
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
                        {
                            "id": row["id"],
                            "name": row["name"],
                            "slug": row["slug"],
                            "path": f"/product/{row['slug']}",
                        }
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

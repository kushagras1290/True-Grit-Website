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

    async def get_published_by_slug(
        self, slug: str, country: str | None = None
    ) -> dict[str, Any] | None:
        geo_sql, geo_params = geo_release_clause(
            country, alias="categories", table="category_release_countries", id_column="category_id"
        )
        return await self._db.fetch_one(
            f"""
            SELECT id, name, slug, short_description, hero_eyebrow, hero_title,
                   hero_description, theme_key, season_label, product_assignment_mode,
                   product_rule_json, seo_title, seo_description, hero_image_url,
                   hero_image_alt, updated_at
            FROM categories
            WHERE slug = ? AND status = 'published' AND visibility = 'public'{geo_sql}
            """,
            (slug, *geo_params),
        )

    async def list_published(self, country: str | None = None) -> list[dict[str, Any]]:
        geo_sql, geo_params = geo_release_clause(
            country, alias="c", table="category_release_countries", id_column="category_id"
        )
        return await self._db.fetch_all(
            f"""
            SELECT c.id, c.name, c.slug, c.short_description, c.theme_key, c.season_label,
                   c.hero_image_url,
                   (SELECT COUNT(*) FROM product_categories pc
                     JOIN products p ON p.id = pc.product_id
                    WHERE pc.category_id = c.id AND p.status = 'published') AS product_count
            FROM categories c
            WHERE c.status = 'published' AND c.visibility = 'public'{geo_sql}
            ORDER BY c.sort_order, c.name
            """,
            tuple(geo_params),
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

    async def list_published(self) -> list[dict[str, Any]]:
        """Slug + updated_at for every publicly visible page — the sitemap's
        only source for CMS pages, so a newly published page appears without
        any code change."""
        return await self._db.fetch_all(
            "SELECT slug, updated_at FROM pages WHERE status = 'published' ORDER BY slug"
        )


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


_RECIPE_PUBLIC_COLUMNS = """
    id, title, slug, excerpt, prep_minutes, cook_minutes, servings,
    dietary_tags_json, published_version_id, seo_title, seo_description,
    seo_keywords, canonical_url, indexing_policy
"""


class RecipeRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            f"""
            SELECT {_RECIPE_PUBLIC_COLUMNS}
            FROM recipes
            WHERE status = 'published'
            ORDER BY published_at DESC, title
            """
        )
        return [await self._detail_from_row(row) for row in rows]

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            f"""
            SELECT {_RECIPE_PUBLIC_COLUMNS}
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
        blocks = content.get("blocks") if isinstance(content, dict) else []
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
            "blocks": [b for b in blocks if isinstance(b, dict) and b.get("enabled", True)]
            if isinstance(blocks, list)
            else [],
            "steps": [str(step) for step in steps] if isinstance(steps, list) else [],
            "seo": {
                "title": row["seo_title"] or row["title"],
                "description": row["seo_description"] or row["excerpt"] or "",
                "keywords": row["seo_keywords"],
                "canonical_path": row["canonical_url"] or f"/recipes/{row['slug']}",
                "indexing": row["indexing_policy"],
            },
        }

    async def list_admin(
        self,
        *,
        chef_user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Admin listing. `chef_user_id` scopes results to one chef's own
        recipes — the caller only passes it for principals without
        `recipes.approve` (i.e. the `chef` role), never for reviewers."""
        like = f"%{search}%" if search else None
        return await self._db.fetch_all(
            """
            SELECT r.id, r.title, r.slug, r.status, r.updated_at, r.published_at,
                   COALESCE(u.display_name, 'Unassigned') AS chef_name,
                   (SELECT MAX(version_number) FROM recipe_versions WHERE recipe_id = r.id)
                     AS latest_version_number,
                   (SELECT version_number FROM recipe_versions WHERE id = r.published_version_id)
                     AS published_version_number
            FROM recipes r
            LEFT JOIN users u ON u.id = r.chef_user_id
            WHERE (? IS NULL OR r.chef_user_id = ?)
              AND (? IS NULL OR r.title LIKE ? OR r.slug LIKE ? OR r.excerpt LIKE ?)
            ORDER BY r.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (
                chef_user_id,
                chef_user_id,
                like,
                like,
                like,
                like,
                min(max(limit, 1), 100),
                max(offset, 0),
            ),
        )

    async def get_admin_detail(self, recipe_id: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT r.id, r.title, r.slug, r.excerpt, r.prep_minutes, r.cook_minutes,
                   r.servings, r.dietary_tags_json, r.status, r.chef_user_id,
                   r.seo_title, r.seo_description, r.seo_keywords, r.canonical_url,
                   r.indexing_policy, r.updated_at, r.published_version_id,
                   COALESCE(latest.content_json, v.content_json, '{"blocks":[],"steps":[]}') AS content_json
            FROM recipes r
            LEFT JOIN recipe_versions v ON v.id = r.published_version_id
            LEFT JOIN (
              SELECT rv.recipe_id, rv.content_json
              FROM recipe_versions rv
              JOIN (
                SELECT recipe_id, MAX(version_number) AS version_number
                FROM recipe_versions GROUP BY recipe_id
              ) mx ON mx.recipe_id = rv.recipe_id AND mx.version_number = rv.version_number
            ) latest ON latest.recipe_id = r.id
            WHERE r.id = ?
            """,
            (recipe_id,),
        )
        if row is None:
            return None
        content = json.loads(row["content_json"] or '{"blocks":[],"steps":[]}')
        ingredients = await self._db.fetch_all(
            """
            SELECT ri.id, ri.label, ri.quantity_text, ri.product_id, ri.sort_order,
                   p.slug AS product_slug
            FROM recipe_ingredients ri
            LEFT JOIN products p ON p.id = ri.product_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.sort_order, ri.label
            """,
            (recipe_id,),
        )
        tags = json.loads(row["dietary_tags_json"] or "[]")
        return {
            "id": row["id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"] or "",
            "prep_minutes": int(row["prep_minutes"] or 0),
            "cook_minutes": int(row["cook_minutes"] or 0),
            "servings": int(row["servings"] or 0),
            "dietary_tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
            "status": row["status"],
            "chef_user_id": row["chef_user_id"],
            "seo_title": row["seo_title"] or "",
            "seo_description": row["seo_description"] or "",
            "seo_keywords": row["seo_keywords"] or "",
            "canonical_url": row["canonical_url"] or "",
            "indexing_policy": row["indexing_policy"],
            "updated_at": row["updated_at"],
            "blocks": content.get("blocks", []) if isinstance(content, dict) else [],
            "steps": content.get("steps", []) if isinstance(content, dict) else [],
            "ingredients": [
                {
                    "id": entry["id"],
                    "label": entry["label"],
                    "quantity_text": entry["quantity_text"] or "",
                    "product_id": entry["product_id"],
                    "product_slug": entry["product_slug"],
                }
                for entry in ingredients
            ],
        }

    async def next_version_number(self, recipe_id: str) -> int:
        row = await self._db.fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) AS max_version"
            " FROM recipe_versions WHERE recipe_id = ?",
            (recipe_id,),
        )
        return int(row["max_version"]) + 1 if row else 1


_ARTICLE_PUBLIC_COLUMNS = """
    a.id, a.title, a.slug, a.excerpt, a.reading_minutes, a.published_at,
    a.published_version_id, a.seo_title, a.seo_description, a.seo_keywords,
    a.canonical_url, a.indexing_policy,
    COALESCE(u.display_name, 'True Grit') AS author_name
"""


class ArticleRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            f"""
            SELECT {_ARTICLE_PUBLIC_COLUMNS}
            FROM articles a
            LEFT JOIN users u ON u.id = a.author_user_id
            WHERE a.status = 'published'
            ORDER BY a.published_at DESC, a.title
            """
        )
        return [await self._detail_from_row(row) for row in rows]

    async def get_published_by_slug(self, slug: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            f"""
            SELECT {_ARTICLE_PUBLIC_COLUMNS}
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
        blocks = content.get("blocks") if isinstance(content, dict) else []
        return {
            "id": row["id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"] or "",
            "author_name": row["author_name"],
            "published_at": row["published_at"] or "",
            "reading_minutes": int(row["reading_minutes"] or 1),
            "blocks": [b for b in blocks if isinstance(b, dict) and b.get("enabled", True)]
            if isinstance(blocks, list)
            else [],
            "pull_quote": content.get("pullQuote") if isinstance(content, dict) else None,
            "seo": {
                "title": row["seo_title"] or row["title"],
                "description": row["seo_description"] or row["excerpt"] or "",
                "keywords": row["seo_keywords"],
                "canonical_path": row["canonical_url"] or f"/blog/{row['slug']}",
                "indexing": row["indexing_policy"],
            },
        }

    async def list_admin(
        self,
        *,
        author_user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """Admin listing. `author_user_id` scopes results to one blogger's own
        articles — the caller only passes it for principals without
        `articles.approve` (i.e. the `blogger` role), never for reviewers."""
        like = f"%{search}%" if search else None
        return await self._db.fetch_all(
            """
            SELECT a.id, a.title, a.slug, a.status, a.updated_at, a.published_at,
                   COALESCE(u.display_name, 'Unassigned') AS author_name,
                   (SELECT MAX(version_number) FROM article_versions WHERE article_id = a.id)
                     AS latest_version_number,
                   (SELECT version_number FROM article_versions WHERE id = a.published_version_id)
                     AS published_version_number
            FROM articles a
            LEFT JOIN users u ON u.id = a.author_user_id
            WHERE (? IS NULL OR a.author_user_id = ?)
              AND (? IS NULL OR a.title LIKE ? OR a.slug LIKE ? OR a.excerpt LIKE ?)
            ORDER BY a.updated_at DESC
            LIMIT ? OFFSET ?
            """,
            (
                author_user_id,
                author_user_id,
                like,
                like,
                like,
                like,
                min(max(limit, 1), 100),
                max(offset, 0),
            ),
        )

    async def get_admin_detail(self, article_id: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT a.id, a.title, a.slug, a.excerpt, a.reading_minutes, a.status,
                   a.author_user_id, a.hero_media_id, a.seo_title, a.seo_description,
                   a.seo_keywords, a.canonical_url, a.indexing_policy, a.updated_at,
                   a.published_version_id,
                   COALESCE(latest.content_json, v.content_json, '{"blocks":[]}') AS content_json
            FROM articles a
            LEFT JOIN article_versions v ON v.id = a.published_version_id
            LEFT JOIN (
              SELECT av.article_id, av.content_json
              FROM article_versions av
              JOIN (
                SELECT article_id, MAX(version_number) AS version_number
                FROM article_versions GROUP BY article_id
              ) mx ON mx.article_id = av.article_id AND mx.version_number = av.version_number
            ) latest ON latest.article_id = a.id
            WHERE a.id = ?
            """,
            (article_id,),
        )
        if row is None:
            return None
        content = json.loads(row["content_json"] or '{"blocks":[]}')
        return {
            "id": row["id"],
            "title": row["title"],
            "slug": row["slug"],
            "excerpt": row["excerpt"] or "",
            "reading_minutes": int(row["reading_minutes"] or 1),
            "status": row["status"],
            "author_user_id": row["author_user_id"],
            "hero_media_id": row["hero_media_id"],
            "seo_title": row["seo_title"] or "",
            "seo_description": row["seo_description"] or "",
            "seo_keywords": row["seo_keywords"] or "",
            "canonical_url": row["canonical_url"] or "",
            "indexing_policy": row["indexing_policy"],
            "updated_at": row["updated_at"],
            "blocks": content.get("blocks", []) if isinstance(content, dict) else [],
            "pull_quote": content.get("pullQuote") if isinstance(content, dict) else None,
        }

    async def next_version_number(self, article_id: str) -> int:
        row = await self._db.fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) AS max_version"
            " FROM article_versions WHERE article_id = ?",
            (article_id,),
        )
        return int(row["max_version"]) + 1 if row else 1


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


class RouteSeoRepository:
    """Admin-editable SEO overrides for storefront routes that are not backed
    by a single-segment CMS page record (see migration 0035)."""

    def __init__(self, db: Database):
        self._db = db

    async def get(self, path: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT path, seo_title, seo_description, seo_keywords, indexing_policy, updated_at"
            " FROM route_seo_overrides WHERE path = ?",
            (path,),
        )

    async def list(self) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT path, seo_title, seo_description, seo_keywords, indexing_policy, updated_at"
            " FROM route_seo_overrides ORDER BY path"
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


class ReturnRequestRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = "AND (o.public_reference LIKE ? OR oi.product_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT rr.id, rr.order_id, o.public_reference, rr.customer_user_id,
                   COALESCE(u.display_name, o.customer_email) AS customer_name,
                   rr.reason_code, rr.status, rr.requested_refund_amount_minor,
                   rr.resolution_type, rr.resolution_amount_minor, rr.requested_at,
                   rr.resolved_at
            FROM return_requests rr
            JOIN orders o ON o.id = rr.order_id
            LEFT JOIN users u ON u.id = rr.customer_user_id
            LEFT JOIN order_items oi ON oi.id = rr.order_item_id
            WHERE (? IS NULL OR rr.status = ?)
            {search_clause}
            ORDER BY rr.requested_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get_admin_detail(self, return_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT rr.*, o.public_reference, o.total_minor AS order_total_minor,
                   o.currency_code, COALESCE(u.display_name, o.customer_email) AS customer_name,
                   oi.product_name, oi.variant_name
            FROM return_requests rr
            JOIN orders o ON o.id = rr.order_id
            LEFT JOIN users u ON u.id = rr.customer_user_id
            LEFT JOIN order_items oi ON oi.id = rr.order_item_id
            WHERE rr.id = ?
            """,
            (return_id,),
        )

    async def list_for_customer(self, customer_user_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT rr.id, rr.order_id, o.public_reference, rr.reason_code, rr.status,
                   rr.resolution_type, rr.requested_at, rr.resolved_at
            FROM return_requests rr
            JOIN orders o ON o.id = rr.order_id
            WHERE rr.customer_user_id = ?
            ORDER BY rr.requested_at DESC
            """,
            (customer_user_id,),
        )


class ContentSubmissionRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self,
        *,
        content_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        search_clause = ""
        params: list[Any] = [content_type, content_type, status, status]
        if search:
            search_clause = "AND (cs.title LIKE ? OR cs.contact_name LIKE ? OR cs.contact_email LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT cs.id, cs.content_type, cs.status, cs.title, cs.contact_name, cs.contact_email,
                   cs.contact_phone, cs.submitter_user_id, cs.created_at, cs.updated_at, cs.reviewed_at
            FROM content_submissions cs
            WHERE (? IS NULL OR cs.content_type = ?) AND (? IS NULL OR cs.status = ?)
            {search_clause}
            ORDER BY cs.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def count_pending(self) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS n FROM content_submissions WHERE status IN ('submitted', 'under_review')"
        )
        return int(row["n"]) if row else 0

    async def get_admin_detail(self, submission_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one("SELECT * FROM content_submissions WHERE id = ?", (submission_id,))

    async def list_for_customer(self, customer_user_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT id, content_type, status, title, excerpt, body, contact_name, contact_email,
                   contact_phone, prep_minutes, cook_minutes, servings, dietary_tags_json,
                   ingredients_json, steps_json, reviewer_notes, created_at, updated_at,
                   published_article_id, published_recipe_id
            FROM content_submissions
            WHERE submitter_user_id = ?
            ORDER BY created_at DESC
            """,
            (customer_user_id,),
        )

    async def get_for_customer(self, customer_user_id: str, submission_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT id, content_type, status, title, excerpt, body, contact_name, contact_email,
                   contact_phone, prep_minutes, cook_minutes, servings, dietary_tags_json,
                   ingredients_json, steps_json, reviewer_notes, created_at, updated_at,
                   published_article_id, published_recipe_id
            FROM content_submissions
            WHERE id = ? AND submitter_user_id = ?
            """,
            (submission_id, customer_user_id),
        )


class DiscussionRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_public(self, *, limit: int = 30, offset: int = 0) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT d.id, d.title, d.body, d.comment_count, d.last_activity_at, d.created_at,
                   u.display_name AS author_name
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE d.status = 'visible'
            ORDER BY d.last_activity_at DESC
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 100), max(offset, 0)),
        )

    async def get_public_detail(self, discussion_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT d.id, d.title, d.body, d.comment_count, d.last_activity_at, d.created_at,
                   u.display_name AS author_name
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE d.id = ? AND d.status = 'visible'
            """,
            (discussion_id,),
        )

    async def list_comments_public(self, discussion_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT c.id, c.body, c.created_at, u.display_name AS author_name
            FROM discussion_comments c
            JOIN users u ON u.id = c.author_user_id
            WHERE c.discussion_id = ? AND c.status = 'visible'
            ORDER BY c.created_at ASC
            """,
            (discussion_id,),
        )

    async def list_admin(
        self, *, status: str | None = None, limit: int = 50, offset: int = 0, search: str | None = None
    ) -> list[dict[str, Any]]:
        search_clause = ""
        params: list[Any] = [status, status]
        if search:
            search_clause = "AND (d.title LIKE ? OR u.display_name LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT d.id, d.title, d.status, d.comment_count, d.last_activity_at, d.created_at,
                   u.display_name AS author_name
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE (? IS NULL OR d.status = ?)
            {search_clause}
            ORDER BY d.last_activity_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get_admin_detail(self, discussion_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT d.*, u.display_name AS author_name, u.email AS author_email
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE d.id = ?
            """,
            (discussion_id,),
        )

    async def list_comments_admin(self, discussion_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT c.*, u.display_name AS author_name
            FROM discussion_comments c
            JOIN users u ON u.id = c.author_user_id
            WHERE c.discussion_id = ?
            ORDER BY c.created_at ASC
            """,
            (discussion_id,),
        )

    async def list_all_visible_for_sitemap(self, limit: int = 5000) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT id, updated_at FROM discussions WHERE status = 'visible'"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )


class AuditRepository:
    def __init__(self, db: Database):
        self._db = db

    async def recent(self, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            """
            SELECT a.id, COALESCE(u.display_name, 'system') AS actor_name, a.action,
                   a.entity_type, a.entity_id, a.request_id, a.created_at
            FROM audit_logs a
            LEFT JOIN users u ON u.id = a.actor_user_id
            ORDER BY a.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 200), max(offset, 0)),
        )

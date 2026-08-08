"""Content repositories: categories, pages, navigation, search."""

from __future__ import annotations

import json
import re
from typing import Any

from truegrit_api.domain.sitemap import SITEMAP_MAX_URLS
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import geo_release_clause
from truegrit_api.repositories.entity_translations import EntityTranslationRepository
from truegrit_api.services.translation_hub import apply_path_overrides, override_map


class CategoryRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get_published_by_slug(
        self, slug: str, country: str | None = None, *, locale: str | None = None
    ) -> dict[str, Any] | None:
        # Alias must match the FROM clause below: the self-join for the parent
        # department means the table can no longer be referenced by its own name.
        geo_sql, geo_params = geo_release_clause(
            country, alias="c", table="category_release_countries", id_column="category_id"
        )
        row = await self._db.fetch_one(
            f"""
            SELECT c.id, c.name, c.slug, c.short_description, c.hero_eyebrow, c.hero_title,
                   c.hero_description, c.theme_key, c.season_label, c.product_assignment_mode,
                   c.product_rule_json, c.seo_title, c.seo_description, c.hero_image_url,
                   c.hero_image_alt, c.updated_at, c.parent_id,
                   parent.name AS parent_name, parent.slug AS parent_slug
            FROM categories c
            LEFT JOIN categories parent
              ON parent.id = c.parent_id
             AND parent.status = 'published' AND parent.visibility = 'public'
            WHERE c.slug = ? AND c.status = 'published' AND c.visibility = 'public'{geo_sql}
            """,
            (slug, *geo_params),
        )
        if row is None or not locale or locale == "en":
            return row
        translation = await EntityTranslationRepository(self._db).get("category", row["id"], locale)
        if translation is None:
            return row
        fields = translation["fields"]
        return {
            **row,
            "name": fields.get("name") or row["name"],
            "short_description": fields.get("short_description") or row["short_description"],
            "hero_eyebrow": fields.get("hero_eyebrow") or row["hero_eyebrow"],
            "hero_title": fields.get("hero_title") or row["hero_title"],
            "hero_description": fields.get("hero_description") or row["hero_description"],
        }

    async def _translate_rows(
        self, rows: list[dict[str, Any]], locale: str | None
    ) -> list[dict[str, Any]]:
        """Swap in translated `name`/`short_description` (migration 0068) for
        every row that has one saved in `locale`, in one batched lookup rather
        than one query per category -- the same reasoning `NavigationRepository
        .menu` follows for nav labels."""
        if not locale or locale == "en" or not rows:
            return rows
        fields_by_id = await EntityTranslationRepository(self._db).get_fields_map(
            "category", [row["id"] for row in rows], locale
        )
        if not fields_by_id:
            return rows
        translated = []
        for row in rows:
            fields = fields_by_id.get(row["id"])
            if not fields:
                translated.append(row)
                continue
            translated.append(
                {
                    **row,
                    "name": fields.get("name") or row["name"],
                    "short_description": fields.get("short_description")
                    or row["short_description"],
                }
            )
        return translated

    async def list_published(
        self, country: str | None = None, *, locale: str | None = None
    ) -> list[dict[str, Any]]:
        """Every published category, in tree order: each department immediately
        followed by its own subcategories.

        `sort_order` is only meaningful among siblings — a subcategory's
        `sort_order` positions it within its department, not within the whole
        catalogue. Ordering by it globally therefore interleaves the levels
        (subcategories at 1-4 sort ahead of departments at 11-50, so the list
        opens with unrelated subcategories). Sorting by the *department's*
        position first, then level, then position within the department, keeps
        every branch contiguous and lets callers group the flat list without a
        second request.
        """
        geo_sql, geo_params = geo_release_clause(
            country, alias="c", table="category_release_countries", id_column="category_id"
        )
        rows = await self._db.fetch_all(
            f"""
            SELECT c.id, c.name, c.slug, c.short_description, c.theme_key, c.season_label,
                   c.hero_image_url, c.parent_id, c.level,
                   (SELECT COUNT(*) FROM product_categories pc
                     JOIN products p ON p.id = pc.product_id
                    WHERE pc.category_id = c.id AND p.status = 'published') AS product_count
            FROM categories c
            LEFT JOIN categories root ON root.id = c.parent_id
            WHERE c.status = 'published' AND c.visibility = 'public'{geo_sql}
            ORDER BY COALESCE(root.sort_order, c.sort_order),
                     COALESCE(root.name, c.name),
                     c.level,
                     c.sort_order,
                     c.name
            """,
            tuple(geo_params),
        )
        return await self._translate_rows(rows, locale)

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + updated_at for every indexable public category. Skips the
        per-category product COUNT that `list_published` runs for navigation
        badges — a sitemap never reads it."""
        return await self._db.fetch_all(
            "SELECT slug, updated_at FROM categories"
            " WHERE status = 'published' AND visibility = 'public'"
            " AND indexing_policy = 'index'"
            " ORDER BY slug LIMIT ?",
            (limit,),
        )

    async def list_published_children(
        self, parent_id: str, country: str | None = None, *, locale: str | None = None
    ) -> list[dict[str, Any]]:
        """Published subcategories of one department, in editor-defined order.
        Backs the drill-down on a department page, which would otherwise dead-end
        in a flat product grid."""
        geo_sql, geo_params = geo_release_clause(
            country, alias="c", table="category_release_countries", id_column="category_id"
        )
        rows = await self._db.fetch_all(
            f"""
            SELECT c.id, c.name, c.slug, c.short_description, c.theme_key, c.season_label,
                   c.hero_image_url, c.parent_id, c.level,
                   (SELECT COUNT(*) FROM product_categories pc
                     JOIN products p ON p.id = pc.product_id
                    WHERE pc.category_id = c.id AND p.status = 'published') AS product_count
            FROM categories c
            WHERE c.parent_id = ? AND c.status = 'published'
              AND c.visibility = 'public'{geo_sql}
            ORDER BY c.sort_order, c.name
            """,
            (parent_id, *geo_params),
        )
        return await self._translate_rows(rows, locale)

    async def get_published_id_by_slug(self, slug: str, country: str | None = None) -> str | None:
        """Resolve a category slug to its id for filtering product queries.
        Returns None for a slug that is missing, unpublished, non-public or not
        released in `country`, so a filter can never widen visibility."""
        geo_sql, geo_params = geo_release_clause(
            country, alias="c", table="category_release_countries", id_column="category_id"
        )
        row = await self._db.fetch_one(
            f"""
            SELECT c.id FROM categories c
            WHERE c.slug = ? AND c.status = 'published'
              AND c.visibility = 'public'{geo_sql}
            """,
            (slug, *geo_params),
        )
        return str(row["id"]) if row else None

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

    async def get_published_by_slug(
        self, slug: str, *, locale: str | None = None
    ) -> dict[str, Any] | None:
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
        content_json = page["content_json"]
        # A translated page (migration 0067) swaps in here -- block ids and
        # `enabled` flags are unchanged by translation, so the same filtering
        # below applies identically to either language.
        if locale and locale != "en":
            translation = await self._db.fetch_one(
                "SELECT content_json FROM page_content_translations"
                " WHERE page_id = ? AND locale = ?",
                (page["id"], locale),
            )
            if translation is not None:
                content_json = translation["content_json"]
        content = json.loads(content_json)
        runtime_fields: dict[str, str] = {}
        if locale and locale != "en":
            runtime_fields = await override_map(self._db, "page", page["id"], locale)
            content = apply_path_overrides(content, runtime_fields, prefix="content")
        return {
            "id": page["id"],
            "slug": page["slug"],
            "title": runtime_fields.get("title") or page["title"],
            "blocks": [block for block in content.get("blocks", []) if block.get("enabled", True)],
            "seo": {
                "title": runtime_fields.get("seo_title") or page["seo_title"] or page["title"],
                "description": runtime_fields.get("seo_description")
                or page["seo_description"]
                or "",
                "keywords": page["seo_keywords"],
                "canonical_path": "/" if page["slug"] == "home" else f"/{page['slug']}",
                "indexing": page["indexing_policy"],
            },
        }

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + updated_at for every indexable published page — the sitemap's
        only source for CMS pages, so a newly published page appears without
        any code change. Pages flipped to `noindex` in the CMS drop out of the
        sitemap on the same publish, keeping the two signals consistent."""
        return await self._db.fetch_all(
            "SELECT slug, updated_at FROM pages"
            " WHERE status = 'published' AND indexing_policy = 'index'"
            " ORDER BY slug LIMIT ?",
            (limit,),
        )


class FarmRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(self, *, locale: str | None = None) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.story_json,
                   f.established_year, f.seo_title, f.seo_description,
                   f.hero_image_url, f.hero_image_alt,
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
        # One batched lookup for the whole list (migration 0068), matching
        # `RecipeRepository.list_published`.
        fields_by_id: dict[str, dict[str, Any]] = {}
        if locale and locale != "en" and rows:
            fields_by_id = await EntityTranslationRepository(self._db).get_fields_map(
                "farm", [row["id"] for row in rows], locale
            )
        return [
            await self._detail_from_row(row, fields_by_id.get(row["id"]), locale=locale)
            for row in rows
        ]

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + updated_at for every published farm. `list_published` runs a
        certification lookup and story assembly per farm to build profile
        cards; the sitemap needs neither."""
        return await self._db.fetch_all(
            "SELECT slug, updated_at FROM farms WHERE status = 'published' ORDER BY slug LIMIT ?",
            (limit,),
        )

    async def get_published_by_slug(
        self, slug: str, *, locale: str | None = None
    ) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.story_json,
                   f.established_year, f.seo_title, f.seo_description,
                   f.hero_image_url, f.hero_image_alt,
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
        translation = None
        if locale and locale != "en":
            translation = await EntityTranslationRepository(self._db).get("farm", row["id"], locale)
        return await self._detail_from_row(
            row, translation["fields"] if translation else None, locale=locale
        )

    async def _detail_from_row(
        self,
        row: dict[str, Any],
        fields: dict[str, Any] | None = None,
        *,
        locale: str | None = None,
    ) -> dict[str, Any]:
        story = json.loads(row["story_json"] or "{}")
        if not isinstance(story, dict):
            story = {}
        runtime_fields = (
            await override_map(self._db, "farm", row["id"], locale)
            if locale and locale != "en"
            else {}
        )
        story = apply_path_overrides(story, runtime_fields, prefix="story")
        summary = str(story.get("summary") or "")
        body = str(story.get("body") or summary)
        methods = story.get("methods")
        product_rows = await self._db.fetch_all(
            "SELECT slug FROM products WHERE farm_id = ? AND status = 'published' ORDER BY name",
            (row["id"],),
        )

        def translated(field: str, fallback: Any) -> Any:
            """A saved translation wins; a blank one is treated as absent so a
            half-filled record never blanks a farm's name on the page."""
            if not fields:
                return fallback
            value = fields.get(field)
            return value if isinstance(value, str) and value.strip() else fallback

        localized_summary = translated("summary", summary)
        localized_name = translated("name", row["name"])
        return {
            "id": row["id"],
            "name": localized_name,
            "slug": row["slug"],
            "farmer_name": translated("farmer_name", row["farmer_name"] or ""),
            "region": translated("region", row["region"] or ""),
            "summary": localized_summary,
            "certification": translated("certification", row["certification"] or "Verified farm"),
            "established_year": int(row["established_year"] or 0),
            "story": translated("story", body),
            "methods": [str(method) for method in methods] if isinstance(methods, list) else [],
            "product_slugs": [entry["slug"] for entry in product_rows],
            "hero_image_url": row["hero_image_url"] or None,
            "hero_image_alt": translated("hero_image_alt", row["hero_image_alt"] or "") or None,
            "seo": {
                # Falls back to the *translated* name, so a farm with no saved
                # SEO override still gets a localized browser title rather than
                # an English one sitting above a translated page.
                "title": translated("seo_title", row["seo_title"] or localized_name),
                "description": translated(
                    "seo_description", row["seo_description"] or localized_summary
                ),
                "canonical_path": f"/farms/{row['slug']}",
                "indexing": "index",
            },
        }


_RECIPE_PUBLIC_COLUMNS = """
    id, title, slug, excerpt, prep_minutes, cook_minutes, servings,
    dietary_tags_json, published_version_id, seo_title, seo_description,
    seo_keywords, canonical_url, indexing_policy, hero_image_url, hero_image_alt
"""


class RecipeRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(
        self, *, limit: int = 12, offset: int = 0, locale: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            f"""
            SELECT {_RECIPE_PUBLIC_COLUMNS}
            FROM recipes
            WHERE status = 'published'
            ORDER BY published_at DESC, title
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 5000), max(offset, 0)),
        )
        # One batched lookup for the whole page (migration 0068) rather than
        # one per recipe -- the same reasoning `CategoryRepository
        # ._translate_rows` follows.
        fields_by_id: dict[str, dict[str, Any]] = {}
        if locale and locale != "en" and rows:
            fields_by_id = await EntityTranslationRepository(self._db).get_fields_map(
                "recipe", [row["id"] for row in rows], locale
            )
        return [
            await self._detail_from_row(row, fields_by_id.get(row["id"]), locale=locale)
            for row in rows
        ]

    async def count_published(self) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM recipes WHERE status = 'published'"
        )
        return int(row["total"]) if row else 0

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + freshness for every indexable published recipe.

        `list_published` calls `_detail_from_row` per row, and each of those
        loads the recipe's version body and its ingredient list — two extra
        queries and a JSON parse per recipe. Asking it for the whole
        catalogue at once is what timed this endpoint out; the sitemap reads
        the two columns it actually renders instead.
        """
        return await self._db.fetch_all(
            "SELECT slug, COALESCE(updated_at, published_at) AS updated_at FROM recipes"
            " WHERE status = 'published' AND indexing_policy = 'index'"
            " ORDER BY published_at DESC, slug LIMIT ?",
            (limit,),
        )

    async def get_published_by_slug(
        self, slug: str, *, locale: str | None = None
    ) -> dict[str, Any] | None:
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
        translation = None
        if locale and locale != "en":
            translation = await EntityTranslationRepository(self._db).get(
                "recipe", row["id"], locale
            )
        return await self._detail_from_row(
            row, translation["fields"] if translation else None, locale=locale
        )

    async def _detail_from_row(
        self,
        row: dict[str, Any],
        translated_fields: dict[str, Any] | None = None,
        *,
        locale: str | None = None,
    ) -> dict[str, Any]:
        version = None
        if row["published_version_id"]:
            version = await self._db.fetch_one(
                "SELECT content_json FROM recipe_versions WHERE id = ?",
                (row["published_version_id"],),
            )
        content = json.loads(version["content_json"]) if version else {}
        runtime_fields = (
            await override_map(self._db, "recipe", row["id"], locale)
            if locale and locale != "en"
            else {}
        )
        ingredients = await self._db.fetch_all(
            """
            SELECT ri.id, ri.label, ri.quantity_text, p.slug AS product_slug
            FROM recipe_ingredients ri
            LEFT JOIN products p ON p.id = ri.product_id
            WHERE ri.recipe_id = ?
            ORDER BY ri.sort_order, ri.label
            """,
            (row["id"],),
        )
        tags = json.loads(row["dietary_tags_json"] or "[]")
        translated_fields = translated_fields or {}
        if runtime_fields:
            content = apply_path_overrides(content, runtime_fields, prefix="content")
            for entry in ingredients:
                token = str(entry.get("id") or "").replace("~", "~0").replace("/", "~1")
                entry["label"] = runtime_fields.get(f"ingredient/{token}/label") or entry["label"]
                entry["quantity_text"] = (
                    runtime_fields.get(f"ingredient/{token}/quantity_text")
                    or entry["quantity_text"]
                )
        steps = content.get("steps") if isinstance(content, dict) else []
        blocks = content.get("blocks") if isinstance(content, dict) else []
        title = translated_fields.get("title") or row["title"]
        excerpt = translated_fields.get("excerpt") or row["excerpt"] or ""
        return {
            "id": row["id"],
            "title": title,
            "slug": row["slug"],
            "excerpt": excerpt,
            "prep_minutes": int(row["prep_minutes"] or 0),
            "cook_minutes": int(row["cook_minutes"] or 0),
            "servings": int(row["servings"] or 0),
            "dietary_tags": [str(tag) for tag in tags] if isinstance(tags, list) else [],
            "hero_image_url": row["hero_image_url"] or None,
            "hero_image_alt": translated_fields.get("hero_image_alt")
            or row["hero_image_alt"]
            or None,
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
                "title": translated_fields.get("seo_title") or row["seo_title"] or title,
                "description": translated_fields.get("seo_description")
                or row["seo_description"]
                or excerpt,
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
            WHERE r.archived_at IS NULL
              AND (? IS NULL OR r.chef_user_id = ?)
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
                   r.hero_image_url, r.hero_image_alt,
                   COALESCE(latest.content_json, v.content_json, '{"blocks":[],"steps":[]}')
                     AS content_json
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
            "hero_image_url": row["hero_image_url"] or "",
            "hero_image_alt": row["hero_image_alt"] or "",
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
    a.canonical_url, a.indexing_policy, a.hero_image_url, a.hero_image_alt,
    COALESCE(u.display_name, 'True Grit') AS author_name
"""


class ArticleRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_published(
        self, *, limit: int = 10, offset: int = 0, locale: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            f"""
            SELECT {_ARTICLE_PUBLIC_COLUMNS}
            FROM articles a
            LEFT JOIN users u ON u.id = a.author_user_id
            WHERE a.status = 'published'
            ORDER BY a.published_at DESC, a.title
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 5000), max(offset, 0)),
        )
        # One batched lookup for the whole page (migration 0068) rather than
        # one per article -- the same reasoning `CategoryRepository
        # ._translate_rows` follows.
        fields_by_id: dict[str, dict[str, Any]] = {}
        if locale and locale != "en" and rows:
            fields_by_id = await EntityTranslationRepository(self._db).get_fields_map(
                "article", [row["id"] for row in rows], locale
            )
        return [
            await self._detail_from_row(row, fields_by_id.get(row["id"]), locale=locale)
            for row in rows
        ]

    async def count_published(self) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM articles WHERE status = 'published'"
        )
        return int(row["total"]) if row else 0

    async def list_slugs_for_sitemap(
        self, *, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        """Slug + freshness for every indexable published article. Same reason
        as recipes: `list_published` loads each article's version body to
        render blog cards, which the sitemap never uses."""
        return await self._db.fetch_all(
            "SELECT slug, COALESCE(updated_at, published_at) AS updated_at FROM articles"
            " WHERE status = 'published' AND indexing_policy = 'index'"
            " ORDER BY published_at DESC, slug LIMIT ?",
            (limit,),
        )

    async def get_published_by_slug(
        self, slug: str, *, locale: str | None = None
    ) -> dict[str, Any] | None:
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
        translation = None
        if locale and locale != "en":
            translation = await EntityTranslationRepository(self._db).get(
                "article", row["id"], locale
            )
        return await self._detail_from_row(
            row, translation["fields"] if translation else None, locale=locale
        )

    async def _detail_from_row(
        self,
        row: dict[str, Any],
        translated_fields: dict[str, Any] | None = None,
        *,
        locale: str | None = None,
    ) -> dict[str, Any]:
        version = None
        if row["published_version_id"]:
            version = await self._db.fetch_one(
                "SELECT content_json FROM article_versions WHERE id = ?",
                (row["published_version_id"],),
            )
        content = json.loads(version["content_json"]) if version else {}
        translated_fields = translated_fields or {}
        if locale and locale != "en":
            runtime_fields = await override_map(self._db, "article", row["id"], locale)
            content = apply_path_overrides(content, runtime_fields, prefix="content")
        blocks = content.get("blocks") if isinstance(content, dict) else []
        title = translated_fields.get("title") or row["title"]
        excerpt = translated_fields.get("excerpt") or row["excerpt"] or ""
        return {
            "id": row["id"],
            "title": title,
            "slug": row["slug"],
            "excerpt": excerpt,
            "author_name": row["author_name"],
            "published_at": row["published_at"] or "",
            "reading_minutes": int(row["reading_minutes"] or 1),
            "hero_image_url": row["hero_image_url"] or None,
            "hero_image_alt": translated_fields.get("hero_image_alt")
            or row["hero_image_alt"]
            or None,
            "blocks": [b for b in blocks if isinstance(b, dict) and b.get("enabled", True)]
            if isinstance(blocks, list)
            else [],
            "pull_quote": content.get("pullQuote") if isinstance(content, dict) else None,
            "seo": {
                "title": translated_fields.get("seo_title") or row["seo_title"] or title,
                "description": translated_fields.get("seo_description")
                or row["seo_description"]
                or excerpt,
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
            WHERE a.archived_at IS NULL
              AND (? IS NULL OR a.author_user_id = ?)
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
                   a.published_version_id, a.hero_image_url, a.hero_image_alt,
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
            "hero_image_url": row["hero_image_url"] or "",
            "hero_image_alt": row["hero_image_alt"] or "",
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

    async def menu(self, key: str, *, locale: str | None = None) -> list[dict[str, str]]:
        rows = await self._db.fetch_all(
            """
            SELECT ni.id, ni.label, ni.destination_type, ni.destination_reference
            FROM navigation_items ni
            JOIN navigation_menus nm ON nm.id = ni.menu_id
            WHERE nm.key = ? AND ni.visible = 1 AND ni.parent_id IS NULL
            ORDER BY ni.sort_order
            """,
            (key,),
        )
        # A translated label (migration 0068) swaps in here -- destinations
        # and visibility are unchanged by translation, so the filtering below
        # applies identically to either language.
        translated_fields: dict[str, dict[str, Any]] = {}
        if locale and locale != "en":
            translated_fields = await EntityTranslationRepository(self._db).get_fields_map(
                "navigation_item", [row["id"] for row in rows], locale
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
            label = translated_fields.get(row["id"], {}).get("label") or row["label"]
            items.append({"label": label, "path": path})
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

    # Relevance tiers for an expanded search term. A catalogue of hundreds of
    # products always overflows the result limit, so which matches survive is
    # decided here rather than by alphabetical luck.
    #
    # A term resolved from a *multi-word* synonym phrase is the strongest
    # signal: "finger millet" names one thing, and matching it beats matching
    # the loose word "millet", which every millet product in the catalogue
    # carries. A word the visitor actually typed comes next, and a synonym
    # expanded outwards from one of those words comes last — it broadens
    # recall and must never outrank what was literally asked for.
    _RANK_PHRASE_SYNONYM = 0
    _RANK_TYPED = 1
    _RANK_EXPANSION = 2

    async def _expand_terms(self, query: str) -> list[tuple[str, int]]:
        """Search terms paired with their relevance tier, best first."""
        normalized = _FTS_SANITIZE.sub(" ", query).lower()
        terms = [term for term in normalized.split() if len(term) >= 2][:6]
        if not terms:
            return []
        # Synonyms expand in both directions: a query for "ragi" should also
        # match "finger millet", and a query phrased as "finger millet" (the
        # synonym, possibly multi-word) should match "ragi". The table is tiny,
        # so scan it rather than juggle phrase placeholders.
        ranked: dict[str, int] = dict.fromkeys(terms, self._RANK_TYPED)
        rows = await self._db.fetch_all("SELECT term, synonym FROM search_synonyms")
        for row in rows:
            term = row["term"].lower()
            synonym = row["synonym"].lower()
            if term in terms and synonym not in ranked:
                ranked[synonym] = self._RANK_EXPANSION
            if synonym in normalized and term not in terms:
                # Multi-word phrases identify the intent; a single-word synonym
                # is just another way of saying a word already typed.
                rank = self._RANK_PHRASE_SYNONYM if " " in synonym else self._RANK_EXPANSION
                ranked[term] = min(rank, ranked.get(term, rank))
        return sorted(ranked.items(), key=lambda entry: (entry[1], entry[0]))

    async def search(
        self,
        query: str,
        limit: int = 20,
        country: str | None = None,
        *,
        locale: str | None = None,
    ) -> dict[str, Any]:
        terms = await self._expand_terms(query)
        if not terms:
            return {"query": query, "total": 0, "groups": []}
        match = " OR ".join(f'"{term}"*' for term, _ in terms)

        # Products are searched against the live catalogue (not the FTS shadow
        # table, which only the seed populates) so results always reflect what
        # is actually published — and only what is released in the visitor's
        # country.
        match_sql = (
            "(p.name LIKE ? OR p.slug LIKE ? OR p.short_description LIKE ?"
            " OR f.name LIKE ? OR t.label LIKE ?)"
        )
        term_clause = " OR ".join(match_sql for _ in terms)
        term_params: list[Any] = []
        for term, _rank in terms:
            like = f"%{term}%"
            term_params.extend([like, like, like, like, like])

        # Rank by the best tier any of a product's fields matched, so the limit
        # keeps the most relevant rows rather than the alphabetically first.
        # A product matching several terms scores its strongest one via MIN.
        rank_sql = " ".join(f"WHEN {match_sql} THEN {rank}" for _term, rank in terms)
        rank_params: list[Any] = []
        for term, _rank in terms:
            like = f"%{term}%"
            rank_params.extend([like, like, like, like, like])

        geo_sql, geo_params = geo_release_clause(country)
        product_rows = await self._db.fetch_all(
            f"""
            SELECT p.id, p.name, p.slug,
                   MIN(CASE {rank_sql} ELSE {self._RANK_EXPANSION + 1} END) AS relevance
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN product_tags pt ON pt.product_id = p.id
            LEFT JOIN tags t ON t.id = pt.tag_id
            WHERE p.status = 'published' AND ({term_clause}){geo_sql}
            GROUP BY p.id, p.name, p.slug
            ORDER BY relevance, p.name
            LIMIT ?
            """,
            (*rank_params, *term_params, *geo_params, limit),
        )
        content_rows = await self._db.fetch_all(
            "SELECT entity_type, entity_id AS id, title AS name, slug FROM search_content"
            " WHERE search_content MATCH ? LIMIT ?",
            (match, limit),
        )

        # Matching runs against English -- the FTS index and the LIKE clauses
        # above both read the source columns -- but the *result list* is read by
        # the visitor, so the names shown are swapped for saved translations
        # (migration 0068). One batched lookup per entity type.
        translations = EntityTranslationRepository(self._db)

        async def names_for(entity_type: str, ids: list[str]) -> dict[str, dict[str, Any]]:
            if not locale or locale == "en" or not ids:
                return {}
            return await translations.get_fields_map(entity_type, ids, locale)

        def localized_name(fields: dict[str, Any] | None, field: str, fallback: str) -> str:
            if not fields:
                return fallback
            value = fields.get(field)
            return value if isinstance(value, str) and value.strip() else fallback

        groups: list[dict[str, Any]] = []
        if product_rows:
            product_fields = await names_for("product", [row["id"] for row in product_rows])
            groups.append(
                {
                    "group": "products",
                    "items": [
                        {
                            "id": row["id"],
                            "name": localized_name(
                                product_fields.get(row["id"]), "name", row["name"]
                            ),
                            "slug": row["slug"],
                            "path": f"/product/{row['slug']}",
                        }
                        for row in product_rows
                    ],
                }
            )
        content_paths = {"article": "/journal/", "recipe": "/recipes/", "farm": "/farms/"}
        # Articles and recipes carry their display name in `title`; a farm in
        # `name`. The search shadow table flattens all three into `name`, so the
        # translated field has to be looked up under the entity's own key.
        translated_field = {"article": "title", "recipe": "title", "farm": "name"}
        for entity_type, base_path in content_paths.items():
            matched = [row for row in content_rows if row["entity_type"] == entity_type]
            if matched:
                fields_by_id = await names_for(entity_type, [row["id"] for row in matched])
                groups.append(
                    {
                        "group": f"{entity_type}s",
                        "items": [
                            {
                                "id": row["id"],
                                "name": localized_name(
                                    fields_by_id.get(row["id"]),
                                    translated_field[entity_type],
                                    row["name"],
                                ),
                                "path": base_path + row["slug"],
                            }
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
        farm_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """`farm_id` is dormant today -- no seeded role holds `returns.view`
        and a `farm_id` at once -- but if one ever does, this scopes them to
        returns against their own farm's products. A return with no linked
        order_item (order-level, not one specific item) has no farm to
        attribute it to, so it's hidden rather than shown to every farm."""
        search_clause = ""
        params: list[Any] = [status, status, farm_id, farm_id]
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
              AND (? IS NULL OR oi.farm_id = ?)
            {search_clause}
            ORDER BY rr.requested_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get_admin_detail(
        self, return_id: str, farm_id: str | None = None
    ) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            """
            SELECT rr.*, o.public_reference, o.total_minor AS order_total_minor,
                   o.currency_code, COALESCE(u.display_name, o.customer_email) AS customer_name,
                   oi.product_name, oi.variant_name
            FROM return_requests rr
            JOIN orders o ON o.id = rr.order_id
            LEFT JOIN users u ON u.id = rr.customer_user_id
            LEFT JOIN order_items oi ON oi.id = rr.order_item_id
            WHERE rr.id = ? AND (? IS NULL OR oi.farm_id = ?)
            """,
            (return_id, farm_id, farm_id),
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
            search_clause = (
                "AND (cs.title LIKE ? OR cs.contact_name LIKE ? OR cs.contact_email LIKE ?)"
            )
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT cs.id, cs.content_type, cs.status, cs.title, cs.contact_name, cs.contact_email,
                   cs.contact_phone, cs.submitter_user_id, cs.created_at, cs.updated_at,
                   cs.reviewed_at
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
            "SELECT COUNT(*) AS n FROM content_submissions "
            "WHERE status IN ('submitted', 'under_review')"
        )
        return int(row["n"]) if row else 0

    async def get_admin_detail(self, submission_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT * FROM content_submissions WHERE id = ?", (submission_id,)
        )

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

    async def get_for_customer(
        self, customer_user_id: str, submission_id: str
    ) -> dict[str, Any] | None:
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

    async def list_public(
        self, *, limit: int = 30, offset: int = 0, locale: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT d.id, d.title, d.body, d.image_url, d.image_alt,
                   d.comment_count, d.last_activity_at, d.created_at,
                   u.display_name AS author_name
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE d.status = 'visible'
            ORDER BY d.last_activity_at DESC
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 100), max(offset, 0)),
        )
        if not locale or locale == "en":
            return rows
        translated = []
        for row in rows:
            fields = await override_map(self._db, "discussion", row["id"], locale)
            translated.append(
                {
                    **row,
                    "title": fields.get("title") or row["title"],
                    "body": fields.get("body") or row["body"],
                    "image_alt": fields.get("image_alt") or row["image_alt"],
                }
            )
        return translated

    async def count_public(self) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM discussions WHERE status = 'visible'"
        )
        return int(row["total"]) if row else 0

    async def get_public_detail(
        self, discussion_id: str, *, locale: str | None = None
    ) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            """
            SELECT d.id, d.title, d.body, d.image_url, d.image_alt,
                   d.comment_count, d.last_activity_at, d.created_at,
                   u.display_name AS author_name
            FROM discussions d
            JOIN users u ON u.id = d.author_user_id
            WHERE d.id = ? AND d.status = 'visible'
            """,
            (discussion_id,),
        )
        if row is None or not locale or locale == "en":
            return row
        fields = await override_map(self._db, "discussion", discussion_id, locale)
        return {
            **row,
            "title": fields.get("title") or row["title"],
            "body": fields.get("body") or row["body"],
            "image_alt": fields.get("image_alt") or row["image_alt"],
        }

    async def list_comments_public(
        self, discussion_id: str, *, locale: str | None = None
    ) -> list[dict[str, Any]]:
        rows = await self._db.fetch_all(
            """
            SELECT c.id, c.body, c.created_at, u.display_name AS author_name
            FROM discussion_comments c
            JOIN users u ON u.id = c.author_user_id
            WHERE c.discussion_id = ? AND c.status = 'visible'
            ORDER BY c.created_at ASC
            """,
            (discussion_id,),
        )
        if not locale or locale == "en":
            return rows
        for row in rows:
            fields = await override_map(self._db, "discussion_comment", row["id"], locale)
            row["body"] = fields.get("body") or row["body"]
        return rows

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

    async def list_all_visible_for_sitemap(
        self, limit: int = SITEMAP_MAX_URLS
    ) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT id, updated_at FROM discussions WHERE status = 'visible'"
            " ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )


class ContentCommentRepository:
    """Admin-side reads over `content_comments` (migration 0043).

    Public reads live in `services.content_comments`, which resolves the parent
    by slug; these queries go the other way — across every post at once — which
    is what a moderation queue needs. Writes are in the service.
    """

    def __init__(self, db: Database):
        self._db = db

    async def list_admin(
        self,
        *,
        content_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Every comment, newest first, with its parent's title and slug so a
        moderator can open the post without a second round trip.

        The parent is one of two tables, so both are LEFT JOINed and COALESCEd:
        exactly one matches on any given row, guaranteed by the CHECK constraint
        in 0043.
        """
        search_clause = ""
        params: list[Any] = [content_type, content_type, status, status]
        if search:
            search_clause = "AND (c.body LIKE ? OR u.display_name LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT c.id, c.content_type, c.body, c.status, c.created_at,
                   c.moderation_reason, c.moderated_at,
                   u.display_name AS author_name, u.email AS author_email,
                   COALESCE(a.title, r.title) AS parent_title,
                   COALESCE(a.slug, r.slug) AS parent_slug
            FROM content_comments c
            JOIN users u ON u.id = c.author_user_id
            LEFT JOIN articles a ON a.id = c.article_id
            LEFT JOIN recipes r ON r.id = c.recipe_id
            WHERE (? IS NULL OR c.content_type = ?)
              AND (? IS NULL OR c.status = ?)
            {search_clause}
            ORDER BY c.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def count(
        self,
        *,
        content_type: str | None = None,
        status: str | None = None,
        search: str | None = None,
    ) -> int:
        search_clause = ""
        params: list[Any] = [content_type, content_type, status, status]
        if search:
            search_clause = "AND (c.body LIKE ? OR u.display_name LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern])
        row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS total
            FROM content_comments c
            JOIN users u ON u.id = c.author_user_id
            WHERE (? IS NULL OR c.content_type = ?)
              AND (? IS NULL OR c.status = ?)
            {search_clause}
            """,
            tuple(params),
        )
        return int(row["total"]) if row else 0

    async def count_visible(self) -> int:
        """Feeds the admin dashboard tile. Visible rather than total, because a
        hidden comment is already handled."""
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM content_comments WHERE status = 'visible'"
        )
        return int(row["total"]) if row else 0


_REVIEW_PUBLIC_COLUMNS = """
  r.id, r.rating, r.title, r.body, r.created_at,
  u.display_name AS author_name,
  (r.order_id IS NOT NULL) AS verified_purchase
"""


class ReviewRepository:
    """Public reads and admin-side reads over `reviews` (migration 0005,
    extended by 0057). Writes are in `services.reviews`."""

    def __init__(self, db: Database):
        self._db = db

    async def list_public_for_product(
        self, product_id: str, *, limit: int = 20, offset: int = 0
    ) -> list[dict[str, Any]]:
        """Approved reviews for one product, newest first."""
        return await self._db.fetch_all(
            f"""
            SELECT {_REVIEW_PUBLIC_COLUMNS}
            FROM reviews r
            JOIN users u ON u.id = r.customer_user_id
            WHERE r.product_id = ? AND r.status = 'approved'
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (product_id, min(max(limit, 1), 100), max(offset, 0)),
        )

    async def count_public_for_product(self, product_id: str) -> int:
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM reviews WHERE product_id = ? AND status = 'approved'",
            (product_id,),
        )
        return int(row["total"]) if row else 0

    async def list_public_all(self, *, limit: int = 20, offset: int = 0) -> list[dict[str, Any]]:
        """Every approved review sitewide, newest first -- backs the dedicated
        `/reviews` page, as distinct from `list_featured`'s curated homepage
        feed."""
        return await self._db.fetch_all(
            f"""
            SELECT {_REVIEW_PUBLIC_COLUMNS}, p.name AS product_name, p.slug AS product_slug
            FROM reviews r
            JOIN users u ON u.id = r.customer_user_id
            JOIN products p ON p.id = r.product_id
            WHERE r.status = 'approved' AND p.status = 'published'
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            (min(max(limit, 1), 100), max(offset, 0)),
        )

    async def count_public_all(self) -> int:
        row = await self._db.fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM reviews r
            JOIN products p ON p.id = r.product_id
            WHERE r.status = 'approved' AND p.status = 'published'
            """
        )
        return int(row["total"]) if row else 0

    async def list_featured(
        self, *, review_ids: list[str] | None, min_rating: int, limit: int
    ) -> list[dict[str, Any]]:
        """Reviews for the homepage `reviews_showcase` block.

        `review_ids` (manual mode) returns exactly those reviews, in the given
        order, silently dropping any id that is not approved -- an editor who
        featured a review that was later rejected sees the showcase shrink, not
        error. `None` (rule mode) returns the current top-rated approved
        reviews sitewide, live on every call.
        """
        safe_limit = min(max(limit, 1), 24)
        if review_ids:
            placeholders = ", ".join("?" for _ in review_ids)
            rows = await self._db.fetch_all(
                f"""
                SELECT {_REVIEW_PUBLIC_COLUMNS}, p.name AS product_name, p.slug AS product_slug
                FROM reviews r
                JOIN users u ON u.id = r.customer_user_id
                JOIN products p ON p.id = r.product_id
                WHERE r.id IN ({placeholders}) AND r.status = 'approved'
                """,
                review_ids,
            )
            by_id = {row["id"]: row for row in rows}
            return [by_id[review_id] for review_id in review_ids if review_id in by_id][:safe_limit]
        return await self._db.fetch_all(
            f"""
            SELECT {_REVIEW_PUBLIC_COLUMNS}, p.name AS product_name, p.slug AS product_slug
            FROM reviews r
            JOIN users u ON u.id = r.customer_user_id
            JOIN products p ON p.id = r.product_id
            WHERE r.status = 'approved' AND r.rating >= ? AND p.status = 'published'
            ORDER BY r.rating DESC, r.created_at DESC
            LIMIT ?
            """,
            (min(max(min_rating, 1), 5), safe_limit),
        )

    async def list_admin(
        self,
        *,
        status: str | None = None,
        rating: int | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
        farm_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Every review, newest first, with the product and author attached so
        a moderator never needs a second round trip to decide.

        `farm_id` is dormant today -- no seeded role holds `reviews.moderate`
        and a `farm_id` at once -- but if one ever does, this scopes them to
        reviews of their own farm's products rather than the whole catalogue.
        """
        search_clause = ""
        params: list[Any] = [status, status, rating, rating, farm_id, farm_id]
        if search:
            search_clause = "AND (r.title LIKE ? OR r.body LIKE ? OR u.display_name LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        params.extend([min(max(limit, 1), 100), max(offset, 0)])
        return await self._db.fetch_all(
            f"""
            SELECT r.id, r.rating, r.title, r.body, r.status, r.created_at,
                   r.moderated_at, r.moderation_reason,
                   u.display_name AS author_name, u.email AS author_email,
                   p.name AS product_name, p.slug AS product_slug
            FROM reviews r
            JOIN users u ON u.id = r.customer_user_id
            JOIN products p ON p.id = r.product_id
            WHERE (? IS NULL OR r.status = ?)
              AND (? IS NULL OR r.rating = ?)
              AND (? IS NULL OR p.farm_id = ?)
            {search_clause}
            ORDER BY r.created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def count_admin(
        self,
        *,
        status: str | None = None,
        rating: int | None = None,
        search: str | None = None,
        farm_id: str | None = None,
    ) -> int:
        search_clause = ""
        params: list[Any] = [status, status, rating, rating, farm_id, farm_id]
        if search:
            search_clause = "AND (r.title LIKE ? OR r.body LIKE ? OR u.display_name LIKE ?)"
            pattern = f"%{search}%"
            params.extend([pattern, pattern, pattern])
        row = await self._db.fetch_one(
            f"""
            SELECT COUNT(*) AS total
            FROM reviews r
            JOIN users u ON u.id = r.customer_user_id
            JOIN products p ON p.id = r.product_id
            WHERE (? IS NULL OR r.status = ?)
              AND (? IS NULL OR r.rating = ?)
              AND (? IS NULL OR p.farm_id = ?)
            {search_clause}
            """,
            tuple(params),
        )
        return int(row["total"]) if row else 0

    async def count_pending(self) -> int:
        """Feeds the admin nav badge."""
        row = await self._db.fetch_one(
            "SELECT COUNT(*) AS total FROM reviews WHERE status = 'pending'"
        )
        return int(row["total"]) if row else 0


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

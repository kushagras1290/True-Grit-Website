"""Catalogue mutations: create / update / archive for products and categories.

Each operation writes its entity change and its audit record in a single
`db.batch`, so a partial failure rolls back and nothing lands unaudited. Slugs
are validated and checked for uniqueness (excluding the row being edited).
Publishing lives in `services.publishing`; these functions manage the working
row that publishing later snapshots.
"""

from __future__ import annotations

import re
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_PRODUCT_EDITABLE = (
    "name",
    "slug",
    "short_description",
    "seo_title",
    "seo_description",
    "image_url",
    "image_alt",
    "return_eligible",
)
_CATEGORY_EDITABLE = (
    "name",
    "slug",
    "short_description",
    "hero_eyebrow",
    "hero_title",
    "hero_description",
    "season_label",
    "theme_key",
    "visibility",
    "seo_title",
    "seo_description",
    "hero_image_url",
    "hero_image_alt",
)


def _clean_name(name: str) -> str:
    name = (name or "").strip()
    if len(name) < 3:
        raise ValidationAppError("Name needs at least 3 characters.")
    if len(name) > 140:
        raise ValidationAppError("Name must be at most 140 characters.")
    return name


def _resolve_slug(name: str, slug: str | None) -> str:
    return validate_slug(slug.strip()) if slug else slugify(name)


async def _slug_taken(db: Database, table: str, slug: str, exclude_id: str | None = None) -> bool:
    row = await db.fetch_one(
        f"SELECT id FROM {table} WHERE slug = ? AND id != ?",
        (slug, exclude_id or ""),
    )
    return row is not None


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


async def create_product(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    name: str,
    product_type: str,
    slug: str | None = None,
    short_description: str | None = None,
    farm_id: str | None = None,
) -> dict[str, Any]:
    name = _clean_name(name)
    slug = _resolve_slug(name, slug)
    product_type = (product_type or "").strip() or "general"
    if await _slug_taken(db, "products", slug):
        raise ConflictError("A product with this slug already exists.")

    product_id = new_id("prd")
    now = utc_now_iso()
    await db.batch(
        [
            (
                """
                INSERT INTO products (
                  id, internal_name, name, slug, product_type, farm_id, status,
                  short_description, indexing_policy,
                  created_at, created_by, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, ?, 'draft', ?, 'index', ?, ?, ?, ?)
                """,
                (
                    product_id,
                    name,
                    name,
                    slug,
                    product_type,
                    farm_id,
                    short_description,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="product.created",
                entity_type="product",
                entity_id=product_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"name": name, "slug": slug, "status": "draft"},
            ),
        ]
    )
    return {"id": product_id, "slug": slug, "status": "draft"}


async def update_product(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    *,
    fields: dict[str, Any],
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id, name, slug, short_description, seo_title, seo_description,"
        " image_url, image_alt, status, return_eligible"
        " FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if current is None:
        raise NotFoundError("Product not found.")

    updates = _collect_updates(fields, _PRODUCT_EDITABLE, current)
    if "return_eligible" in updates:
        updates["return_eligible"] = 1 if updates["return_eligible"] else 0
    if "name" in updates:
        updates["name"] = _clean_name(updates["name"])
    if "slug" in updates:
        updates["slug"] = validate_slug(str(updates["slug"]).strip())
        if await _slug_taken(db, "products", updates["slug"], exclude_id=product_id):
            raise ConflictError("A product with this slug already exists.")
    if not updates:
        return {"id": product_id, "status": current["status"], "changed": False}

    await _apply_update(
        db,
        table="products",
        entity_type="product",
        action="product.updated",
        entity_id=product_id,
        actor=actor,
        request_id=request_id,
        current=current,
        updates=updates,
    )
    return {"id": product_id, "status": current["status"], "changed": True}


_COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")
_MAX_RELEASE_COUNTRIES = 100
_MAX_PRODUCT_LINKS = 12
_MAX_HIGHLIGHTS = 12


def _normalize_country_codes(countries: list[str]) -> list[str]:
    """Uppercase, validate and dedupe ISO-3166 alpha-2 codes, keeping order."""
    seen: list[str] = []
    for raw in countries:
        code = (raw or "").strip().upper()
        if not _COUNTRY_CODE.match(code):
            raise ValidationAppError(f"'{raw}' is not a two-letter ISO country code.")
        if code not in seen:
            seen.append(code)
    if len(seen) > _MAX_RELEASE_COUNTRIES:
        raise ValidationAppError(
            f"At most {_MAX_RELEASE_COUNTRIES} release countries are supported."
        )
    return seen


async def set_product_release(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    *,
    scope: str,
    countries: list[str],
) -> dict[str, Any]:
    """Replace a product's geo release: global, or a specific country list."""
    if scope not in ("global", "selected"):
        raise ValidationAppError("Release scope must be 'global' or 'selected'.")
    codes = _normalize_country_codes(countries) if scope == "selected" else []
    if scope == "selected" and not codes:
        raise ValidationAppError("Pick at least one country, or release globally.")

    current = await db.fetch_one(
        "SELECT id, release_scope FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if current is None:
        raise NotFoundError("Product not found.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM product_release_countries WHERE product_id = ?", (product_id,)),
        *[
            (
                "INSERT INTO product_release_countries"
                " (product_id, country_code, added_at, added_by) VALUES (?, ?, ?, ?)",
                (product_id, code, now, actor.user_id),
            )
            for code in codes
        ],
        (
            "UPDATE products SET release_scope = ?, updated_at = ?, updated_by = ?"
            " WHERE id = ?",
            (scope, now, actor.user_id, product_id),
        ),
        audit_statement(
            action="product.release_updated",
            entity_type="product",
            entity_id=product_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"release_scope": current["release_scope"]},
            after={"release_scope": scope, "countries": codes},
        ),
    ]
    await db.batch(statements)
    return {"id": product_id, "release_scope": scope, "release_countries": codes}


async def set_category_release(
    db: Database,
    actor: Principal,
    request_id: str,
    category_id: str,
    *,
    scope: str,
    countries: list[str],
) -> dict[str, Any]:
    """Replace a category's geo release: global, or a specific country list.
    Mirrors `set_product_release` exactly so a category page can be limited to
    selected countries the same way a product can."""
    if scope not in ("global", "selected"):
        raise ValidationAppError("Release scope must be 'global' or 'selected'.")
    codes = _normalize_country_codes(countries) if scope == "selected" else []
    if scope == "selected" and not codes:
        raise ValidationAppError("Pick at least one country, or release globally.")

    current = await db.fetch_one(
        "SELECT id, release_scope FROM categories WHERE id = ? AND archived_at IS NULL",
        (category_id,),
    )
    if current is None:
        raise NotFoundError("Category not found.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM category_release_countries WHERE category_id = ?", (category_id,)),
        *[
            (
                "INSERT INTO category_release_countries"
                " (category_id, country_code, added_at, added_by) VALUES (?, ?, ?, ?)",
                (category_id, code, now, actor.user_id),
            )
            for code in codes
        ],
        (
            "UPDATE categories SET release_scope = ?, updated_at = ?, updated_by = ?"
            " WHERE id = ?",
            (scope, now, actor.user_id, category_id),
        ),
        audit_statement(
            action="category.release_updated",
            entity_type="category",
            entity_id=category_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"release_scope": current["release_scope"]},
            after={"release_scope": scope, "countries": codes},
        ),
    ]
    await db.batch(statements)
    return {"id": category_id, "release_scope": scope, "release_countries": codes}


async def set_product_links(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    *,
    linked_product_ids: list[str],
) -> dict[str, Any]:
    """Replace the owner-curated 'goes well with' slots for a product, keeping
    the given order. An empty list clears them (storefront falls back to
    same-category picks)."""
    ordered: list[str] = []
    for linked_id in linked_product_ids:
        if linked_id == product_id or linked_id in ordered:
            continue
        ordered.append(linked_id)
    if len(ordered) > _MAX_PRODUCT_LINKS:
        raise ValidationAppError(f"At most {_MAX_PRODUCT_LINKS} linked products are supported.")

    current = await db.fetch_one(
        "SELECT id FROM products WHERE id = ? AND archived_at IS NULL", (product_id,)
    )
    if current is None:
        raise NotFoundError("Product not found.")
    if ordered:
        placeholders = ", ".join("?" for _ in ordered)
        rows = await db.fetch_all(
            f"SELECT id FROM products WHERE id IN ({placeholders}) AND archived_at IS NULL",
            ordered,
        )
        found = {row["id"] for row in rows}
        missing = [linked_id for linked_id in ordered if linked_id not in found]
        if missing:
            raise ValidationAppError(f"Unknown linked products: {', '.join(missing)}.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM product_links WHERE product_id = ?", (product_id,)),
        *[
            (
                "INSERT INTO product_links"
                " (product_id, linked_product_id, sort_order, created_at, created_by)"
                " VALUES (?, ?, ?, ?, ?)",
                (product_id, linked_id, index, now, actor.user_id),
            )
            for index, linked_id in enumerate(ordered)
        ],
        audit_statement(
            action="product.links_updated",
            entity_type="product",
            entity_id=product_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"linked_product_ids": ordered},
        ),
    ]
    await db.batch(statements)
    return {"id": product_id, "linked_product_ids": ordered}


async def set_highlighted_products(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    product_ids: list[str],
) -> dict[str, Any]:
    """Replace the site-wide highlighted products (search page slots), keeping
    the given order. The owner swaps products by saving a new list."""
    ordered: list[str] = []
    for product_id in product_ids:
        if product_id not in ordered:
            ordered.append(product_id)
    if len(ordered) > _MAX_HIGHLIGHTS:
        raise ValidationAppError(f"At most {_MAX_HIGHLIGHTS} highlighted products are supported.")
    if ordered:
        placeholders = ", ".join("?" for _ in ordered)
        rows = await db.fetch_all(
            f"SELECT id FROM products WHERE id IN ({placeholders}) AND archived_at IS NULL",
            ordered,
        )
        found = {row["id"] for row in rows}
        missing = [product_id for product_id in ordered if product_id not in found]
        if missing:
            raise ValidationAppError(f"Unknown products: {', '.join(missing)}.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM highlighted_products", ()),
        *[
            (
                "INSERT INTO highlighted_products (product_id, sort_order, added_at, added_by)"
                " VALUES (?, ?, ?, ?)",
                (product_id, index, now, actor.user_id),
            )
            for index, product_id in enumerate(ordered)
        ],
        audit_statement(
            action="site.highlights_updated",
            entity_type="site",
            entity_id="highlighted_products",
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"product_ids": ordered},
        ),
    ]
    await db.batch(statements)
    return {"product_ids": ordered}


async def archive_product(
    db: Database, actor: Principal, request_id: str, product_id: str
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id, status FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if current is None:
        raise NotFoundError("Product not found.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE products SET status = 'archived', archived_at = ?, updated_at = ?,"
                " updated_by = ? WHERE id = ?",
                (now, now, actor.user_id, product_id),
            ),
            audit_statement(
                action="product.archived",
                entity_type="product",
                entity_id=product_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "archived"},
            ),
        ]
    )
    return {"id": product_id, "status": "archived"}


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


async def create_category(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    name: str,
    slug: str | None = None,
    short_description: str | None = None,
    hero_title: str | None = None,
    hero_description: str | None = None,
) -> dict[str, Any]:
    name = _clean_name(name)
    slug = _resolve_slug(name, slug)
    if await _slug_taken(db, "categories", slug):
        raise ConflictError("A category with this slug already exists.")
    if await db.fetch_one("SELECT id FROM categories WHERE path = ?", (slug,)) is not None:
        raise ConflictError("A category with this path already exists.")

    category_id = new_id("cat")
    now = utc_now_iso()
    await db.batch(
        [
            (
                """
                INSERT INTO categories (
                  id, internal_name, name, slug, path, level, sort_order,
                  status, visibility, short_description, hero_title, hero_description,
                  product_assignment_mode, indexing_policy,
                  created_at, created_by, updated_at, updated_by
                ) VALUES (?, ?, ?, ?, ?, 0, 0, 'draft', 'public', ?, ?, ?, 'manual', 'index',
                          ?, ?, ?, ?)
                """,
                (
                    category_id,
                    name,
                    name,
                    slug,
                    slug,
                    short_description,
                    hero_title,
                    hero_description,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="category.created",
                entity_type="category",
                entity_id=category_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"name": name, "slug": slug, "status": "draft"},
            ),
        ]
    )
    return {"id": category_id, "slug": slug, "status": "draft"}


async def update_category(
    db: Database,
    actor: Principal,
    request_id: str,
    category_id: str,
    *,
    fields: dict[str, Any],
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id, name, slug, path, parent_id, short_description, hero_eyebrow, hero_title,"
        " hero_description, season_label, theme_key, visibility, seo_title, seo_description,"
        " hero_image_url, hero_image_alt, status"
        " FROM categories WHERE id = ? AND archived_at IS NULL",
        (category_id,),
    )
    if current is None:
        raise NotFoundError("Category not found.")

    updates = _collect_updates(fields, _CATEGORY_EDITABLE, current)
    if "name" in updates:
        updates["name"] = _clean_name(updates["name"])
    if "visibility" in updates and updates["visibility"] not in ("public", "hidden", "private"):
        raise ValidationAppError("Visibility must be public, hidden, or private.")
    if "slug" in updates:
        new_slug = validate_slug(str(updates["slug"]).strip())
        updates["slug"] = new_slug
        if await _slug_taken(db, "categories", new_slug, exclude_id=category_id):
            raise ConflictError("A category with this slug already exists.")
        updates["path"] = await _category_path(db, current["parent_id"], new_slug, category_id)
    if not updates:
        return {"id": category_id, "status": current["status"], "changed": False}

    await _apply_update(
        db,
        table="categories",
        entity_type="category",
        action="category.updated",
        entity_id=category_id,
        actor=actor,
        request_id=request_id,
        current=current,
        updates=updates,
    )
    return {"id": category_id, "status": current["status"], "changed": True}


async def archive_category(
    db: Database, actor: Principal, request_id: str, category_id: str
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id, status FROM categories WHERE id = ? AND archived_at IS NULL",
        (category_id,),
    )
    if current is None:
        raise NotFoundError("Category not found.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE categories SET status = 'archived', archived_at = ?, updated_at = ?,"
                " updated_by = ? WHERE id = ?",
                (now, now, actor.user_id, category_id),
            ),
            audit_statement(
                action="category.archived",
                entity_type="category",
                entity_id=category_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "archived"},
            ),
        ]
    )
    return {"id": category_id, "status": "archived"}


async def _category_path(db: Database, parent_id: str | None, slug: str, category_id: str) -> str:
    if parent_id is None:
        path = slug
    else:
        parent = await db.fetch_one("SELECT path FROM categories WHERE id = ?", (parent_id,))
        path = f"{parent['path']}/{slug}" if parent else slug
    clash = await db.fetch_one(
        "SELECT id FROM categories WHERE path = ? AND id != ?", (path, category_id)
    )
    if clash is not None:
        raise ConflictError("A category with this path already exists.")
    return path


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _collect_updates(
    fields: dict[str, Any], allowed: tuple[str, ...], current: dict[str, Any]
) -> dict[str, Any]:
    """Keep only allowed keys whose value actually differs from the current row."""
    updates: dict[str, Any] = {}
    for key in allowed:
        if key in fields and fields[key] != current.get(key):
            updates[key] = fields[key]
    return updates


async def _apply_update(
    db: Database,
    *,
    table: str,
    entity_type: str,
    action: str,
    entity_id: str,
    actor: Principal,
    request_id: str,
    current: dict[str, Any],
    updates: dict[str, Any],
) -> None:
    now = utc_now_iso()
    assignments = ", ".join(f"{column} = ?" for column in updates)
    params = [*updates.values(), now, actor.user_id, entity_id]
    before = {key: current.get(key) for key in updates}
    await db.batch(
        [
            (
                f"UPDATE {table} SET {assignments}, updated_at = ?, updated_by = ? WHERE id = ?",
                params,
            ),
            audit_statement(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before=before,
                after=updates,
            ),
        ]
    )

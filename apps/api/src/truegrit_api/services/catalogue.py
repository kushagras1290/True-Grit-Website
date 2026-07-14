"""Catalogue mutations: create / update / archive for products and categories.

Each operation writes its entity change and its audit record in a single
`db.batch`, so a partial failure rolls back and nothing lands unaudited. Slugs
are validated and checked for uniqueness (excluding the row being edited).
Publishing lives in `services.publishing`; these functions manage the working
row that publishing later snapshots.
"""

from __future__ import annotations

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
        " image_url, image_alt, status"
        " FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if current is None:
        raise NotFoundError("Product not found.")

    updates = _collect_updates(fields, _PRODUCT_EDITABLE, current)
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

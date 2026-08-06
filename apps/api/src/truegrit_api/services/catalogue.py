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
from urllib.parse import urlparse

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.feature_settings import load_curated_max_items
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_PRODUCT_EDITABLE = (
    "name",
    "slug",
    "short_description",
    "harvest_note",
    "growing_method",
    "storage_guidance",
    "seo_title",
    "seo_description",
    "image_url",
    "image_alt",
    "return_eligible",
    "accepts_orders",
    "payments_override",
    "farm_id",
    "primary_media_id",
)
# Mirrors the CHECK constraint on `products.payments_override` (migration
# 0069) -- validated here too so a bad value 400s before it ever reaches SQL.
_PAYMENTS_OVERRIDE_VALUES = frozenset({"inherit", "force_enabled", "force_disabled"})
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
        "SELECT id, name, slug, short_description, harvest_note, growing_method,"
        " storage_guidance, seo_title, seo_description,"
        " image_url, image_alt, status, return_eligible, accepts_orders,"
        " payments_override, farm_id, primary_media_id"
        " FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if current is None:
        raise NotFoundError("Product not found.")
    # The admin "Unassigned" farm option can only round-trip as "" -- a native
    # <select> has no way to hold null -- so every save of an unassigned
    # product resubmits farm_id: "". Without this, that "" would go straight
    # into an UPDATE against a column with FOREIGN KEY ... REFERENCES farms(id)
    # (migration 0002), which SQLite rejects outright: not a validation error,
    # a raw constraint failure that 500s before any response middleware (incl.
    # CORS) runs, which the browser then reports as an opaque CORS failure.
    if fields.get("farm_id") == "":
        fields["farm_id"] = None
    # A farm-owner sub-admin's edit rights stop at their own farm's roster --
    # reassigning `farm_id` would hand the product to (or detach it from) a
    # farm they may not even see, which is a scope change, not a content edit.
    # Unrestricted staff (actor.farm_id is None) are unaffected.
    if (
        actor.farm_id is not None
        and "farm_id" in fields
        and fields["farm_id"] != current["farm_id"]
    ):
        raise ValidationAppError("Only unrestricted staff may reassign a product's farm.")

    # The admin reader deliberately prefers primary_media_id over image_url.
    # Keep both representations in sync when an editor replaces the URL;
    # otherwise the stale primary asset wins after reload and the UI continues
    # requesting the old (possibly deleted) object.
    if "image_url" in fields:
        image_path = urlparse(str(fields["image_url"] or "")).path
        object_key = (
            image_path.removeprefix("/media/") if image_path.startswith("/media/") else None
        )
        media = (
            await db.fetch_one("SELECT id FROM media_assets WHERE object_key = ?", (object_key,))
            if object_key
            else None
        )
        fields["primary_media_id"] = media["id"] if media else None

    updates = _collect_updates(fields, _PRODUCT_EDITABLE, current)
    if "return_eligible" in updates:
        updates["return_eligible"] = 1 if updates["return_eligible"] else 0
    if "accepts_orders" in updates:
        updates["accepts_orders"] = 1 if updates["accepts_orders"] else 0
    if "payments_override" in updates and updates["payments_override"] not in (
        _PAYMENTS_OVERRIDE_VALUES
    ):
        raise ValidationAppError(
            "payments_override must be one of: " + ", ".join(sorted(_PAYMENTS_OVERRIDE_VALUES))
        )
    if "name" in updates:
        updates["name"] = _clean_name(updates["name"])
    if "slug" in updates:
        updates["slug"] = validate_slug(str(updates["slug"]).strip())
        if await _slug_taken(db, "products", updates["slug"], exclude_id=product_id):
            raise ConflictError("A product with this slug already exists.")
    relational_fields = ("category_ids", "diet_tag_ids", "certification_ids")
    if not updates and not any(field in fields for field in relational_fields):
        return {"id": product_id, "status": current["status"], "changed": False}

    if updates:
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

    if "category_ids" in fields:
        category_ids = fields["category_ids"]
        if not isinstance(category_ids, list):
            category_ids = []
        now = utc_now_iso()
        statements = [
            ("DELETE FROM product_categories WHERE product_id = ?", (product_id,)),
        ]
        for idx, cat_id in enumerate(category_ids):
            statements.append(
                (
                    "INSERT INTO product_categories"
                    " (product_id, category_id, is_primary, sort_order, assigned_at, assigned_by)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (product_id, cat_id, 1 if idx == 0 else 0, idx, now, actor.user_id),
                )
            )
        await db.batch(statements)

    if "diet_tag_ids" in fields:
        diet_tag_ids = fields["diet_tag_ids"]
        if not isinstance(diet_tag_ids, list):
            diet_tag_ids = []
        # Scoped to tag_group = 'diet' tags only -- a blanket delete of every
        # product_tags row would also wipe out any intention/attribute/
        # general tags the product carries, which this field never touches.
        statements: list[tuple[str, Any]] = [
            (
                "DELETE FROM product_tags WHERE product_id = ? AND tag_id IN"
                " (SELECT id FROM tags WHERE tag_group = 'diet')",
                (product_id,),
            ),
        ]
        for tag_id in diet_tag_ids:
            statements.append(
                (
                    "INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)",
                    (product_id, tag_id),
                )
            )
        await db.batch(statements)

    if "certification_ids" in fields:
        certification_ids = fields["certification_ids"]
        if not isinstance(certification_ids, list):
            certification_ids = []
        # An admin assigning a certification here is an authoritative action
        # (they verified the paperwork), not a farmer's own claim awaiting
        # review, so this writes 'approved' directly rather than 'pending'.
        statements: list[tuple[str, Any]] = [
            ("DELETE FROM product_certifications WHERE product_id = ?", (product_id,)),
        ]
        for certification_id in certification_ids:
            statements.append(
                (
                    "INSERT INTO product_certifications"
                    " (product_id, certification_id, claim_review_state)"
                    " VALUES (?, ?, 'approved')",
                    (product_id, certification_id),
                )
            )
        await db.batch(statements)

    return {"id": product_id, "status": current["status"], "changed": True}


_MAX_PRODUCT_IMAGES = 8


async def replace_product_images(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    images: list[dict[str, Any]],
) -> None:
    """Full replace, not incremental add/remove -- a product's gallery is
    edited as an ordered set (pick the photos, put them in order, save), the
    same 'delete then reinsert' pattern `replace_bundle_items` already uses.
    Never touches `products.image_url`/`primary_media_id`: the main image
    stays a wholly separate field (see migration 0066's WHY note)."""
    product = await db.fetch_one(
        "SELECT id FROM products WHERE id = ? AND archived_at IS NULL", (product_id,)
    )
    if product is None:
        raise NotFoundError("Product not found.")
    if len(images) > _MAX_PRODUCT_IMAGES:
        raise ValidationAppError(
            f"A product can hold at most {_MAX_PRODUCT_IMAGES} gallery images."
        )

    cleaned: list[dict[str, Any]] = []
    for index, image in enumerate(images):
        url = str(image.get("image_url") or "").strip()
        if not url:
            raise ValidationAppError("Each gallery image needs a URL.")
        alt = str(image.get("image_alt") or "").strip()[:200] or None
        cleaned.append({"image_url": url, "image_alt": alt, "sort_order": index})

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM product_images WHERE product_id = ?", (product_id,)),
    ]
    for image in cleaned:
        statements.append(
            (
                "INSERT INTO product_images"
                " (id, product_id, image_url, image_alt, sort_order, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("pimg"),
                    product_id,
                    image["image_url"],
                    image["image_alt"],
                    image["sort_order"],
                    now,
                ),
            )
        )
    statements.append(
        audit_statement(
            action="product.images_replaced",
            entity_type="product",
            entity_id=product_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"imageCount": len(cleaned)},
        )
    )
    await db.batch(statements)


async def set_product_status(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    status: str,
) -> dict[str, Any]:
    if status not in {"published", "unpublished"}:
        raise ValidationAppError("Invalid status.")

    current = await db.fetch_one(
        "SELECT status FROM products WHERE id = ? AND archived_at IS NULL", (product_id,)
    )
    if current is None:
        raise NotFoundError("Product not found.")

    if current["status"] == status:
        return {"id": product_id, "status": status, "changed": False}

    updates = {"status": status}
    await _apply_update(
        db,
        table="products",
        entity_type="product",
        action=f"product.status.{status}",
        entity_id=product_id,
        actor=actor,
        request_id=request_id,
        current=current,
        updates=updates,
    )
    return {"id": product_id, "status": status, "changed": True}


async def create_variant(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    *,
    name: str,
    sku: str,
    list_minor: int,
    sale_minor: int | None = None,
) -> str:
    product = await db.fetch_one(
        "SELECT id FROM products WHERE id = ? AND archived_at IS NULL", (product_id,)
    )
    if not product:
        raise NotFoundError("Product not found.")

    sku = str(sku).strip()
    row = await db.fetch_one("SELECT id FROM product_variants WHERE sku = ?", (sku,))
    if row:
        raise ConflictError("A variant with this SKU already exists.")
    if sale_minor is not None and sale_minor > list_minor:
        raise ValidationAppError("Sale price cannot be greater than list price.")

    variant_id = new_id("var")
    price_id = new_id("vpr")
    now = utc_now_iso()

    await db.batch(
        [
            (
                "INSERT INTO product_variants"
                " (id, product_id, sku, name, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'active', ?, ?)",
                (variant_id, product_id, sku, name.strip(), now, now),
            ),
            (
                "INSERT INTO variant_prices"
                " (id, variant_id, market_code, currency_code, list_amount_minor,"
                " sale_amount_minor, starts_at, status, created_at, created_by)"
                " VALUES (?, ?, 'IN', 'INR', ?, ?, ?, 'active', ?, ?)",
                (price_id, variant_id, list_minor, sale_minor, now, now, actor.user_id),
            ),
            audit_statement(
                action="variant.created",
                entity_type="variant",
                entity_id=variant_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "sku": sku,
                    "name": name,
                    "list_minor": list_minor,
                    "sale_minor": sale_minor,
                },
            ),
        ]
    )
    return variant_id


async def update_variant(
    db: Database,
    actor: Principal,
    request_id: str,
    product_id: str,
    variant_id: str,
    *,
    name: str | None = None,
    sku: str | None = None,
    list_minor: int | None = None,
    sale_minor: int | None = None,
) -> dict[str, Any]:
    variant = await db.fetch_one(
        "SELECT id, sku, name FROM product_variants WHERE id = ? AND product_id = ?",
        (variant_id, product_id),
    )
    if not variant:
        raise NotFoundError("Variant not found.")

    price = await db.fetch_one(
        "SELECT id, list_amount_minor, sale_amount_minor FROM variant_prices"
        " WHERE variant_id = ? AND status = 'active' ORDER BY starts_at DESC LIMIT 1",
        (variant_id,),
    )

    now = utc_now_iso()
    batch = []
    after = {}

    if sku is not None and sku.strip() != variant["sku"]:
        sku_clean = sku.strip()
        row = await db.fetch_one(
            "SELECT id FROM product_variants WHERE sku = ? AND id != ?", (sku_clean, variant_id)
        )
        if row:
            raise ConflictError("A variant with this SKU already exists.")
        batch.append(
            (
                "UPDATE product_variants SET sku = ?, updated_at = ? WHERE id = ?",
                (sku_clean, now, variant_id),
            )
        )
        after["sku"] = sku_clean

    if name is not None and name.strip() != variant["name"]:
        name_clean = name.strip()
        batch.append(
            (
                "UPDATE product_variants SET name = ?, updated_at = ? WHERE id = ?",
                (name_clean, now, variant_id),
            )
        )
        after["name"] = name_clean

    if price:
        new_list = list_minor if list_minor is not None else price["list_amount_minor"]
        current_sale = price["sale_amount_minor"]
        # Allow clearing sale price if explicitly set or use current_sale
        new_sale = sale_minor if sale_minor is not None else current_sale
        if sale_minor == -1:  # hack to clear it
            new_sale = None
        if new_sale is not None and new_sale > new_list:
            raise ValidationAppError("Sale price cannot be greater than list price.")

        if new_list != price["list_amount_minor"] or new_sale != current_sale:
            batch.append(
                (
                    "UPDATE variant_prices SET list_amount_minor = ?, sale_amount_minor = ?"
                    " WHERE id = ?",
                    (new_list, new_sale, price["id"]),
                )
            )
            after["list_minor"] = new_list
            after["sale_minor"] = new_sale
    elif list_minor is not None:
        price_id = new_id("vpr")
        real_sale = None if sale_minor == -1 else sale_minor
        batch.append(
            (
                "INSERT INTO variant_prices"
                " (id, variant_id, market_code, currency_code, list_amount_minor,"
                " sale_amount_minor, starts_at, status, created_at, created_by)"
                " VALUES (?, ?, 'IN', 'INR', ?, ?, ?, 'active', ?, ?)",
                (price_id, variant_id, list_minor, real_sale, now, now, actor.user_id),
            )
        )
        after["list_minor"] = list_minor
        after["sale_minor"] = real_sale

    if batch:
        batch.append(
            audit_statement(
                action="variant.updated",
                entity_type="variant",
                entity_id=variant_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=after,
            )
        )
        await db.batch(batch)
        return {"id": variant_id, "changed": True}

    return {"id": variant_id, "changed": False}


_COUNTRY_CODE = re.compile(r"^[A-Za-z]{2}$")
_MAX_RELEASE_COUNTRIES = 100
_MAX_PRODUCT_LINKS = 12


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
            "UPDATE products SET release_scope = ?, updated_at = ?, updated_by = ? WHERE id = ?",
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
            "UPDATE categories SET release_scope = ?, updated_at = ?, updated_by = ? WHERE id = ?",
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
    max_items = await load_curated_max_items(db)
    if len(ordered) > max_items:
        raise ValidationAppError(f"At most {max_items} highlighted products are supported.")
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


async def set_category_status(
    db: Database,
    actor: Principal,
    request_id: str,
    category_id: str,
    status: str,
) -> dict[str, Any]:
    """One-click enable/disable. An unpublished category disappears from the
    public API immediately, so homepage category collections and navigation
    stop showing it without any storefront redeploy (mirrors
    ``set_product_status``)."""
    if status not in {"published", "unpublished"}:
        raise ValidationAppError("Invalid status.")

    current = await db.fetch_one(
        "SELECT status FROM categories WHERE id = ? AND archived_at IS NULL", (category_id,)
    )
    if current is None:
        raise NotFoundError("Category not found.")

    if current["status"] == status:
        return {"id": category_id, "status": status, "changed": False}

    await _apply_update(
        db,
        table="categories",
        entity_type="category",
        action=f"category.status.{status}",
        entity_id=category_id,
        actor=actor,
        request_id=request_id,
        current=current,
        updates={"status": status},
    )
    return {"id": category_id, "status": status, "changed": True}


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

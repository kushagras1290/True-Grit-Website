"""Product bundles (migration 0062): curated sets of specific variants sold
together at a flat advertised price.

Writes here cover the admin CRUD surface (create/update/delete a bundle,
replace its item list). `resolve_bundle_discount` is read-only by design,
the same reasoning `services.promotions.resolve_checkout_discount` documents:
it is called from `services.checkout.place_order`, which owns the order's
batch and is responsible for actually writing the discount into
`order_adjustments` alongside the order itself, so a discount can never be
computed without being recorded, or recorded without an order behind it.

A bundle discount and a coupon/promotion discount are independent and both
apply when both match -- a bundle is a catalogue price, a coupon is a
marketing code, and there is no reason a customer should be denied one for
having the other. See `services.checkout` for how the two amounts combine.
"""

from __future__ import annotations

from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.repositories.bundles import BundleRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_NAME: Final = 140
_MAX_DESCRIPTION: Final = 500
_MAX_ITEMS: Final = 12
_STATUSES: Final = frozenset({"draft", "active", "ended", "archived"})


def _clean_name(name: str) -> str:
    cleaned = name.strip()
    if not cleaned or len(cleaned) > _MAX_NAME:
        raise ValidationAppError(f"Name must be 1-{_MAX_NAME} characters.")
    return cleaned


async def _assert_farm_owns_bundle(db: Database, actor: Principal, bundle_id: str) -> None:
    """Dormant today -- no seeded role holds `bundles.manage` and a `farm_id`
    at once -- but kept correct in case that combination is ever granted. A
    bundle can span farms (via its items' products), so a farm-scoped
    principal may only touch one that is entirely their own, the same
    all-or-nothing rule `services.orders._assert_farm_owns_order` uses."""
    if actor.farm_id is None:
        return
    owned = await db.fetch_one(
        """
        SELECT NOT EXISTS (
          SELECT 1 FROM bundle_items bi
          JOIN product_variants v ON v.id = bi.variant_id
          JOIN products p ON p.id = v.product_id
          WHERE bi.bundle_id = ? AND (p.farm_id IS NULL OR p.farm_id != ?)
        ) AS fully_owned
        """,
        (bundle_id, actor.farm_id),
    )
    if owned is None or not owned["fully_owned"]:
        raise PermissionDeniedError(
            "This bundle includes another farm's products; only an administrator can change it."
        )


async def create_bundle(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    name: str,
    slug: str | None,
    description: str | None,
    status: str,
    bundle_price_minor: int,
    image_url: str | None,
    image_alt: str | None,
) -> dict[str, Any]:
    clean_name = _clean_name(name)
    if status not in _STATUSES:
        raise ValidationAppError("Unsupported status.")
    if bundle_price_minor < 0:
        raise ValidationAppError("Bundle price must be zero or more.")
    clean_slug = validate_slug(slug.strip()) if slug else slugify(clean_name)
    existing = await db.fetch_one("SELECT id FROM bundles WHERE slug = ?", (clean_slug,))
    if existing is not None:
        raise ConflictError(f'A bundle with the slug "{clean_slug}" already exists.')

    now = utc_now_iso()
    bundle_id = new_id("bndl")
    await db.batch(
        [
            (
                """
                INSERT INTO bundles
                  (id, name, slug, description, status, bundle_price_minor,
                   image_url, image_alt, created_at, created_by, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bundle_id,
                    clean_name,
                    clean_slug,
                    (description or "").strip()[:_MAX_DESCRIPTION] or None,
                    status,
                    bundle_price_minor,
                    (image_url or "").strip() or None,
                    (image_alt or "").strip() or None,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="bundle.created",
                entity_type="bundle",
                entity_id=bundle_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"name": clean_name, "slug": clean_slug, "status": status},
            ),
        ]
    )
    return {"id": bundle_id, "slug": clean_slug, "status": status}


async def update_bundle(
    db: Database, actor: Principal, request_id: str, bundle_id: str, fields: dict[str, Any]
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM bundles WHERE id = ?", (bundle_id,))
    if current is None:
        raise NotFoundError("Bundle not found.")
    await _assert_farm_owns_bundle(db, actor, bundle_id)

    updates: dict[str, Any] = {}
    if "name" in fields:
        updates["name"] = _clean_name(fields["name"])
    if fields.get("slug"):
        clean_slug = validate_slug(str(fields["slug"]).strip())
        existing = await db.fetch_one(
            "SELECT id FROM bundles WHERE slug = ? AND id != ?", (clean_slug, bundle_id)
        )
        if existing is not None:
            raise ConflictError(f'A bundle with the slug "{clean_slug}" already exists.')
        updates["slug"] = clean_slug
    if "description" in fields:
        updates["description"] = (fields["description"] or "").strip()[:_MAX_DESCRIPTION] or None
    if "status" in fields:
        if fields["status"] not in _STATUSES:
            raise ValidationAppError("Unsupported status.")
        updates["status"] = fields["status"]
    if "bundle_price_minor" in fields:
        price = fields["bundle_price_minor"]
        if not isinstance(price, int) or price < 0:
            raise ValidationAppError("Bundle price must be zero or more.")
        updates["bundle_price_minor"] = price
    if "image_url" in fields:
        updates["image_url"] = (fields["image_url"] or "").strip() or None
    if "image_alt" in fields:
        updates["image_alt"] = (fields["image_alt"] or "").strip() or None

    if not updates:
        return {"id": bundle_id, "status": current["status"]}

    now = utc_now_iso()
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    await db.batch(
        [
            (
                f"UPDATE bundles SET {set_clause}, updated_at = ?, updated_by = ? WHERE id = ?",
                (*updates.values(), now, actor.user_id, bundle_id),
            ),
            audit_statement(
                action="bundle.updated",
                entity_type="bundle",
                entity_id=bundle_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={key: current[key] for key in updates},
                after=updates,
            ),
        ]
    )
    return {"id": bundle_id, "status": updates.get("status", current["status"])}


async def delete_bundle(db: Database, actor: Principal, request_id: str, bundle_id: str) -> None:
    current = await db.fetch_one("SELECT id FROM bundles WHERE id = ?", (bundle_id,))
    if current is None:
        raise NotFoundError("Bundle not found.")
    await _assert_farm_owns_bundle(db, actor, bundle_id)
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM bundles WHERE id = ?", (bundle_id,)),
            audit_statement(
                action="bundle.deleted",
                entity_type="bundle",
                entity_id=bundle_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )


async def replace_bundle_items(
    db: Database,
    actor: Principal,
    request_id: str,
    bundle_id: str,
    items: list[dict[str, Any]],
) -> None:
    """Full replace, not incremental add/remove: a bundle's contents are
    edited as a set (matching how the admin form presents them -- pick the
    variants and quantities, save), the same 'delete then reinsert' pattern
    `product_categories` assignment already uses elsewhere in this codebase.
    """
    bundle = await db.fetch_one("SELECT id FROM bundles WHERE id = ?", (bundle_id,))
    if bundle is None:
        raise NotFoundError("Bundle not found.")
    await _assert_farm_owns_bundle(db, actor, bundle_id)
    if len(items) > _MAX_ITEMS:
        raise ValidationAppError(f"A bundle can hold at most {_MAX_ITEMS} items.")
    if not items:
        raise ValidationAppError("A bundle needs at least one item.")

    seen_variants: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        variant_id = str(item.get("variant_id") or "").strip()
        quantity = item.get("quantity")
        if not variant_id:
            raise ValidationAppError("Each bundle item needs a variant.")
        if variant_id in seen_variants:
            raise ValidationAppError("Each variant can only appear once in a bundle.")
        if not isinstance(quantity, int) or quantity < 1:
            raise ValidationAppError("Each bundle item needs a quantity of at least 1.")
        seen_variants.add(variant_id)
        cleaned.append({"variant_id": variant_id, "quantity": quantity, "sort_order": index})

    variant_rows = await db.fetch_all(
        f"""
        SELECT v.id, p.farm_id FROM product_variants v
        JOIN products p ON p.id = v.product_id
        WHERE v.id IN ({", ".join("?" for _ in cleaned)})
        """,
        tuple(item["variant_id"] for item in cleaned),
    )
    found_ids = {row["id"] for row in variant_rows}
    missing = [item["variant_id"] for item in cleaned if item["variant_id"] not in found_ids]
    if missing:
        raise ValidationAppError(f"Unknown variant id(s): {', '.join(missing)}.")
    # A farm-scoped principal cannot smuggle another farm's variant into a
    # bundle they otherwise own -- same posture as `services.catalogue`
    # refusing to let a product be reassigned off a farm-owner's own farm.
    if actor.farm_id is not None:
        foreign = [row["id"] for row in variant_rows if row["farm_id"] != actor.farm_id]
        if foreign:
            raise PermissionDeniedError(
                "A bundle you manage can only contain your own farm's products."
            )

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM bundle_items WHERE bundle_id = ?", (bundle_id,)),
    ]
    for item in cleaned:
        statements.append(
            (
                "INSERT INTO bundle_items (id, bundle_id, variant_id, quantity, sort_order)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    new_id("bndi"),
                    bundle_id,
                    item["variant_id"],
                    item["quantity"],
                    item["sort_order"],
                ),
            )
        )
    statements.append(
        (
            "UPDATE bundles SET updated_at = ?, updated_by = ? WHERE id = ?",
            (now, actor.user_id, bundle_id),
        )
    )
    statements.append(
        audit_statement(
            action="bundle.items_replaced",
            entity_type="bundle",
            entity_id=bundle_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"itemCount": len(cleaned)},
        )
    )
    await db.batch(statements)


async def resolve_bundle_discount(
    db: Database, resolved_lines: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """What, if any, bundle discount this cart earns. `resolved_lines` is
    `services.checkout._resolve_line`'s own per-line output -- reusing its
    already-fetched `unit_effective_minor` rather than re-pricing, so a
    bundle's savings are always measured against the exact price the
    customer is being charged for each component, sale price included.

    Returns the single largest-discount matching bundle when several qualify
    -- bundles are not stacked with each other, the same simplicity
    `resolve_checkout_discount` holds for promotions.
    """
    cart_by_variant = {item["variant"]["variant_id"]: item for item in resolved_lines}
    if not cart_by_variant:
        return None

    repository = BundleRepository(db)
    candidates = await repository.list_active_matching_variants(list(cart_by_variant))

    best: dict[str, Any] | None = None
    for bundle in candidates:
        component_sum = 0
        matches = True
        for bundle_item in bundle["items"]:
            cart_item = cart_by_variant.get(bundle_item["variant_id"])
            if cart_item is None or cart_item["quantity"] < bundle_item["quantity"]:
                matches = False
                break
            component_sum += cart_item["unit_effective_minor"] * bundle_item["quantity"]
        if not matches:
            continue
        discount = max(component_sum - bundle["bundle_price_minor"], 0)
        if discount <= 0:
            continue
        if best is None or discount > best["discount_minor"]:
            best = {
                "bundle_id": bundle["id"],
                "name": bundle["name"],
                "discount_minor": discount,
            }
    return best

"""Wishlist / saved-for-later: a signed-in customer saves a product to
revisit later. Activates the dormant `wishlists`/`wishlist_items` schema
from migration 0005 (see migration 0079's comment) -- product-level, no
status machine, no financial commitment, the simplest customer-owned
resource in this codebase.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.wishlist import WishlistRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def serialize_wishlist_item(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "productId": row["product_id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "imageUrl": row["image_url"],
        "variantId": row["variant_id"],
        "variantName": row["variant_name"],
        "sku": row["sku"],
        "unitPriceMinor": row["unit_price_minor"],
        "currencyCode": row["currency_code"],
        "addedAt": row["added_at"],
    }


async def _assert_product_exists(db: Database, product_id: str) -> None:
    row = await db.fetch_one(
        "SELECT id FROM products WHERE id = ? AND status = 'published'", (product_id,)
    )
    if row is None:
        raise ValidationAppError("This product is not available to save.")


async def _get_or_create_wishlist_id(db: Database, user_id: str, now: str) -> str:
    repository = WishlistRepository(db)
    existing = await repository.get_wishlist_id(user_id)
    if existing is not None:
        return existing
    wishlist_id = new_id("wl")
    # Racing this against a concurrent first-save from the same customer (two
    # tabs) is harmless: `user_id` is UNIQUE on `wishlists`, so the loser's
    # INSERT is ignored rather than erroring, and both end up pointed at the
    # single row that won.
    await db.execute(
        "INSERT OR IGNORE INTO wishlists (id, user_id, created_at) VALUES (?, ?, ?)",
        (wishlist_id, user_id, now),
    )
    resolved = await repository.get_wishlist_id(user_id)
    assert resolved is not None
    return resolved


async def list_my_wishlist(db: Database, customer: Principal) -> list[dict[str, Any]]:
    rows = await WishlistRepository(db).list_for_customer(customer.user_id)
    return [serialize_wishlist_item(row) for row in rows]


async def list_wishlist_product_ids(db: Database, customer: Principal) -> list[str]:
    return await WishlistRepository(db).product_ids_for_customer(customer.user_id)


async def add_to_wishlist(
    db: Database, customer: Principal, request_id: str, *, product_id: str
) -> dict[str, Any]:
    await _assert_product_exists(db, product_id)

    now = utc_now_iso()
    wishlist_id = await _get_or_create_wishlist_id(db, customer.user_id, now)
    await db.batch(
        [
            (
                # INSERT OR IGNORE against the (wishlist_id, product_id)
                # primary key: saving an already-saved product is a no-op,
                # not an error -- a double-clicked heart button can never
                # fail.
                "INSERT OR IGNORE INTO wishlist_items (wishlist_id, product_id, added_at)"
                " VALUES (?, ?, ?)",
                (wishlist_id, product_id, now),
            ),
            audit_statement(
                action="wishlist.item_added",
                entity_type="wishlist_item",
                entity_id=product_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                after={"product_id": product_id},
            ),
        ]
    )
    repository = WishlistRepository(db)
    rows = await repository.list_for_customer(customer.user_id)
    match = next(row for row in rows if row["product_id"] == product_id)
    return serialize_wishlist_item(match)


async def remove_from_wishlist(
    db: Database, customer: Principal, request_id: str, *, product_id: str
) -> None:
    now = utc_now_iso()
    # No existence check first: removing something never saved (or removing
    # from a wishlist that doesn't exist yet because nothing was ever added)
    # is a no-op, not an error -- matches add's idempotent posture in the
    # other direction.
    await db.batch(
        [
            (
                "DELETE FROM wishlist_items"
                " WHERE product_id = ? AND wishlist_id IN"
                " (SELECT id FROM wishlists WHERE user_id = ?)",
                (product_id, customer.user_id),
            ),
            audit_statement(
                action="wishlist.item_removed",
                entity_type="wishlist_item",
                entity_id=product_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )

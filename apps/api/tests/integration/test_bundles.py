"""Product bundles (migration 0062), end to end against checkout.

Uses the seeded catalogue (`var_alphonso_1kg` at 89900, `var_spinach_250g` at
6900) the same way test_promotions.py does, since a bundle's savings are only
meaningful against real variant prices.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}


def as_customer(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def checkout(client: TestClient, items: list[dict[str, Any]]) -> Any:
    return client.post("/v1/public/checkout", json={"items": items, "deliveryAddress": ADDRESS})


def create_active_bundle(
    client: TestClient, db: SQLiteDatabase, *, bundle_price_minor: int = 89_900, **overrides: Any
) -> dict[str, Any]:
    as_admin(client, db)
    body: dict[str, Any] = {
        "name": "Mango & Greens Combo",
        "status": "active",
        "bundlePriceMinor": bundle_price_minor,
    }
    body.update(overrides)
    response = client.post("/v1/admin/bundles", json=body)
    assert response.status_code == 200, response.text
    bundle = response.json()
    items = client.put(
        f"/v1/admin/bundles/{bundle['id']}/items",
        json={
            "items": [
                {"variantId": "var_alphonso_1kg", "quantity": 1},
                {"variantId": "var_spinach_250g", "quantity": 1},
            ]
        },
    )
    assert items.status_code == 200, items.text
    return bundle


def test_admin_can_create_a_bundle_and_set_its_items(client, db):
    bundle = create_active_bundle(client, db)
    detail = client.get(f"/v1/admin/bundles/{bundle['id']}")
    assert detail.status_code == 200
    body = detail.json()
    assert body["status"] == "active"
    assert len(body["items"]) == 2
    skus = {item["sku"] for item in body["items"]}
    assert skus == {"TRG-MNG-1KG", "TRG-SPN-250"}


def test_creating_a_bundle_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.post(
        "/v1/admin/bundles", json={"name": "Nope", "status": "active", "bundlePriceMinor": 1000}
    )
    assert response.status_code == 403


def test_items_replace_rejects_an_unknown_variant(client, db):
    as_admin(client, db)
    bundle = client.post(
        "/v1/admin/bundles",
        json={"name": "Test", "status": "draft", "bundlePriceMinor": 1000},
    ).json()
    response = client.put(
        f"/v1/admin/bundles/{bundle['id']}/items",
        json={"items": [{"variantId": "var_does_not_exist", "quantity": 1}]},
    )
    assert response.status_code == 422


def test_items_replace_rejects_a_duplicate_variant(client, db):
    as_admin(client, db)
    bundle = client.post(
        "/v1/admin/bundles",
        json={"name": "Test", "status": "draft", "bundlePriceMinor": 1000},
    ).json()
    response = client.put(
        f"/v1/admin/bundles/{bundle['id']}/items",
        json={
            "items": [
                {"variantId": "var_alphonso_1kg", "quantity": 1},
                {"variantId": "var_alphonso_1kg", "quantity": 2},
            ]
        },
    )
    assert response.status_code == 422


def test_a_full_basket_earns_the_bundle_discount_at_checkout(client, db):
    create_active_bundle(client, db, bundle_price_minor=89_900)

    as_customer(client, db)
    response = checkout(
        client,
        [
            {"variantId": "var_alphonso_1kg", "quantity": 1},
            {"variantId": "var_spinach_250g", "quantity": 1},
        ],
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # 89900 + 6900 = 96800 priced separately; bundle price 89900 -> saves 6900.
    assert body["discountMinor"] == 6_900
    assert body["totalMinor"] == body["subtotalMinor"] + body["deliveryMinor"] - 6_900

    order_id = db._conn.execute(
        "SELECT id FROM orders WHERE public_reference = ?", (body["reference"],)
    ).fetchone()[0]
    adjustment = db._conn.execute(
        "SELECT adjustment_type, label, amount_minor FROM order_adjustments WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    assert adjustment[0] == "promotion"
    assert "Bundle savings" in adjustment[1]
    assert adjustment[2] == -6_900


def test_a_partial_basket_does_not_earn_the_bundle_discount(client, db):
    create_active_bundle(client, db)

    as_customer(client, db)
    response = checkout(client, [{"variantId": "var_alphonso_1kg", "quantity": 1}])
    assert response.status_code == 200, response.text
    assert response.json()["discountMinor"] == 0


def test_a_draft_bundle_never_applies_at_checkout(client, db):
    as_admin(client, db)
    bundle = client.post(
        "/v1/admin/bundles",
        json={"name": "Not live yet", "status": "draft", "bundlePriceMinor": 89_900},
    ).json()
    client.put(
        f"/v1/admin/bundles/{bundle['id']}/items",
        json={
            "items": [
                {"variantId": "var_alphonso_1kg", "quantity": 1},
                {"variantId": "var_spinach_250g", "quantity": 1},
            ]
        },
    )

    as_customer(client, db)
    response = checkout(
        client,
        [
            {"variantId": "var_alphonso_1kg", "quantity": 1},
            {"variantId": "var_spinach_250g", "quantity": 1},
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["discountMinor"] == 0


def test_bundle_price_at_or_above_component_sum_grants_no_discount(client, db):
    # 96800 is exactly the component sum -- no saving to grant.
    create_active_bundle(client, db, bundle_price_minor=96_800)

    as_customer(client, db)
    response = checkout(
        client,
        [
            {"variantId": "var_alphonso_1kg", "quantity": 1},
            {"variantId": "var_spinach_250g", "quantity": 1},
        ],
    )
    assert response.status_code == 200, response.text
    assert response.json()["discountMinor"] == 0


def test_bundle_and_coupon_discounts_stack(client, db):
    create_active_bundle(client, db, bundle_price_minor=89_900)

    as_admin(client, db)
    settings = client.patch("/v1/admin/storefront-settings", json={"promotions": True})
    assert settings.status_code == 200
    promotion = client.post(
        "/v1/admin/promotions",
        json={
            "name": "Extra ₹50 off",
            "status": "active",
            "actionType": "fixed_discount",
            "amountMinor": 5_000,
        },
    ).json()
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "EXTRA50"})

    as_customer(client, db)
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {"variantId": "var_alphonso_1kg", "quantity": 1},
                {"variantId": "var_spinach_250g", "quantity": 1},
            ],
            "deliveryAddress": ADDRESS,
            "couponCode": "EXTRA50",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    # 6900 (bundle) + 5000 (coupon) = 11900, independent and additive.
    assert body["discountMinor"] == 11_900
    assert body["couponCode"] == "EXTRA50"


def test_public_bundle_listing_and_detail(client, db):
    bundle = create_active_bundle(client, db)

    listing = client.get("/v1/public/bundles")
    assert listing.status_code == 200
    items = listing.json()["items"]
    listed = next(item for item in items if item["id"] == bundle["id"])
    assert listed["savingsMinor"] == 6_900
    assert len(listed["items"]) == 2

    detail = client.get(f"/v1/public/bundles/{bundle['slug']}")
    assert detail.status_code == 200
    assert detail.json()["id"] == bundle["id"]


def test_public_bundle_detail_404s_for_a_draft_bundle(client, db):
    as_admin(client, db)
    bundle = client.post(
        "/v1/admin/bundles",
        json={"name": "Draft only", "status": "draft", "bundlePriceMinor": 1000},
    ).json()
    response = client.get(f"/v1/public/bundles/{bundle['slug']}")
    assert response.status_code == 404


def test_deleting_a_bundle_removes_it(client, db):
    bundle = create_active_bundle(client, db)
    as_admin(client, db)
    deleted = client.delete(f"/v1/admin/bundles/{bundle['id']}")
    assert deleted.status_code == 200
    assert client.get(f"/v1/admin/bundles/{bundle['id']}").status_code == 404

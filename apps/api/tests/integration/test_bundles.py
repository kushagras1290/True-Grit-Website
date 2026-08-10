"""Product bundles (migration 0062), end to end against checkout.

Seeds its own two purchasable products (`var_bundle_fixture_a` at 89900,
`var_bundle_fixture_b` at 6900) rather than depending on the demo catalogue:
migration 0095 retires that catalogue from every database it touches (the
live site must not keep any trace of it), so tests cannot rely on it
surviving either. A bundle's savings are only meaningful against real
variant prices.
"""

from __future__ import annotations

from typing import Any

import pytest
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


@pytest.fixture(autouse=True)
def _bundle_fixture_products(db: SQLiteDatabase) -> None:
    """Two synthetic purchasable products every test in this module builds
    its bundle from -- see the module docstring above for why these are not
    the old demo catalogue's `var_alphonso_1kg` / `var_spinach_250g`."""
    db._conn.executescript(
        """
        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_bundle_fixture_a', 'Bundle Fixture Product A',
          'Bundle Fixture Product A', 'bundle-fixture-product-a', 'simple',
          'published', 1, '2026-07-01T00:00:00Z', 'usr_admin',
          '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('var_bundle_fixture_a', 'prd_bundle_fixture_a', 'BNDL-FIXTURE-A-1KG',
          '1 kg', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_bundle_fixture_a', 'var_bundle_fixture_a', 'IN', 'INR', 89900,
          'active', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('var_bundle_fixture_a', 'loc_mumbai', 500, 0, 20, 1, '2026-07-01T00:00:00Z');

        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_bundle_fixture_b', 'Bundle Fixture Product B',
          'Bundle Fixture Product B', 'bundle-fixture-product-b', 'simple',
          'published', 1, '2026-07-01T00:00:00Z', 'usr_admin',
          '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('var_bundle_fixture_b', 'prd_bundle_fixture_b', 'BNDL-FIXTURE-B-250G',
          '250 g', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_bundle_fixture_b', 'var_bundle_fixture_b', 'IN', 'INR', 6900,
          'active', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('var_bundle_fixture_b', 'loc_mumbai', 500, 0, 20, 1, '2026-07-01T00:00:00Z');
        """
    )
    db._conn.commit()


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
        "name": "Fixture Bundle Combo",
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
                {"variantId": "var_bundle_fixture_a", "quantity": 1},
                {"variantId": "var_bundle_fixture_b", "quantity": 1},
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
    assert skus == {"BNDL-FIXTURE-A-1KG", "BNDL-FIXTURE-B-250G"}


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
                {"variantId": "var_bundle_fixture_a", "quantity": 1},
                {"variantId": "var_bundle_fixture_a", "quantity": 2},
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
            {"variantId": "var_bundle_fixture_a", "quantity": 1},
            {"variantId": "var_bundle_fixture_b", "quantity": 1},
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
    response = checkout(client, [{"variantId": "var_bundle_fixture_a", "quantity": 1}])
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
                {"variantId": "var_bundle_fixture_a", "quantity": 1},
                {"variantId": "var_bundle_fixture_b", "quantity": 1},
            ]
        },
    )

    as_customer(client, db)
    response = checkout(
        client,
        [
            {"variantId": "var_bundle_fixture_a", "quantity": 1},
            {"variantId": "var_bundle_fixture_b", "quantity": 1},
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
            {"variantId": "var_bundle_fixture_a", "quantity": 1},
            {"variantId": "var_bundle_fixture_b", "quantity": 1},
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
                {"variantId": "var_bundle_fixture_a", "quantity": 1},
                {"variantId": "var_bundle_fixture_b", "quantity": 1},
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

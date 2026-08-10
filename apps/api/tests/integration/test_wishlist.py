"""Wishlist (activates the dormant `wishlists`/`wishlist_items` schema from
migration 0005, in migration 0079): add/remove/list, idempotency, and
per-customer scoping.

Seeds its own product (`prd_wishlist_test`) rather than depending on the demo
catalogue: migration 0095 retires that catalogue from every database it
touches (the live site must not keep any trace of it), so tests cannot rely
on it surviving either.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_cust_riya") -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


@pytest.fixture(autouse=True)
def _wishlistable_product(db: SQLiteDatabase) -> None:
    db._conn.executescript(
        """
        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          created_at, created_by, updated_at, updated_by)
        VALUES ('prd_wishlist_test', 'Wishlist Test Product', 'Wishlist Test Product',
          'wishlist-test-product', 'simple', 'published',
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('var_wishlist_test_1kg', 'prd_wishlist_test', 'WISH-TEST-1KG', '1 kg', 'active',
          1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_wishlist_test_1kg', 'var_wishlist_test_1kg', 'IN', 'INR', 89900, 'active',
          '2026-07-01T00:00:00Z', 'usr_admin');
        """
    )
    db._conn.commit()


def test_customer_can_add_list_and_remove_a_wishlist_item(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)

    added = client.post("/v1/public/wishlist", json={"productId": "prd_wishlist_test"})
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["productId"] == "prd_wishlist_test"
    assert body["productName"] == "Wishlist Test Product"
    assert body["unitPriceMinor"] is not None

    listed = client.get("/v1/public/wishlist").json()["items"]
    assert {item["productId"] for item in listed} == {"prd_wishlist_test"}

    ids = client.get("/v1/public/wishlist/product-ids").json()["productIds"]
    assert ids == ["prd_wishlist_test"]

    removed = client.delete("/v1/public/wishlist/prd_wishlist_test")
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"productId": "prd_wishlist_test", "removed": True}
    assert client.get("/v1/public/wishlist").json()["items"] == []


def test_adding_the_same_product_twice_is_idempotent(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)

    first = client.post("/v1/public/wishlist", json={"productId": "prd_wishlist_test"})
    second = client.post("/v1/public/wishlist", json={"productId": "prd_wishlist_test"})
    assert first.status_code == 200
    assert second.status_code == 200

    items = client.get("/v1/public/wishlist").json()["items"]
    assert len(items) == 1


def test_removing_a_product_never_added_is_a_no_op(client: TestClient, db: SQLiteDatabase):
    # No wishlist row exists yet for this customer at all -- must not error.
    as_customer(client, db)
    response = client.delete("/v1/public/wishlist/prd_wishlist_test")
    assert response.status_code == 200
    assert response.json() == {"productId": "prd_wishlist_test", "removed": True}


def test_saving_an_unknown_product_is_rejected(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    response = client.post("/v1/public/wishlist", json={"productId": "prd_does_not_exist"})
    assert response.status_code == 422


def test_a_customer_cannot_see_or_remove_another_customers_wishlist_item(
    client: TestClient, db: SQLiteDatabase
):
    as_customer(client, db, "usr_cust_riya")
    client.post("/v1/public/wishlist", json={"productId": "prd_wishlist_test"})

    as_customer(client, db, "usr_cust_arjun")
    assert client.get("/v1/public/wishlist").json()["items"] == []
    assert client.get("/v1/public/wishlist/product-ids").json()["productIds"] == []

    # Arjun "removing" Riya's saved product only ever deletes from his own
    # (nonexistent) wishlist -- scoped by `wishlists.user_id`, so this can't
    # touch Riya's row regardless of him knowing the product id.
    removed = client.delete("/v1/public/wishlist/prd_wishlist_test")
    assert removed.status_code == 200

    as_customer(client, db, "usr_cust_riya")
    riya_items = client.get("/v1/public/wishlist").json()["items"]
    assert {item["productId"] for item in riya_items} == {"prd_wishlist_test"}


def test_wishlist_requires_a_signed_in_customer(client: TestClient, db: SQLiteDatabase):
    assert client.get("/v1/public/wishlist").status_code == 401
    response = client.post("/v1/public/wishlist", json={"productId": "prd_wishlist_test"})
    assert response.status_code == 401

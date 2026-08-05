"""Wishlist (activates the dormant `wishlists`/`wishlist_items` schema from
migration 0005, in migration 0079): add/remove/list, idempotency, and
per-customer scoping.

Uses the seeded catalogue (`prd_alphonso`) the same way test_subscriptions.py
uses `var_alphonso_1kg`.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_cust_riya") -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def test_customer_can_add_list_and_remove_a_wishlist_item(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)

    added = client.post("/v1/public/wishlist", json={"productId": "prd_alphonso"})
    assert added.status_code == 200, added.text
    body = added.json()
    assert body["productId"] == "prd_alphonso"
    assert body["productName"] == "Organic Alphonso Mangoes"
    assert body["unitPriceMinor"] is not None

    listed = client.get("/v1/public/wishlist").json()["items"]
    assert {item["productId"] for item in listed} == {"prd_alphonso"}

    ids = client.get("/v1/public/wishlist/product-ids").json()["productIds"]
    assert ids == ["prd_alphonso"]

    removed = client.delete("/v1/public/wishlist/prd_alphonso")
    assert removed.status_code == 200, removed.text
    assert removed.json() == {"productId": "prd_alphonso", "removed": True}
    assert client.get("/v1/public/wishlist").json()["items"] == []


def test_adding_the_same_product_twice_is_idempotent(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)

    first = client.post("/v1/public/wishlist", json={"productId": "prd_alphonso"})
    second = client.post("/v1/public/wishlist", json={"productId": "prd_alphonso"})
    assert first.status_code == 200
    assert second.status_code == 200

    items = client.get("/v1/public/wishlist").json()["items"]
    assert len(items) == 1


def test_removing_a_product_never_added_is_a_no_op(client: TestClient, db: SQLiteDatabase):
    # No wishlist row exists yet for this customer at all -- must not error.
    as_customer(client, db)
    response = client.delete("/v1/public/wishlist/prd_alphonso")
    assert response.status_code == 200
    assert response.json() == {"productId": "prd_alphonso", "removed": True}


def test_saving_an_unknown_product_is_rejected(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    response = client.post("/v1/public/wishlist", json={"productId": "prd_does_not_exist"})
    assert response.status_code == 422


def test_a_customer_cannot_see_or_remove_another_customers_wishlist_item(
    client: TestClient, db: SQLiteDatabase
):
    as_customer(client, db, "usr_cust_riya")
    client.post("/v1/public/wishlist", json={"productId": "prd_alphonso"})

    as_customer(client, db, "usr_cust_arjun")
    assert client.get("/v1/public/wishlist").json()["items"] == []
    assert client.get("/v1/public/wishlist/product-ids").json()["productIds"] == []

    # Arjun "removing" Riya's saved product only ever deletes from his own
    # (nonexistent) wishlist -- scoped by `wishlists.user_id`, so this can't
    # touch Riya's row regardless of him knowing the product id.
    removed = client.delete("/v1/public/wishlist/prd_alphonso")
    assert removed.status_code == 200

    as_customer(client, db, "usr_cust_riya")
    riya_items = client.get("/v1/public/wishlist").json()["items"]
    assert {item["productId"] for item in riya_items} == {"prd_alphonso"}


def test_wishlist_requires_a_signed_in_customer(client: TestClient, db: SQLiteDatabase):
    assert client.get("/v1/public/wishlist").status_code == 401
    assert client.post("/v1/public/wishlist", json={"productId": "prd_alphonso"}).status_code == 401

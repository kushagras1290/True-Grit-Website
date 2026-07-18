"""Integration tests for customer checkout and order history."""

from __future__ import annotations

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
    client.cookies.set(SESSION_COOKIE, create_session(db, client, "usr_cust_riya"))


def test_checkout_requires_a_verified_mobile(client: TestClient, db: SQLiteDatabase):
    """Accounts predating phone verification are prompted (and may skip) in the
    storefront, so checkout is the backstop — a courier needs a live number, and
    cash on delivery has nothing else to fall back on."""
    db._conn.execute(
        "UPDATE users SET phone_e164 = NULL, phone_verified_at = NULL WHERE id = 'usr_cust_riya'"
    )
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "phone_verification_required"


def test_checkout_records_the_customers_verified_mobile(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200
    stored = db._conn.execute(
        "SELECT customer_phone_e164 FROM orders WHERE public_reference = ?",
        (response.json()["reference"],),
    ).fetchone()[0]
    # Fulfilment needs a number it can actually ring.
    assert stored == "+919999900010"


def test_checkout_creates_order_and_reserves_stock(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    before = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 2}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["reference"].startswith("TG-")
    assert body["totalMinor"] == 179800  # 2 x 89900, free delivery over the threshold
    assert body["orderStatus"] == "confirmed"

    after = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]
    assert after == before + 2

    listing = client.get("/v1/public/orders").json()["items"]
    assert body["reference"] in [order["reference"] for order in listing]

    detail = client.get(f"/v1/public/orders/{body['reference']}")
    assert detail.status_code == 200
    assert detail.json()["items"][0]["sku"] == "TRG-MNG-1KG"


def test_checkout_requires_authentication(client: TestClient):
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 401


def test_checkout_rejects_insufficient_stock(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    # var_rajma_500g has only 8 on hand; 10 (<= per-line max) exceeds free stock.
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_rajma_500g", "quantity": 10}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 409


def test_checkout_requires_address_fields(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": {
                "recipientName": "Riya",
                "line1": "12 Palm Grove",
                "city": "Mumbai",
            },
        },
    )
    assert response.status_code == 422


def test_order_detail_is_scoped_to_customer(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    # Seeded order TG-1001 belongs to riya, so she can see it; a made-up ref 404s.
    assert client.get("/v1/public/orders/TG-1001").status_code == 200
    assert client.get("/v1/public/orders/TG-DOESNOTEXIST").status_code == 404

"""End-to-end coverage for roadmap features 5-9 and their kill switches."""

from __future__ import annotations

import datetime
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


def sign_in(client: TestClient, db: SQLiteDatabase, user_id: str) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    sign_in(client, db, "usr_admin")


def as_customer(client: TestClient, db: SQLiteDatabase) -> None:
    sign_in(client, db, "usr_cust_riya")


def enable(client: TestClient, db: SQLiteDatabase, **switches: bool) -> None:
    as_admin(client, db)
    response = client.patch("/v1/admin/storefront-settings", json=switches)
    assert response.status_code == 200, response.text


def checkout(client: TestClient, **overrides: Any):
    body: dict[str, Any] = {
        "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
        "deliveryAddress": ADDRESS,
        "paymentMethod": "razorpay",
    }
    body.update(overrides)
    return client.post("/v1/public/checkout", json=body)


def test_all_expanded_features_are_independently_disabled_by_default(client, db):
    as_admin(client, db)
    settings = client.get("/v1/admin/storefront-settings").json()["settings"]
    assert {
        key: settings[key] for key in ("loyalty", "pickup", "preorders", "deliveryZones", "b2b")
    } == {
        "loyalty": False,
        "pickup": False,
        "preorders": False,
        "deliveryZones": False,
        "b2b": False,
    }

    as_customer(client, db)
    assert client.get("/v1/public/loyalty").status_code == 422
    assert client.get("/v1/public/pickup-points").status_code == 422
    assert client.get("/v1/public/seasonal-calendar").status_code == 422
    assert client.get("/v1/public/delivery/check?postalCode=400001").status_code == 422
    assert client.get("/v1/public/b2b/account").status_code == 422


def test_pickup_checkout_waives_delivery_and_snapshots_the_point(client, db):
    as_admin(client, db)
    point = client.post(
        "/v1/admin/pickup-points",
        json={
            "name": "Bandra Saturday Hub",
            "address": {"line1": "Market Road", "city": "Mumbai"},
            "hours": "Saturday 09:00-13:00",
        },
    ).json()
    enable(client, db, pickup=True)

    as_customer(client, db)
    response = checkout(
        client,
        deliveryMethod="pickup",
        pickupPointId=point["id"],
    )
    assert response.status_code == 200, response.text
    assert response.json()["deliveryMinor"] == 0
    assert response.json()["deliveryMethod"] == "pickup"
    row = db._conn.execute(
        "SELECT pickup_point_id, delivery_method FROM orders WHERE id = ?",
        (response.json()["id"],),
    ).fetchone()
    assert tuple(row) == (point["id"], "pickup")


def test_delivery_zone_and_slot_are_enforced_and_booked(client, db):
    selected_date = datetime.date.today() + datetime.timedelta(days=14)
    day_of_week = (selected_date.weekday() + 1) % 7
    as_admin(client, db)
    zone = client.post(
        "/v1/admin/delivery-zones",
        json={
            "name": "Mumbai core",
            "postalCodes": ["400*"],
            "feeOverrideMinor": 2_500,
            "leadTimeHours": 0,
        },
    ).json()
    slot = client.post(
        f"/v1/admin/delivery-zones/{zone['id']}/slots",
        json={
            "dayOfWeek": day_of_week,
            "startTime": "09:00",
            "endTime": "12:00",
            "maxOrders": 1,
        },
    ).json()
    enable(client, db, deliveryZones=True)

    as_customer(client, db)
    response = checkout(
        client,
        deliverySlotId=slot["id"],
        deliveryDate=selected_date.isoformat(),
    )
    assert response.status_code == 200, response.text
    assert response.json()["deliveryMinor"] == 2_500
    assert response.json()["deliveryZoneId"] == zone["id"]
    assert response.json()["deliverySlotId"] == slot["id"]
    booking = db._conn.execute(
        "SELECT order_id FROM delivery_slot_bookings WHERE slot_id = ?",
        (slot["id"],),
    ).fetchone()
    assert booking["order_id"] == response.json()["id"]


def test_preorder_reserves_harvest_capacity_without_inventory(client, db):
    as_admin(client, db)
    window = client.post(
        "/v1/admin/harvest-windows",
        json={
            "productId": "prd_alphonso",
            "title": "Monsoon mango harvest",
            "expectedStart": "2026-09-01",
            "expectedEnd": "2026-09-15",
            "maxPreorders": 20,
        },
    ).json()
    enable(client, db, preorders=True)
    before = db._conn.execute(
        "SELECT reserved FROM inventory_levels"
        " WHERE variant_id = 'var_alphonso_1kg' AND location_id = 'loc_mumbai'"
    ).fetchone()["reserved"]

    as_customer(client, db)
    response = checkout(
        client,
        items=[{"variantId": "var_alphonso_1kg", "quantity": 2, "preorder": True}],
    )
    assert response.status_code == 200, response.text
    assert response.json()["orderType"] == "preorder"
    preorder = db._conn.execute(
        "SELECT harvest_window_id, quantity FROM preorders WHERE order_id = ?",
        (response.json()["id"],),
    ).fetchone()
    assert tuple(preorder) == (window["id"], 2)
    as_admin(client, db)
    too_small = client.patch(
        f"/v1/admin/harvest-windows/{window['id']}",
        json={"maxPreorders": 1},
    )
    assert too_small.status_code == 409, too_small.text
    after = db._conn.execute(
        "SELECT reserved FROM inventory_levels"
        " WHERE variant_id = 'var_alphonso_1kg' AND location_id = 'loc_mumbai'"
    ).fetchone()["reserved"]
    assert after == before


def test_b2b_checkout_applies_bulk_price_and_creates_invoice(client, db):
    as_admin(client, db)
    account = client.post(
        "/v1/admin/b2b/accounts",
        json={
            "companyName": "Konkan Kitchens",
            "contactEmail": "accounts@konkan.example",
            "creditLimitMinor": 1_000_000,
            "paymentTermsDays": 30,
        },
    ).json()
    linked = client.post(
        f"/v1/admin/b2b/accounts/{account['id']}/users",
        json={"userId": "usr_cust_riya"},
    )
    assert linked.status_code == 200, linked.text
    price = client.post(
        "/v1/admin/b2b/price-breaks",
        json={"variantId": "var_alphonso_1kg", "minQuantity": 2, "priceMinor": 70_000},
    )
    assert price.status_code == 200, price.text
    enable(client, db, b2b=True)

    as_customer(client, db)
    response = checkout(
        client,
        items=[{"variantId": "var_alphonso_1kg", "quantity": 2}],
        paymentMethod="invoice",
    )
    assert response.status_code == 200, response.text
    assert response.json()["subtotalMinor"] == 140_000
    assert response.json()["payment"]["method"] == "invoice"
    invoice = db._conn.execute(
        "SELECT b2b_account_id, amount_minor, status FROM b2b_invoices WHERE order_id = ?",
        (response.json()["id"],),
    ).fetchone()
    assert tuple(invoice) == (account["id"], response.json()["totalMinor"], "issued")


def test_loyalty_points_redeem_and_earn_on_completion(client, db):
    enable(client, db, loyalty=True)
    as_admin(client, db)
    adjusted = client.post(
        "/v1/admin/loyalty/adjustments",
        json={
            "customerUserId": "usr_cust_riya",
            "points": 500,
            "reason": "Launch reward",
        },
    )
    assert adjusted.status_code == 200, adjusted.text

    as_customer(client, db)
    response = checkout(client, loyaltyPoints=100)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["loyaltyPointsRedeemed"] == 100
    assert body["loyaltyAppliedMinor"] == 10_000

    as_admin(client, db)
    assert (
        client.patch(
            f"/v1/admin/orders/{body['id']}/status", json={"status": "processing"}
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/v1/admin/orders/{body['id']}/status", json={"status": "completed"}
        ).status_code
        == 200
    )

    as_customer(client, db)
    account = client.get("/v1/public/loyalty").json()
    expected_earned = (body["totalMinor"] // 10_000) * 10
    assert account["balance"] == 500 - 100 + expected_earned

    as_admin(client, db)
    overdraw = client.post(
        "/v1/admin/loyalty/adjustments",
        json={
            "customerUserId": "usr_cust_riya",
            "points": -(account["balance"] + 1),
            "reason": "Invalid overdraw attempt",
        },
    )
    assert overdraw.status_code == 409, overdraw.text

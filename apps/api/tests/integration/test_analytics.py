"""Owner analytics dashboard (migration 0065): permission gating and revenue
correctness against a real checkout, isolated to today's date so it is never
tangled up with the seeded historical order data (see
`database/seeds/development.sql`, backdated well before "today").

Seeds its own purchasable product (`var_analytics_test_1kg`) rather than
depending on the demo catalogue: migration 0095 retires that catalogue from
every database it touches (the live site must not keep any trace of it), so
tests cannot rely on it surviving either.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}

CHECKOUT_VARIANT_ID = "var_analytics_test_1kg"


@pytest.fixture(autouse=True)
def _purchasable_product(db: SQLiteDatabase) -> None:
    db._conn.executescript(
        """
        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_analytics_test', 'Analytics Test Product', 'Analytics Test Product',
          'analytics-test-product', 'simple', 'published', 1,
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('var_analytics_test_1kg', 'prd_analytics_test', 'ANL-TEST-1KG', '1 kg',
          'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_analytics_test_1kg', 'var_analytics_test_1kg', 'IN', 'INR', 89900,
          'active', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('var_analytics_test_1kg', 'loc_mumbai', 500, 0, 20, 1, '2026-07-01T00:00:00Z');
        """
    )
    db._conn.commit()


def as_admin(client, db) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_customer(client, db) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


def today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def test_analytics_overview_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.get("/v1/admin/analytics/overview")
    assert response.status_code == 403


def test_analytics_overview_defaults_to_the_last_30_days(client, db):
    as_admin(client, db)
    response = client.get("/v1/admin/analytics/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["toDate"] == today_iso()
    for key in (
        "revenueMinor",
        "orderCount",
        "averageOrderValueMinor",
        "newCustomers",
        "revenueByDay",
        "topProducts",
        "statusBreakdown",
    ):
        assert key in body


def test_analytics_rejects_an_end_date_before_the_start_date(client, db):
    as_admin(client, db)
    response = client.get(
        "/v1/admin/analytics/overview", params={"from": "2026-08-10", "to": "2026-08-01"}
    )
    assert response.status_code == 422


def test_a_fresh_order_counts_toward_todays_revenue(client, db):
    as_customer(client, db)
    checkout = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": CHECKOUT_VARIANT_ID, "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert checkout.status_code == 200, checkout.text
    total_minor = checkout.json()["totalMinor"]

    as_admin(client, db)
    today = today_iso()
    response = client.get("/v1/admin/analytics/overview", params={"from": today, "to": today})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["orderCount"] == 1
    assert body["revenueMinor"] == total_minor
    assert body["averageOrderValueMinor"] == total_minor
    assert len(body["revenueByDay"]) == 1
    assert body["revenueByDay"][0]["date"] == today
    assert body["topProducts"][0]["productId"] is not None
    assert body["topProducts"][0]["unitsSold"] == 1


def test_a_cancelled_order_does_not_count_as_revenue(client, db):
    as_customer(client, db)
    checkout = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": CHECKOUT_VARIANT_ID, "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    reference = checkout.json()["reference"]
    order_id = db._conn.execute(
        "SELECT id FROM orders WHERE public_reference = ?", (reference,)
    ).fetchone()[0]
    db._conn.execute("UPDATE orders SET order_status = 'cancelled' WHERE id = ?", (order_id,))
    db._conn.commit()

    as_admin(client, db)
    today = today_iso()
    response = client.get("/v1/admin/analytics/overview", params={"from": today, "to": today})
    body = response.json()
    assert body["orderCount"] == 0
    assert body["revenueMinor"] == 0
    # Cancelled orders still show up in the status mix -- that is what it is for.
    cancelled = next(row for row in body["statusBreakdown"] if row["status"] == "cancelled")
    assert cancelled["orderCount"] == 1

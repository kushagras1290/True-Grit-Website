"""Owner analytics dashboard (migration 0065): permission gating and revenue
correctness against a real checkout, isolated to today's date so it is never
tangled up with the seeded historical order data (see
`database/seeds/development.sql`, backdated well before "today").
"""

from __future__ import annotations

from datetime import UTC, datetime

from tests.integration.conftest import SESSION_COOKIE, create_session

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}


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
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
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
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
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

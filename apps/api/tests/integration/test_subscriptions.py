"""Subscribe & Save (migration 0064), end to end: creation, ownership, admin
support actions, and the renewal engine against real checkout.

Uses the seeded catalogue (`var_alphonso_1kg` at 89900) the same way
test_bundles.py does.
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


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_cust_riya") -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def enable_subscriptions(client: TestClient, db: SQLiteDatabase) -> None:
    as_admin(client, db)
    response = client.patch("/v1/admin/storefront-settings", json={"subscriptions": True})
    assert response.status_code == 200, response.text


def create_my_address(client: TestClient) -> str:
    response = client.post("/v1/public/addresses", json=ADDRESS)
    assert response.status_code == 200, response.text
    return response.json()["id"]


def create_my_subscription(
    client: TestClient,
    db: SQLiteDatabase,
    *,
    variant_id: str = "var_alphonso_1kg",
    quantity: int = 1,
    frequency: str = "weekly",
    user_id: str = "usr_cust_riya",
) -> dict[str, Any]:
    enable_subscriptions(client, db)
    as_customer(client, db, user_id)
    address_id = create_my_address(client)
    response = client.post(
        "/v1/public/subscriptions",
        json={
            "variantId": variant_id,
            "quantity": quantity,
            "frequency": frequency,
            "addressId": address_id,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_creating_a_subscription_is_refused_while_the_feature_is_off(client, db):
    as_customer(client, db)
    address_id = create_my_address(client)
    response = client.post(
        "/v1/public/subscriptions",
        json={
            "variantId": "var_alphonso_1kg",
            "quantity": 1,
            "frequency": "weekly",
            "addressId": address_id,
        },
    )
    assert response.status_code == 422


def test_customer_can_create_and_list_their_own_subscription(client, db):
    subscription = create_my_subscription(client, db)
    assert subscription["status"] == "active"
    assert subscription["frequency"] == "weekly"
    assert subscription["quantity"] == 1

    listed = client.get("/v1/public/subscriptions")
    assert listed.status_code == 200
    ids = [entry["id"] for entry in listed.json()["items"]]
    assert subscription["id"] in ids


def test_a_customer_cannot_see_or_act_on_another_customers_subscription(client, db):
    subscription = create_my_subscription(client, db, user_id="usr_cust_riya")

    as_customer(client, db, "usr_cust_arjun")
    listed = client.get("/v1/public/subscriptions")
    assert subscription["id"] not in [entry["id"] for entry in listed.json()["items"]]

    pause = client.post(f"/v1/public/subscriptions/{subscription['id']}/pause")
    assert pause.status_code == 404


def test_customer_can_pause_resume_and_cancel_their_subscription(client, db):
    subscription = create_my_subscription(client, db)
    sub_id = subscription["id"]

    paused = client.post(f"/v1/public/subscriptions/{sub_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"

    resumed = client.post(f"/v1/public/subscriptions/{sub_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"

    cancelled = client.post(f"/v1/public/subscriptions/{sub_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # A cancelled subscription cannot be paused, resumed, or edited again.
    assert client.post(f"/v1/public/subscriptions/{sub_id}/pause").status_code == 409
    assert (
        client.patch(f"/v1/public/subscriptions/{sub_id}", json={"quantity": 2}).status_code == 422
    )


def test_admin_without_manage_permission_cannot_pause_a_subscription(client, db):
    subscription = create_my_subscription(client, db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.post(f"/v1/admin/subscriptions/{subscription['id']}/pause")
    assert response.status_code == 403


def test_admin_with_manage_permission_can_pause_on_a_customers_behalf(client, db):
    subscription = create_my_subscription(client, db)
    as_admin(client, db)
    response = client.post(f"/v1/admin/subscriptions/{subscription['id']}/pause")
    assert response.status_code == 200
    assert response.json()["status"] == "paused"


def test_admin_subscriptions_listing_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.get("/v1/admin/subscriptions").status_code == 403


def test_running_due_renewals_places_a_real_order_with_the_discount(client, db):
    subscription = create_my_subscription(client, db, quantity=1)
    original_next_date = subscription["nextOrderDate"]

    as_admin(client, db)
    settings = client.patch("/v1/admin/subscription-settings", json={"percent": 10})
    assert settings.status_code == 200
    assert settings.json()["discountPercent"] == 10

    run = client.post("/v1/admin/subscriptions/run-renewals")
    assert run.status_code == 200, run.text
    body = run.json()
    assert body["processed"] == 1
    assert body["succeeded"] == 1
    order_id = body["outcomes"][0]["orderId"]
    assert order_id is not None

    order = db._conn.execute(
        "SELECT payment_status, order_status, subscription_id, discount_minor, subtotal_minor"
        " FROM orders WHERE id = ?",
        (order_id,),
    ).fetchone()
    assert order["subscription_id"] == subscription["id"]
    assert order["order_status"] == "confirmed"  # cash-on-delivery, confirmed immediately
    # 89900 subtotal at 10% off -> 8990 discount.
    assert order["discount_minor"] == 8_990

    adjustment = db._conn.execute(
        "SELECT adjustment_type, label, amount_minor FROM order_adjustments WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    assert adjustment["adjustment_type"] == "promotion"
    assert "Subscribe & Save" in adjustment["label"]
    assert adjustment["amount_minor"] == -8_990

    updated = client.get(f"/v1/admin/subscriptions/{subscription['id']}")
    assert updated.status_code == 200
    assert updated.json()["lastOrderId"] == order_id
    assert updated.json()["nextOrderDate"] > original_next_date


def test_running_due_renewals_twice_in_one_day_does_not_double_order(client, db):
    create_my_subscription(client, db)
    as_admin(client, db)

    first = client.post("/v1/admin/subscriptions/run-renewals")
    assert first.status_code == 200
    assert first.json()["processed"] == 1

    second = client.post("/v1/admin/subscriptions/run-renewals")
    assert second.status_code == 200
    # Already advanced past today by the first run -- nothing left due.
    assert second.json()["processed"] == 0


def test_running_due_renewals_is_a_no_op_while_the_feature_is_off(client, db):
    subscription = create_my_subscription(client, db)

    as_admin(client, db)
    off = client.patch("/v1/admin/storefront-settings", json={"subscriptions": False})
    assert off.status_code == 200

    run = client.post("/v1/admin/subscriptions/run-renewals")
    assert run.status_code == 200
    assert run.json() == {"processed": 0, "succeeded": 0, "outcomes": []}

    unchanged = client.get(f"/v1/admin/subscriptions/{subscription['id']}")
    assert unchanged.json()["lastOrderId"] is None


def test_a_cancelled_subscription_is_never_renewed(client, db):
    subscription = create_my_subscription(client, db)
    client.post(f"/v1/public/subscriptions/{subscription['id']}/cancel")

    as_admin(client, db)
    run = client.post("/v1/admin/subscriptions/run-renewals")
    assert run.status_code == 200
    assert run.json()["processed"] == 0

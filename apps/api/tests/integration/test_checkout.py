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
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


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
    # The e-receipt needs the delivery address -- stored as the snake_case
    # keys CheckoutAddress posts, translated to camelCase on the way out like
    # every other response shape.
    assert detail.json()["deliveryAddress"]["recipientName"] == ADDRESS["recipientName"]
    assert detail.json()["deliveryAddress"]["postalCode"] == ADDRESS["postalCode"]


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
    # Pinned rather than trusting the seed's current quantity, which is free
    # to change independently of what this test needs: fewer than 10 on hand.
    db._conn.execute(
        "UPDATE inventory_levels SET on_hand = 5, reserved = 0 WHERE variant_id = 'var_rajma_500g'"
    )
    db._conn.commit()

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_rajma_500g", "quantity": 10}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 409


def test_checkout_rejects_insufficient_stock_and_releases_earlier_lines(
    client: TestClient, db: SQLiteDatabase
):
    """A multi-line order where a later line fails must not leave the earlier,
    already-reserved lines holding stock for an order that never exists."""
    as_customer(client, db)
    db._conn.execute(
        "UPDATE inventory_levels SET on_hand = 5, reserved = 0 WHERE variant_id = 'var_rajma_500g'"
    )
    db._conn.commit()
    before = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {"variantId": "var_alphonso_1kg", "quantity": 1},
                # Pinned above to 5 on hand; 10 exceeds free stock.
                {"variantId": "var_rajma_500g", "quantity": 10},
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 409

    after = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]
    assert after == before, "the mango reservation must be released when rajma's line fails"


def test_checkout_second_line_cannot_oversell_the_last_unit(client: TestClient, db: SQLiteDatabase):
    """The reservation write is conditional on the row it changes, not a
    separate read-then-write — two requests racing for the same last unit
    cannot both succeed."""
    as_customer(client, db)
    db._conn.execute(
        "UPDATE inventory_levels SET on_hand = 5, reserved = 4 WHERE variant_id = 'var_rajma_500g'"
    )
    db._conn.commit()

    first = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_rajma_500g", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_rajma_500g", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert second.status_code == 409

    reserved = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_rajma_500g'"
    ).fetchone()[0]
    assert reserved == 5  # the last unit is held by exactly one order, not oversold


def test_checkout_idempotency_key_returns_the_original_order_on_retry(
    client: TestClient, db: SQLiteDatabase
):
    as_customer(client, db)
    before = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]

    payload = {
        "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
        "deliveryAddress": ADDRESS,
        "idempotencyKey": "retry-key-riya-1",
    }
    first = client.post("/v1/public/checkout", json=payload)
    assert first.status_code == 200

    retried = client.post("/v1/public/checkout", json=payload)
    assert retried.status_code == 200
    assert retried.json()["reference"] == first.json()["reference"]
    assert retried.json()["id"] == first.json()["id"]

    after = db._conn.execute(
        "SELECT reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()[0]
    assert after == before + 1, "a retried request must not reserve stock a second time"

    orders = db._conn.execute(
        "SELECT COUNT(*) FROM orders WHERE idempotency_key = 'retry-key-riya-1'"
    ).fetchone()[0]
    assert orders == 1


def test_checkout_idempotency_key_is_scoped_per_customer(client: TestClient, db: SQLiteDatabase):
    """The same key from two different customers must never collide."""
    db._conn.execute(
        "INSERT INTO users"
        " (id, email, display_name, user_type, status, email_verified_at,"
        "  phone_e164, phone_verified_at, created_at, updated_at)"
        " VALUES ('usr_cust_kavya', 'kavya@example.test', 'Kavya Rao', 'customer', 'active',"
        "  '2026-07-05T00:00:00Z', '+919999900099', '2026-07-05T00:00:00Z',"
        "  '2026-07-05T00:00:00Z', '2026-07-05T00:00:00Z')"
    )
    db._conn.commit()

    payload = {
        "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
        "deliveryAddress": ADDRESS,
        "idempotencyKey": "shared-key",
    }
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    riya_order = client.post("/v1/public/checkout", json=payload)
    assert riya_order.status_code == 200

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_kavya"))
    kavya_order = client.post("/v1/public/checkout", json=payload)
    assert kavya_order.status_code == 200
    assert kavya_order.json()["reference"] != riya_order.json()["reference"]


def _insert_pending_razorpay_order(
    db: SQLiteDatabase, *, order_id: str, reference: str, razorpay_order_id: str, total_minor: int
) -> None:
    """A minimal pending_payment order with its own Razorpay payment row,
    bypassing checkout (which would call the real gateway) since these tests
    only need the order/payment shape `/payments/razorpay/verify` reads."""
    db._conn.execute(
        """
        INSERT INTO orders (
          id, public_reference, customer_user_id, customer_email, customer_phone_e164,
          currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,
          order_status, payment_status, fulfilment_status, delivery_status,
          delivery_address_json, placed_at, created_at, updated_at
        ) VALUES (?, ?, 'usr_cust_riya', 'riya@example.test', '+919999900010', 'INR',
                  ?, 0, 0, 0, ?, 'pending_payment', 'pending', 'unfulfilled', 'not_ready',
                  '{}', '2026-08-02T00:00:00Z', '2026-08-02T00:00:00Z', '2026-08-02T00:00:00Z')
        """,
        (order_id, reference, total_minor, total_minor),
    )
    db._conn.execute(
        """
        INSERT INTO payments
          (id, order_id, provider, provider_intent_id, amount_minor, currency_code,
           status, created_at, updated_at)
        VALUES (?, ?, 'razorpay', ?, ?, 'INR', 'created',
                '2026-08-02T00:00:00Z', '2026-08-02T00:00:00Z')
        """,
        (f"pay_{order_id}", order_id, razorpay_order_id, total_minor),
    )
    db._conn.commit()


def test_razorpay_verify_rejects_a_payment_for_a_different_order(
    client: TestClient, db: SQLiteDatabase
):
    """A signature is only proof that (razorpay_order_id, payment_id,
    signature) are internally consistent -- it says nothing about which order
    that Razorpay order was created for. Submitting a real payment's
    razorpay_order_id against a *different*, more expensive pending order
    must be rejected before signature verification is even attempted --
    otherwise a customer could pay for a cheap order and replay that valid
    signature to mark any number of their other pending orders as paid."""
    as_customer(client, db)
    _insert_pending_razorpay_order(
        db,
        order_id="ord_cheap",
        reference="TG-CHEAP01",
        razorpay_order_id="rzp_cheap",
        total_minor=100,
    )
    _insert_pending_razorpay_order(
        db,
        order_id="ord_expensive",
        reference="TG-EXPENSIVE01",
        razorpay_order_id="rzp_expensive",
        total_minor=999_900,
    )

    # A signature that is genuinely valid for the cheap order's Razorpay
    # order id, replayed against the expensive order.
    response = client.post(
        "/v1/public/payments/razorpay/verify",
        json={
            "orderId": "ord_expensive",
            "razorpayOrderId": "rzp_cheap",
            "razorpayPaymentId": "pay_real",
            "razorpaySignature": "sig_real",
        },
    )
    assert response.status_code == 422
    assert "does not belong" in response.json()["error"]["message"].lower()

    expensive_status = db._conn.execute(
        "SELECT payment_status, order_status FROM orders WHERE id = 'ord_expensive'"
    ).fetchone()
    assert expensive_status["payment_status"] != "paid"
    assert expensive_status["order_status"] != "confirmed"


def test_razorpay_verify_rejects_an_already_paid_order(client: TestClient, db: SQLiteDatabase):
    """The order/payment status transition is a single atomic batch in normal
    operation, so this state (payment already paid, order still showing
    pending_payment) should not arise from ordinary use -- this is the
    defensive belt-and-braces check for it anyway, exercised directly."""
    as_customer(client, db)
    _insert_pending_razorpay_order(
        db,
        order_id="ord_once",
        reference="TG-ONCE01",
        razorpay_order_id="rzp_once",
        total_minor=5000,
    )
    db._conn.execute("UPDATE payments SET status = 'paid' WHERE order_id = 'ord_once'")
    db._conn.commit()

    response = client.post(
        "/v1/public/payments/razorpay/verify",
        json={
            "orderId": "ord_once",
            "razorpayOrderId": "rzp_once",
            "razorpayPaymentId": "pay_x",
            "razorpaySignature": "sig_x",
        },
    )
    assert response.status_code == 409


def test_razorpay_verify_with_matching_order_reaches_signature_check(
    client: TestClient, db: SQLiteDatabase
):
    """A correctly-matched razorpay_order_id must clear the ownership check
    and proceed to signature verification, not be rejected by the ownership
    check itself -- proves the fix does not also reject legitimate payments."""
    as_customer(client, db)
    _insert_pending_razorpay_order(
        db,
        order_id="ord_legit",
        reference="TG-LEGIT01",
        razorpay_order_id="rzp_legit",
        total_minor=5000,
    )

    response = client.post(
        "/v1/public/payments/razorpay/verify",
        json={
            "orderId": "ord_legit",
            "razorpayOrderId": "rzp_legit",
            "razorpayPaymentId": "pay_x",
            "razorpaySignature": "not-a-real-signature",
        },
    )
    # No real Razorpay secret is configured in tests, so a made-up signature
    # cannot verify -- but the failure must be "could not verify", not "does
    # not belong to that order".
    assert response.status_code == 422
    assert "does not belong" not in response.json()["error"]["message"].lower()


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

"""Integration tests for payment gateway webhooks.

Unlike `test_checkout.py` (which drives the browser-facing confirm endpoints
through a signed-in customer session), these tests exercise the
server-to-server confirmation path: the gateway calling `/webhooks/...`
directly, with no cookie and no CSRF token, authenticated only by its
signature. Fixture orders are inserted straight into the database — mirroring
exactly what `services.checkout.place_order` + the "razorpay"/"paypal"
branches of `api.storefront.checkout` leave behind — rather than driven
through the authenticated checkout endpoint, so these tests depend only on
the webhook routes under test, not on unrelated authentication machinery.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any

import pytest
from fastapi.testclient import TestClient

from truegrit_api.config import Settings, get_settings
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.payments import verify_paypal_webhook_signature

RAZORPAY_WEBHOOK_SECRET = "whsec_test_razorpay_secret"
PAYPAL_WEBHOOK_ID = "WH-TEST-PAYPAL-1"

_PAYPAL_HEADERS = {
    "Content-Type": "application/json",
    "PAYPAL-AUTH-ALGO": "SHA256withRSA",
    "PAYPAL-CERT-URL": "https://api.sandbox.paypal.com/cert",
    "PAYPAL-TRANSMISSION-ID": "txn-1",
    "PAYPAL-TRANSMISSION-SIG": "sig-1",
    "PAYPAL-TRANSMISSION-TIME": "2026-07-19T00:00:00Z",
}


@pytest.fixture()
def razorpay_webhook_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", RAZORPAY_WEBHOOK_SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def paypal_webhook_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PAYPAL_WEBHOOK_ID", PAYPAL_WEBHOOK_ID)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _insert_pending_order(
    db: SQLiteDatabase,
    *,
    provider: str,
    provider_intent_id: str,
    order_id: str,
    reference: str,
    payment_id: str,
    amount_minor: int = 89900,
    currency: str = "INR",
) -> None:
    """Seed exactly what checkout leaves behind for an online payment: an
    order in `pending_payment`/`pending` and its `payments` row holding the
    gateway's own order/intent id — the state a webhook is meant to resolve."""
    now = "2026-07-19T00:00:00Z"
    db._conn.execute(
        """
        INSERT INTO orders (
          id, public_reference, customer_user_id, customer_email, customer_phone_e164,
          currency_code, subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,
          order_status, payment_status, fulfilment_status, delivery_status,
          delivery_address_json, placed_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, 0, ?, 'pending_payment', 'pending',
                  'unfulfilled', 'not_ready', '{}', ?, ?, ?)
        """,
        (
            order_id,
            reference,
            "usr_cust_riya",
            "riya@example.test",
            "+919999900010",
            currency,
            amount_minor,
            amount_minor,
            now,
            now,
            now,
        ),
    )
    db._conn.execute(
        """
        INSERT INTO payments (
          id, order_id, provider, provider_intent_id, amount_minor, currency_code,
          status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, 'created', ?, ?)
        """,
        (payment_id, order_id, provider, provider_intent_id, amount_minor, currency, now, now),
    )
    db._conn.commit()


def _order_state(db: SQLiteDatabase, order_id: str) -> tuple[str, str]:
    row = db._conn.execute(
        "SELECT payment_status, order_status FROM orders WHERE id = ?", (order_id,)
    ).fetchone()
    return row[0], row[1]


def _payment_state(db: SQLiteDatabase, payment_id: str) -> tuple[str, str]:
    row = db._conn.execute(
        "SELECT status, provider_intent_id FROM payments WHERE id = ?", (payment_id,)
    ).fetchone()
    return row[0], row[1]


def _webhook_event_row(
    db: SQLiteDatabase, provider: str, provider_event_id: str
) -> tuple[int, str]:
    row = db._conn.execute(
        "SELECT attempt_count, processing_status FROM webhook_events"
        " WHERE provider = ? AND provider_event_id = ?",
        (provider, provider_event_id),
    ).fetchone()
    return row[0], row[1]


# --- Razorpay -----------------------------------------------------------


def _sign_razorpay(raw_body: bytes) -> str:
    return hmac.new(RAZORPAY_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()


def _razorpay_payload(
    order_id: str,
    *,
    event_id: str = "evt_test_1",
    event: str = "payment.captured",
    payment_id: str = "pay_test_1",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event": event,
        "payload": {
            "payment": {"entity": {"id": payment_id, "order_id": order_id, "status": "captured"}}
        },
    }


def test_razorpay_webhook_404_when_not_configured(client: TestClient):
    """Empty `razorpay_webhook_secret` must look exactly like a route that
    does not exist — not a distinguishable 'webhooks disabled' response."""
    response = client.post(
        "/webhooks/razorpay", content=b"{}", headers={"X-Razorpay-Signature": "x"}
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_valid_razorpay_signature_marks_pending_order_paid(
    client: TestClient, db: SQLiteDatabase, razorpay_webhook_env: None
):
    _insert_pending_order(
        db,
        provider="razorpay",
        provider_intent_id="order_RZP_1",
        order_id="ord_rzp_test",
        reference="TG-RZP-TEST",
        payment_id="pay_rzp_test",
    )
    payload = _razorpay_payload("order_RZP_1")
    raw = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign_razorpay(raw), "Content-Type": "application/json"},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}

    payment_status, order_status = _order_state(db, "ord_rzp_test")
    assert payment_status == "paid"
    assert order_status == "confirmed"
    status, intent_id = _payment_state(db, "pay_rzp_test")
    assert status == "paid"
    assert intent_id == "order_RZP_1"


def test_invalid_razorpay_signature_is_rejected(
    client: TestClient, db: SQLiteDatabase, razorpay_webhook_env: None
):
    _insert_pending_order(
        db,
        provider="razorpay",
        provider_intent_id="order_RZP_2",
        order_id="ord_rzp_bad_sig",
        reference="TG-RZP-BADSIG",
        payment_id="pay_rzp_bad_sig",
    )
    payload = _razorpay_payload("order_RZP_2")
    raw = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": "0" * 64, "Content-Type": "application/json"},
    )
    assert response.status_code == 401

    payment_status, _ = _order_state(db, "ord_rzp_bad_sig")
    assert payment_status == "pending"


def test_missing_razorpay_signature_header_is_rejected(
    client: TestClient, razorpay_webhook_env: None
):
    response = client.post(
        "/webhooks/razorpay",
        content=b'{"id":"evt_x","event":"payment.captured"}',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 401


def test_replayed_razorpay_event_is_idempotent(
    client: TestClient,
    db: SQLiteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    razorpay_webhook_env: None,
):
    _insert_pending_order(
        db,
        provider="razorpay",
        provider_intent_id="order_RZP_3",
        order_id="ord_rzp_replay",
        reference="TG-RZP-REPLAY",
        payment_id="pay_rzp_replay",
    )

    import truegrit_api.api.webhooks as webhooks_module

    reconcile_calls: list[None] = []
    original_reconcile = webhooks_module._reconcile_razorpay_payment

    async def counting_reconcile(db_arg: Any, payload_arg: Any) -> None:
        reconcile_calls.append(None)
        await original_reconcile(db_arg, payload_arg)

    monkeypatch.setattr(webhooks_module, "_reconcile_razorpay_payment", counting_reconcile)

    payload = _razorpay_payload("order_RZP_3", event_id="evt_replay_1")
    raw = json.dumps(payload).encode()
    headers = {"X-Razorpay-Signature": _sign_razorpay(raw), "Content-Type": "application/json"}

    first = client.post("/webhooks/razorpay", content=raw, headers=headers)
    assert first.status_code == 200

    second = client.post("/webhooks/razorpay", content=raw, headers=headers)
    assert second.status_code == 200
    assert second.json() == {"ok": True}

    # The second delivery only bumped attempt_count; reconciliation itself
    # ran exactly once, because the row was already 'processed' the second
    # time and the route short-circuits before touching payments/orders again.
    assert len(reconcile_calls) == 1
    attempt_count, processing_status = _webhook_event_row(db, "razorpay", "evt_replay_1")
    assert attempt_count == 2
    assert processing_status == "processed"

    payment_status, order_status = _order_state(db, "ord_rzp_replay")
    assert payment_status == "paid"
    assert order_status == "confirmed"


def test_unhandled_razorpay_event_type_is_recorded_but_not_reconciled(
    client: TestClient, db: SQLiteDatabase, razorpay_webhook_env: None
):
    _insert_pending_order(
        db,
        provider="razorpay",
        provider_intent_id="order_RZP_4",
        order_id="ord_rzp_other",
        reference="TG-RZP-OTHER",
        payment_id="pay_rzp_other",
    )
    payload = {"id": "evt_other_1", "event": "order.paid", "payload": {}}
    raw = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/razorpay",
        content=raw,
        headers={"X-Razorpay-Signature": _sign_razorpay(raw), "Content-Type": "application/json"},
    )
    assert response.status_code == 200

    payment_status, _ = _order_state(db, "ord_rzp_other")
    assert payment_status == "pending"
    _, processing_status = _webhook_event_row(db, "razorpay", "evt_other_1")
    assert processing_status == "processed"


# --- PayPal ---------------------------------------------------------------


def _paypal_payload(
    order_id: str,
    *,
    event_id: str = "WH-EVT-1",
    event_type: str = "PAYMENT.CAPTURE.COMPLETED",
    capture_id: str = "CAPTURE-1",
) -> dict[str, Any]:
    return {
        "id": event_id,
        "event_type": event_type,
        "resource": {
            "id": capture_id,
            "custom_id": order_id,
            "supplementary_data": {"related_ids": {"order_id": order_id}},
        },
    }


def test_paypal_webhook_404_when_not_configured(client: TestClient):
    response = client.post("/webhooks/paypal", content=b"{}", headers=_PAYPAL_HEADERS)
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_valid_paypal_signature_marks_pending_order_paid(
    client: TestClient,
    db: SQLiteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    paypal_webhook_env: None,
):
    _insert_pending_order(
        db,
        provider="paypal",
        provider_intent_id="PAYPAL-ORDER-1",
        order_id="ord_pp_test",
        reference="TG-PP-TEST",
        payment_id="pay_pp_test",
        currency="USD",
    )

    async def fake_verify(
        settings: Settings,
        *,
        headers: dict[str, str],
        raw_body: bytes,
        webhook_event: dict[str, Any],
    ) -> bool:
        return True

    monkeypatch.setattr("truegrit_api.api.webhooks.verify_paypal_webhook_signature", fake_verify)

    payload = _paypal_payload("PAYPAL-ORDER-1")
    raw = json.dumps(payload).encode()

    response = client.post("/webhooks/paypal", content=raw, headers=_PAYPAL_HEADERS)
    assert response.status_code == 200, response.text
    assert response.json() == {"ok": True}

    payment_status, order_status = _order_state(db, "ord_pp_test")
    assert payment_status == "paid"
    assert order_status == "confirmed"
    status, intent_id = _payment_state(db, "pay_pp_test")
    assert status == "paid"
    # provider_intent_id moves from the PayPal *order* id to the *capture* id,
    # exactly as `capture_paypal_payment` leaves it in api.storefront.
    assert intent_id == "CAPTURE-1"


def test_invalid_paypal_signature_is_rejected(
    client: TestClient,
    db: SQLiteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    paypal_webhook_env: None,
):
    _insert_pending_order(
        db,
        provider="paypal",
        provider_intent_id="PAYPAL-ORDER-2",
        order_id="ord_pp_bad_sig",
        reference="TG-PP-BADSIG",
        payment_id="pay_pp_bad_sig",
        currency="USD",
    )

    async def fake_verify(
        settings: Settings,
        *,
        headers: dict[str, str],
        raw_body: bytes,
        webhook_event: dict[str, Any],
    ) -> bool:
        return False

    monkeypatch.setattr("truegrit_api.api.webhooks.verify_paypal_webhook_signature", fake_verify)

    payload = _paypal_payload("PAYPAL-ORDER-2")
    raw = json.dumps(payload).encode()

    response = client.post("/webhooks/paypal", content=raw, headers=_PAYPAL_HEADERS)
    assert response.status_code == 401

    payment_status, _ = _order_state(db, "ord_pp_bad_sig")
    assert payment_status == "pending"


def test_replayed_paypal_event_is_idempotent(
    client: TestClient,
    db: SQLiteDatabase,
    monkeypatch: pytest.MonkeyPatch,
    paypal_webhook_env: None,
):
    _insert_pending_order(
        db,
        provider="paypal",
        provider_intent_id="PAYPAL-ORDER-3",
        order_id="ord_pp_replay",
        reference="TG-PP-REPLAY",
        payment_id="pay_pp_replay",
        currency="USD",
    )

    async def fake_verify(
        settings: Settings,
        *,
        headers: dict[str, str],
        raw_body: bytes,
        webhook_event: dict[str, Any],
    ) -> bool:
        return True

    monkeypatch.setattr("truegrit_api.api.webhooks.verify_paypal_webhook_signature", fake_verify)

    import truegrit_api.api.webhooks as webhooks_module

    reconcile_calls: list[None] = []
    original_reconcile = webhooks_module._reconcile_paypal_payment

    async def counting_reconcile(db_arg: Any, payload_arg: Any) -> None:
        reconcile_calls.append(None)
        await original_reconcile(db_arg, payload_arg)

    monkeypatch.setattr(webhooks_module, "_reconcile_paypal_payment", counting_reconcile)

    payload = _paypal_payload("PAYPAL-ORDER-3", event_id="WH-EVT-REPLAY")
    raw = json.dumps(payload).encode()

    first = client.post("/webhooks/paypal", content=raw, headers=_PAYPAL_HEADERS)
    assert first.status_code == 200

    second = client.post("/webhooks/paypal", content=raw, headers=_PAYPAL_HEADERS)
    assert second.status_code == 200
    assert second.json() == {"ok": True}

    assert len(reconcile_calls) == 1
    attempt_count, processing_status = _webhook_event_row(db, "paypal", "WH-EVT-REPLAY")
    assert attempt_count == 2
    assert processing_status == "processed"

    payment_status, order_status = _order_state(db, "ord_pp_replay")
    assert payment_status == "paid"
    assert order_status == "confirmed"


# --- verify_paypal_webhook_signature (unit-level, real HTTP plumbing) -----


def _paypal_verify_settings(**overrides: Any) -> Settings:
    base: dict[str, Any] = {
        "paypal_client_id": "client-123",
        "paypal_secret": "secret-123",
        "paypal_webhook_id": PAYPAL_WEBHOOK_ID,
    }
    base.update(overrides)
    return Settings(**base)


def test_verify_paypal_webhook_signature_posts_the_expected_body(monkeypatch: pytest.MonkeyPatch):
    posted: list[dict[str, Any]] = []

    async def fake_form(url: str, *, form: dict[str, str], headers: dict[str, str] | None = None):
        return {"access_token": "tok-999"}

    async def fake_json(url: str, *, body: Any, headers: dict[str, str] | None = None):
        posted.append({"url": url, "body": body, "headers": headers})
        return {"verification_status": "SUCCESS"}

    monkeypatch.setattr("truegrit_api.services.payments.post_form_async", fake_form)
    monkeypatch.setattr("truegrit_api.services.payments.post_json_async", fake_json)

    webhook_event = {"id": "WH-EVT-1", "event_type": "PAYMENT.CAPTURE.COMPLETED"}
    # Mixed case on purpose: proves the lookup is genuinely case-insensitive,
    # not merely tolerant of whatever case PayPal happens to send.
    headers = {
        "paypal-auth-algo": "SHA256withRSA",
        "Paypal-Cert-Url": "https://api.sandbox.paypal.com/cert",
        "PAYPAL-TRANSMISSION-ID": "txn-1",
        "PAYPAL-TRANSMISSION-SIG": "sig-1",
        "PAYPAL-TRANSMISSION-TIME": "2026-07-19T00:00:00Z",
    }

    result = asyncio.run(
        verify_paypal_webhook_signature(
            _paypal_verify_settings(),
            headers=headers,
            raw_body=json.dumps(webhook_event).encode(),
            webhook_event=webhook_event,
        )
    )

    assert result is True
    assert len(posted) == 1
    call = posted[0]
    assert call["url"].endswith("/v1/notifications/verify-webhook-signature")
    assert call["body"] == {
        "auth_algo": "SHA256withRSA",
        "cert_url": "https://api.sandbox.paypal.com/cert",
        "transmission_id": "txn-1",
        "transmission_sig": "sig-1",
        "transmission_time": "2026-07-19T00:00:00Z",
        "webhook_id": PAYPAL_WEBHOOK_ID,
        "webhook_event": webhook_event,
    }
    assert call["headers"]["authorization"] == "Bearer tok-999"


def test_verify_paypal_webhook_signature_rejects_failure_status(monkeypatch: pytest.MonkeyPatch):
    async def fake_form(url: str, *, form: dict[str, str], headers: dict[str, str] | None = None):
        return {"access_token": "tok-999"}

    async def fake_json(url: str, *, body: Any, headers: dict[str, str] | None = None):
        return {"verification_status": "FAILURE"}

    monkeypatch.setattr("truegrit_api.services.payments.post_form_async", fake_form)
    monkeypatch.setattr("truegrit_api.services.payments.post_json_async", fake_json)

    result = asyncio.run(
        verify_paypal_webhook_signature(
            _paypal_verify_settings(),
            headers=_PAYPAL_HEADERS,
            raw_body=b"{}",
            webhook_event={},
        )
    )
    assert result is False


def test_verify_paypal_webhook_signature_missing_header_short_circuits(
    monkeypatch: pytest.MonkeyPatch,
):
    token_calls: list[None] = []

    async def fake_form(url: str, *, form: dict[str, str], headers: dict[str, str] | None = None):
        token_calls.append(None)
        return {"access_token": "tok-999"}

    monkeypatch.setattr("truegrit_api.services.payments.post_form_async", fake_form)

    headers = dict(_PAYPAL_HEADERS)
    del headers["PAYPAL-TRANSMISSION-SIG"]

    result = asyncio.run(
        verify_paypal_webhook_signature(
            _paypal_verify_settings(), headers=headers, raw_body=b"{}", webhook_event={}
        )
    )
    assert result is False
    # Never even spent a round trip fetching a token for an unverifiable request.
    assert token_calls == []


def test_verify_paypal_webhook_signature_unconfigured_returns_false():
    result = asyncio.run(
        verify_paypal_webhook_signature(
            _paypal_verify_settings(paypal_webhook_id=""),
            headers=_PAYPAL_HEADERS,
            raw_body=b"{}",
            webhook_event={},
        )
    )
    assert result is False

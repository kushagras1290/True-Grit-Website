"""Integration tests: admin-only farm-owner creation, durable email jobs, and the
password-reset flows for the customer and staff portals.

Seeds its own farm (`farm_riverbend`) and a purchasable product on it rather
than depending on the demo catalogue: migration 0095 retires that catalogue
(including `farm_devika` and its `farm_members` link) from every database it
touches (the live site must not keep any trace of it), so tests cannot rely
on it surviving either. `usr_farmowner` (`owner@devika.test`) is itself an
ordinary staff seed account -- like `usr_admin` -- that migration 0095 never
touches, so it is reused as-is; only its farm membership needs to be
re-created against the new fixture farm.
"""

from __future__ import annotations

import json
import re

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.config import get_settings
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}

FARM_ID = "farm_riverbend"
FARM_NAME = "Riverbend Growers"
PRODUCT_VARIANT_ID = "var_riverbend_test_1kg"


@pytest.fixture(autouse=True)
def _fast_hashing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("pbkdf2_iterations", "1000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _farm_owner_baseline(db: SQLiteDatabase) -> None:
    """A fresh farm, its owner membership, and one purchasable product on it --
    everything `test_admin_creates_farm_owner_who_can_sign_in` and
    `test_checkout_queues_customer_and_farm_owner_emails` need, without
    touching the retired demo catalogue."""
    db._conn.executescript(
        f"""
        INSERT INTO farms (id, name, slug, country_code, status, created_at,
          created_by, updated_at, updated_by)
        VALUES ('{FARM_ID}', '{FARM_NAME}', 'riverbend-growers', 'IN', 'published',
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO farm_members (user_id, farm_id, created_at, created_by)
        VALUES ('usr_farmowner', '{FARM_ID}', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO products (id, internal_name, name, slug, product_type, farm_id, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_riverbend_test', 'Riverbend Test Product', 'Riverbend Test Product',
          'riverbend-test-product', 'simple', '{FARM_ID}', 'published', 1,
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('{PRODUCT_VARIANT_ID}', 'prd_riverbend_test', 'RVB-TEST-1KG', '1 kg',
          'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_riverbend_test_1kg', '{PRODUCT_VARIANT_ID}', 'IN', 'INR', 89900,
          'active', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('{PRODUCT_VARIANT_ID}', 'loc_mumbai', 500, 0, 20, 1, '2026-07-01T00:00:00Z');
        """
    )
    db._conn.commit()


def _token_from(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    return match.group(1) if match else None


def _pending_emails(db: SQLiteDatabase) -> list[dict[str, object]]:
    rows = db._conn.execute(
        "SELECT payload_json FROM outbox_events WHERE event_type = 'notification.email.v1'"
    ).fetchall()
    return [json.loads(row["payload_json"]) for row in rows]


# --- Farm-owner creation (admin panel only) ---------------------------------


def test_admin_creates_farm_owner_who_can_sign_in(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    farms = client.get("/v1/admin/farms").json()["items"]
    farm_id = next(farm["id"] for farm in farms if farm["name"] == FARM_NAME)

    created = client.post(
        "/v1/admin/farm-owners",
        json={
            "email": "new-owner@example.test",
            "displayName": "New Owner",
            "farmId": farm_id,
            "password": "strongpass12",
        },
    )
    assert created.status_code == 200

    client.cookies.clear()
    login = client.post(
        "/v1/admin/auth/login",
        json={"email": "new-owner@example.test", "password": "strongpass12"},
    )
    assert login.status_code == 200
    assert client.get("/v1/admin/me").json()["farmId"] == farm_id


def test_farm_owner_cannot_create_farm_owner(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post(
        "/v1/admin/farm-owners",
        json={
            "email": "x@example.test",
            "displayName": "X",
            "farmId": FARM_ID,
            "password": "strongpass12",
        },
    )
    assert response.status_code == 403


# --- Order emails -----------------------------------------------------------


def test_checkout_queues_customer_and_farm_owner_emails(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": PRODUCT_VARIANT_ID, "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    recipients = {str(email["to"]) for email in _pending_emails(db)}
    assert "riya@example.test" in recipients  # customer confirmation
    assert "owner@devika.test" in recipients  # owner of farm_riverbend


def test_contact_form_records_message_and_sends_email(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("CONTACT_RECIPIENT_EMAIL", "support@truegrit.test")
    get_settings.cache_clear()
    response = client.post(
        "/v1/public/contact",
        json={
            "name": "Riya Nair",
            "email": "riya@example.test",
            # Typed the way a customer actually types it: no country code, one
            # space. It must land in the column as E.164.
            "phone": "98765 43210",
            "subject": "Order help",
            "message": "Please help with my latest order delivery.",
        },
    )
    assert response.status_code == 200
    row = db._conn.execute(
        "SELECT email, phone_e164, subject, message FROM contact_messages WHERE id = ?",
        (response.json()["id"],),
    ).fetchone()
    assert row["email"] == "riya@example.test"
    assert row["phone_e164"] == "+919876543210"
    assert row["subject"] == "Order help"
    assert "latest order" in row["message"]
    emails = _pending_emails(db)
    assert [(email["to"], email["subject"]) for email in emails] == [
        ("support@truegrit.test", "Contact form: Order help")
    ]


def test_contact_form_requires_a_reachable_phone_number(client: TestClient):
    """The number is what makes the inbox actionable, so an absent or
    unringable one is refused rather than stored as typed."""
    base = {
        "name": "Riya Nair",
        "email": "riya@example.test",
        "subject": "Order help",
        "message": "Please help with my latest order delivery.",
    }
    assert client.post("/v1/public/contact", json=base).status_code == 422
    # 10 digits but starting with 1: not an Indian mobile, and not marked
    # international either.
    assert (
        client.post("/v1/public/contact", json={**base, "phone": "1234567890"}).status_code == 422
    )


# --- Customer password reset ------------------------------------------------


def test_customer_password_reset_flow(client: TestClient, db: SQLiteDatabase):
    assert (
        client.post(
            "/v1/public/auth/password-reset", json={"email": "riya@example.test"}
        ).status_code
        == 200
    )
    token = _token_from(str(_pending_emails(db)[0]["body"]))
    assert token is not None

    confirm = client.post(
        "/v1/public/auth/password-reset/confirm",
        json={"token": token, "newPassword": "brandnewpass1"},
    )
    assert confirm.status_code == 200

    client.cookies.clear()
    login = client.post(
        "/v1/public/auth/login",
        json={"email": "riya@example.test", "password": "brandnewpass1"},
    )
    assert login.status_code == 200


def test_reset_request_is_silent_for_unknown_email(client: TestClient, db: SQLiteDatabase):
    assert (
        client.post(
            "/v1/public/auth/password-reset", json={"email": "nobody@example.test"}
        ).status_code
        == 200
    )
    count = db._conn.execute("SELECT COUNT(*) FROM password_reset_tokens").fetchone()[0]
    assert count == 0


def test_reset_confirm_rejects_bad_token(client: TestClient):
    response = client.post(
        "/v1/public/auth/password-reset/confirm",
        json={"token": "not-a-real-token", "newPassword": "brandnewpass1"},
    )
    assert response.status_code == 422


# --- Staff password reset ---------------------------------------------------


def test_staff_password_reset_flow(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "truegrit_api.services.email_gate.send_email",
        lambda to, subject, body, settings=None, html_body=None, preferred_provider=None: (
            captured.update(body=body) or True
        ),
    )
    assert (
        client.post(
            "/v1/admin/auth/password-reset", json={"email": "owner@devika.test"}
        ).status_code
        == 200
    )
    token = _token_from(captured["body"])
    assert token is not None

    assert (
        client.post(
            "/v1/admin/auth/password-reset/confirm",
            json={"token": token, "newPassword": "resetfarm123"},
        ).status_code
        == 200
    )
    login = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner@devika.test", "password": "resetfarm123"},
    )
    assert login.status_code == 200

    audit = db._conn.execute(
        """
        SELECT action, entity_type, entity_id, actor_user_id, after_summary_json, source
        FROM audit_logs
        WHERE action = 'password.changed' AND entity_id = 'usr_farmowner'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert audit is not None
    assert audit["entity_type"] == "user"
    assert audit["actor_user_id"] == "usr_farmowner"
    assert audit["source"] == "admin"
    after = json.loads(audit["after_summary_json"])
    assert after == {
        "email": "owner@devika.test",
        "userType": "staff",
        "activatedFromInvite": False,
        "credentialChanged": True,
        "passwordStored": False,
    }
    assert "resetfarm123" not in audit["after_summary_json"]

"""Integration tests: admin-only farm-owner creation, order emails, and the
password-reset flows for the customer and staff portals."""

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


@pytest.fixture(autouse=True)
def _fast_hashing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("pbkdf2_iterations", "1000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _token_from(body: str) -> str | None:
    match = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    return match.group(1) if match else None


# --- Farm-owner creation (admin panel only) ---------------------------------


def test_admin_creates_farm_owner_who_can_sign_in(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    farms = client.get("/v1/admin/farms").json()["items"]
    farm_id = next(farm["id"] for farm in farms if farm["name"] == "Devika Organics")

    created = client.post(
        "/v1/admin/farm-owners",
        json={
            "email": "new-owner@devika.test",
            "displayName": "New Owner",
            "farmId": farm_id,
            "password": "strongpass12",
        },
    )
    assert created.status_code == 200

    client.cookies.clear()
    login = client.post(
        "/v1/admin/auth/login",
        json={"email": "new-owner@devika.test", "password": "strongpass12"},
    )
    assert login.status_code == 200
    assert client.get("/v1/admin/me").json()["farmId"] == farm_id


def test_farm_owner_cannot_create_farm_owner(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post(
        "/v1/admin/farm-owners",
        json={
            "email": "x@devika.test",
            "displayName": "X",
            "farmId": "farm_devika",
            "password": "strongpass12",
        },
    )
    assert response.status_code == 403


# --- Order emails -----------------------------------------------------------


def test_checkout_emails_customer_and_farm_owner(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    sent: list[str] = []
    monkeypatch.setattr(
        "truegrit_api.api.storefront.send_email",
        lambda to, subject, body, settings=None, html_body=None: sent.append(to),
    )
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200
    assert "riya@example.test" in sent  # customer confirmation
    assert "owner@devika.test" in sent  # owner of farm_devika (Alphonso)


def test_contact_form_records_message_and_sends_email(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    sent: list[tuple[str, str]] = []
    monkeypatch.setenv("CONTACT_RECIPIENT_EMAIL", "support@truegrit.test")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "truegrit_api.api.public.send_email",
        lambda to, subject, body, settings=None, html_body=None: sent.append((to, subject)),
    )
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
    assert sent == [("support@truegrit.test", "Contact form: Order help")]


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


def test_customer_password_reset_flow(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    captured: dict[str, str] = {}
    monkeypatch.setattr(
        "truegrit_api.api.customer_auth.send_email",
        lambda to, subject, body, settings=None, html_body=None: captured.update(body=body),
    )
    assert (
        client.post(
            "/v1/public/auth/password-reset", json={"email": "riya@example.test"}
        ).status_code
        == 200
    )
    token = _token_from(captured["body"])
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
        "truegrit_api.api.admin.send_email",
        lambda to, subject, body, settings=None, html_body=None: captured.update(body=body),
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

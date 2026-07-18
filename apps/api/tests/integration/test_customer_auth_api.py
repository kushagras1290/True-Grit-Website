"""Integration tests for storefront customer authentication."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import (
    SESSION_COOKIE,
    TEST_PHONE,
    create_session,
    verify_phone_token,
)
from truegrit_api.auth.facebook import FacebookIdentity
from truegrit_api.auth.google import GoogleIdentity
from truegrit_api.config import get_settings
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch):
    """Keep PBKDF2 cheap in tests; restore the real work factor afterwards."""
    monkeypatch.setenv("pbkdf2_iterations", "1000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def register(client: TestClient, sms_outbox=None, **overrides):
    """Register through the real flow: verify a mobile, then redeem that proof.

    Registration requires a verified number (`phone_required_at_registration`),
    so every caller needs the outbox to read the passcode. Tests that assert on
    the *absence* of a token pass `phoneVerificationToken=None` explicitly.
    """
    body = {"name": "Priya Sharma", "email": "priya@example.com", "password": "sunflower-seeds"}
    if sms_outbox is not None and "phoneVerificationToken" not in overrides:
        body["phoneVerificationToken"] = verify_phone_token(client, sms_outbox)
    body.update(overrides)
    return client.post("/v1/public/auth/register", json=body)


def test_register_creates_session_and_me(client: TestClient, sms_outbox):
    response = register(client, sms_outbox)
    assert response.status_code == 200
    customer = response.json()["customer"]
    assert customer["email"] == "priya@example.com"
    assert customer["phone"] == f"+91{TEST_PHONE}"
    assert customer["phoneVerified"] is True
    assert SESSION_COOKIE in response.cookies

    me = client.get("/v1/public/auth/me")
    assert me.status_code == 200
    assert me.json()["displayName"] == "Priya Sharma"
    assert me.json()["phoneVerified"] is True


def test_register_without_verified_phone_is_rejected(client: TestClient):
    response = register(client)
    assert response.status_code == 422
    # Its own code so the storefront reopens the SMS step rather than showing a
    # field error the customer cannot act on.
    assert response.json()["error"]["code"] == "phone_verification_required"


def test_register_rejects_duplicate_email(client: TestClient, sms_outbox):
    assert register(client, sms_outbox).status_code == 200
    client.cookies.clear()
    # A second number: reusing the first would trip the phone conflict before the
    # email one, and this test is about the email.
    duplicate = register(
        client,
        sms_outbox,
        name="Someone Else",
        phoneVerificationToken=verify_phone_token(client, sms_outbox, phone="9999900002"),
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_register_rejects_phone_already_linked(client: TestClient, sms_outbox):
    assert register(client, sms_outbox).status_code == 200
    client.cookies.clear()
    duplicate = register(
        client,
        sms_outbox,
        email="other@example.com",
        phoneVerificationToken=verify_phone_token(client, sms_outbox),
    )
    assert duplicate.status_code == 409


def test_register_rejects_short_password(client: TestClient):
    response = register(client, password="short")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_register_rejects_invalid_email(client: TestClient):
    response = register(client, email="not-an-email")
    assert response.status_code == 422


def test_login_success_and_wrong_password(client: TestClient, sms_outbox):
    register(client, sms_outbox)
    client.cookies.clear()

    ok = client.post(
        "/v1/public/auth/login",
        json={"email": "priya@example.com", "password": "sunflower-seeds"},
    )
    assert ok.status_code == 200
    assert SESSION_COOKIE in ok.cookies

    client.cookies.clear()
    bad = client.post(
        "/v1/public/auth/login",
        json={"email": "priya@example.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401
    assert bad.json()["error"]["message"] == "Invalid email or password."


def test_login_unknown_email_is_generic_401(client: TestClient):
    response = client.post(
        "/v1/public/auth/login",
        json={"email": "nobody@example.com", "password": "whatever-value"},
    )
    assert response.status_code == 401
    assert response.json()["error"]["message"] == "Invalid email or password."


def test_logout_revokes_session(client: TestClient, sms_outbox):
    register(client, sms_outbox)
    assert client.get("/v1/public/auth/me").status_code == 200
    assert client.post("/v1/public/auth/logout").status_code == 200
    assert client.get("/v1/public/auth/me").status_code == 401


def test_me_requires_authentication(client: TestClient):
    assert client.get("/v1/public/auth/me").status_code == 401


def test_staff_session_cannot_access_customer_me(client: TestClient, db: SQLiteDatabase):
    token = create_session(db, client, "usr_admin")
    client.cookies.set(SESSION_COOKIE, token)
    assert client.get("/v1/public/auth/me").status_code == 401


def test_google_not_configured_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "")
    get_settings.cache_clear()
    response = client.post("/v1/public/auth/google", json={"credential": "any.jwt.value"})
    assert response.status_code == 401
    assert "not configured" in response.json()["error"]["message"]


def test_google_sign_in_creates_and_relinks_customer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    identity = GoogleIdentity(
        subject="google-999", email="green@example.com", email_verified=True, name="Green Thumb"
    )
    monkeypatch.setattr(
        "truegrit_api.api.customer_auth.verify_google_id_token",
        lambda credential, *, client_id: identity,
    )

    first = client.post("/v1/public/auth/google", json={"credential": "stub.jwt.token"})
    assert first.status_code == 200
    assert first.json()["customer"]["email"] == "green@example.com"
    assert client.get("/v1/public/auth/me").json()["displayName"] == "Green Thumb"

    # Signing in again with the same Google subject reuses the same account.
    client.cookies.clear()
    second = client.post("/v1/public/auth/google", json={"credential": "stub.jwt.token"})
    assert second.status_code == 200
    assert second.json()["customer"]["id"] == first.json()["customer"]["id"]


def test_facebook_not_configured_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FACEBOOK_APP_ID", "")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "")
    get_settings.cache_clear()
    response = client.post("/v1/public/auth/facebook", json={"accessToken": "facebook-token"})
    assert response.status_code == 401
    assert "not configured" in response.json()["error"]["message"]


def test_facebook_sign_in_creates_and_relinks_customer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("FACEBOOK_APP_ID", "facebook-app-id")
    monkeypatch.setenv("FACEBOOK_APP_SECRET", "facebook-app-secret")
    get_settings.cache_clear()
    identity = FacebookIdentity(
        subject="facebook-999", email="grower@example.com", name="FB Grower"
    )

    async def verify(access_token: str, *, app_id: str, app_secret: str) -> FacebookIdentity:
        assert access_token == "stub-access-token"
        assert app_id == "facebook-app-id"
        assert app_secret == "facebook-app-secret"
        return identity

    monkeypatch.setattr(
        "truegrit_api.api.customer_auth.verify_facebook_access_token",
        verify,
    )

    first = client.post("/v1/public/auth/facebook", json={"accessToken": "stub-access-token"})
    assert first.status_code == 200
    assert first.json()["customer"]["email"] == "grower@example.com"
    assert client.get("/v1/public/auth/me").json()["displayName"] == "FB Grower"

    client.cookies.clear()
    second = client.post("/v1/public/auth/facebook", json={"accessToken": "stub-access-token"})
    assert second.status_code == 200
    assert second.json()["customer"]["id"] == first.json()["customer"]["id"]


def test_login_is_rate_limited_per_account(client: TestClient, sms_outbox):
    register(client, sms_outbox)
    client.cookies.clear()
    # Default per-account limit is 5; the 6th attempt is blocked before the
    # password is even checked.
    statuses = []
    for _ in range(6):
        response = client.post(
            "/v1/public/auth/login",
            json={"email": "priya@example.com", "password": "wrong-password"},
        )
        statuses.append(response.status_code)
        client.cookies.clear()
    assert statuses[:5] == [401, 401, 401, 401, 401]
    assert statuses[5] == 429


def test_global_rate_limit_middleware(monkeypatch: pytest.MonkeyPatch, db: SQLiteDatabase):
    monkeypatch.setenv("rate_limit_global_per_ip", "3")
    get_settings.cache_clear()
    limited_client = TestClient(create_app(db=db), raise_server_exceptions=False)

    for _ in range(3):
        assert limited_client.get("/v1/public/bootstrap").status_code == 200
    blocked = limited_client.get("/v1/public/bootstrap")
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"]
    assert blocked.json()["error"]["code"] == "rate_limited"
    # Liveness probes are exempt so orchestrators never see a throttled health check.
    assert limited_client.get("/health/live").status_code == 200

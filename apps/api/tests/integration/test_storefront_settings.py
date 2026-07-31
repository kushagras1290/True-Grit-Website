"""Storefront feature switches: sign-in methods, taking payments, blog banner.

The point of these switches is that they hold on the API, not just in the
storefront UI, so most of what is worth testing here is a route refusing after a
switch is flipped — hiding a button stops the honest customer, not a replayed
request.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from truegrit_api.platform.database import SQLiteDatabase

from .conftest import SESSION_COOKIE, TEST_PHONE, create_session, verify_phone_token

SETTINGS_PATH = "/v1/admin/storefront-settings"
PUBLIC_SETTINGS_PATH = "/v1/public/settings"


def set_switch(db: SQLiteDatabase, key: str, value: str) -> None:
    """Write a switch straight to `app_settings`, the way the admin PATCH would.

    Bypassing the endpoint keeps these tests about the enforcement they are
    checking rather than about admin authentication, which has its own suite.
    """
    db._conn.execute(  # test-only direct access
        "INSERT INTO app_settings (key, value, updated_at) VALUES (?, ?, '2026-07-31T00:00:00Z')"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    db._conn.commit()


def owner_cookies(db: SQLiteDatabase) -> dict[str, str]:
    """A session for the seeded super-admin (`usr_admin`)."""
    return {SESSION_COOKIE: create_session(db, "usr_admin")}


# --- Defaults ---------------------------------------------------------------


def test_public_settings_defaults_to_everything_on(client: TestClient):
    body = client.get(PUBLIC_SETTINGS_PATH).json()
    assert body["auth"]["phoneOtp"] is True
    assert body["auth"]["password"] is True
    assert body["auth"]["registration"] is True
    assert body["payments"]["enabled"] is True
    assert body["payments"]["disabledNotice"]


def test_unconfigured_providers_report_unavailable(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    """A switch can only take a method away, never conjure one: with no client
    id or app secret configured, Google and Facebook stay off even though their
    switches default to on.

    The credentials are cleared explicitly rather than assumed absent — a
    developer's local `apps/api/.env` may well have real ones.
    """
    from truegrit_api.config import get_settings

    for name in ("GOOGLE_CLIENT_ID", "FACEBOOK_APP_ID", "FACEBOOK_APP_SECRET"):
        monkeypatch.setenv(name, "")
    get_settings.cache_clear()
    try:
        auth = client.get(PUBLIC_SETTINGS_PATH).json()["auth"]
        assert auth["google"] is False
        assert auth["facebook"] is False
    finally:
        get_settings.cache_clear()


def test_unreadable_switch_falls_back_to_enabled(client: TestClient, db: SQLiteDatabase):
    """A hand-edited or truncated row must degrade to the shipped behaviour, not
    lock every customer out."""
    set_switch(db, "auth.password.enabled", "not-a-boolean")
    assert client.get(PUBLIC_SETTINGS_PATH).json()["auth"]["password"] is True


# --- Sign-in enforcement ----------------------------------------------------


def test_password_sign_in_switch_blocks_login(client: TestClient, db: SQLiteDatabase):
    set_switch(db, "auth.password.enabled", "0")
    response = client.post(
        "/v1/public/auth/login", json={"email": "someone@example.test", "password": "irrelevant"}
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"
    assert client.get(PUBLIC_SETTINGS_PATH).json()["auth"]["password"] is False


def test_registration_switch_blocks_sign_up(client: TestClient, db: SQLiteDatabase):
    set_switch(db, "auth.registration.enabled", "0")
    response = client.post(
        "/v1/public/auth/register",
        json={"name": "Priya Sharma", "email": "priya@example.test", "password": "a-long-password"},
    )
    assert response.status_code == 403


def test_phone_switch_blocks_passcode_issue(client: TestClient, db: SQLiteDatabase):
    set_switch(db, "auth.phone_otp.enabled", "0")
    response = client.post("/v1/public/auth/phone/start", json={"phone": TEST_PHONE})
    assert response.status_code == 403


def test_google_switch_blocks_google_sign_in(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    """403 even with a client id configured — otherwise this would be
    indistinguishable from the "not configured" 401 the verifier already
    returns, and the two need different fixes."""
    from truegrit_api.config import get_settings

    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id.apps.googleusercontent.com")
    get_settings.cache_clear()
    try:
        set_switch(db, "auth.google.enabled", "0")
        response = client.post("/v1/public/auth/google", json={"credential": "any.jwt.value"})
        assert response.status_code == 403
    finally:
        monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
        get_settings.cache_clear()


def test_registration_drops_phone_requirement_when_passcodes_are_off(
    client: TestClient, db: SQLiteDatabase
):
    """`phone_required_at_registration` is a stricter rule, not an impossible
    one: with no way to verify a number, demanding one would make sign-up
    unreachable rather than merely tighter."""
    set_switch(db, "auth.phone_otp.enabled", "0")
    response = client.post(
        "/v1/public/auth/register",
        json={"name": "Ravi Patil", "email": "ravi@example.test", "password": "a-long-password"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["customer"]["phone"] is None


def test_registration_still_requires_a_verified_phone_when_passcodes_are_on(client: TestClient):
    response = client.post(
        "/v1/public/auth/register",
        json={"name": "Tara Negi", "email": "tara@example.test", "password": "a-long-password"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "phone_verification_required"


# --- Payments enforcement ---------------------------------------------------


def test_payments_switch_empties_payment_methods(client: TestClient, db: SQLiteDatabase):
    set_switch(db, "commerce.payments.enabled", "0")
    body = client.get("/v1/public/payment-methods").json()
    assert body["methods"] == []
    assert body["razorpayKeyId"] == ""


def test_payments_switch_refuses_checkout(client: TestClient, db: SQLiteDatabase, sms_outbox: list):
    """The switch has to bite before `place_order` runs, or a customer who
    cannot pay still has stock reserved against their name."""
    token = verify_phone_token(client, sms_outbox)
    registered = client.post(
        "/v1/public/auth/register",
        json={
            "name": "Meera Iyer",
            "email": "meera@example.test",
            "password": "a-long-password",
            "phoneVerificationToken": token,
        },
    )
    assert registered.status_code == 200, registered.text

    set_switch(db, "commerce.payments.enabled", "0")
    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_mango_1kg", "quantity": 1}],
            "deliveryAddress": {
                "recipientName": "Meera Iyer",
                "line1": "12 Hill Road",
                "city": "Mumbai",
                "state": "Maharashtra",
                "postalCode": "400050",
            },
            "paymentMethod": "cod",
        },
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


# --- Admin endpoint ---------------------------------------------------------


def test_admin_can_read_and_flip_switches(client: TestClient, db: SQLiteDatabase):
    cookies = owner_cookies(db)

    initial = client.get(SETTINGS_PATH, cookies=cookies)
    assert initial.status_code == 200, initial.text
    assert initial.json()["settings"]["payments"] is True

    patched = client.patch(SETTINGS_PATH, json={"payments": False}, cookies=cookies)
    assert patched.status_code == 200, patched.text
    assert patched.json()["settings"]["payments"] is False
    assert patched.json()["effective"]["payments"] is False

    assert client.get("/v1/public/settings").json()["payments"]["enabled"] is False


def test_patch_only_touches_the_fields_it_was_sent(client: TestClient, db: SQLiteDatabase):
    """A PATCH that flips one switch must not overwrite the others with whatever
    the client last rendered."""
    cookies = owner_cookies(db)
    client.patch(SETTINGS_PATH, json={"googleSignIn": False}, cookies=cookies)
    after = client.patch(SETTINGS_PATH, json={"payments": False}, cookies=cookies).json()
    assert after["settings"]["googleSignIn"] is False
    assert after["settings"]["passwordSignIn"] is True


def test_payments_notice_is_editable_and_published(client: TestClient, db: SQLiteDatabase):
    cookies = owner_cookies(db)
    notice = "Back on Monday — leave your number and we will call."
    patched = client.patch(SETTINGS_PATH, json={"paymentsDisabledNotice": notice}, cookies=cookies)
    assert patched.status_code == 200, patched.text
    assert client.get(PUBLIC_SETTINGS_PATH).json()["payments"]["disabledNotice"] == notice


def test_blank_notice_falls_back_to_the_default(client: TestClient, db: SQLiteDatabase):
    """An empty box must not leave the paused-checkout page with no explanation
    on it at all."""
    cookies = owner_cookies(db)
    patched = client.patch(SETTINGS_PATH, json={"paymentsDisabledNotice": "  "}, cookies=cookies)
    assert patched.json()["settings"]["paymentsDisabledNotice"].strip() != ""


def test_blog_banner_rejects_a_protocol_relative_url(client: TestClient, db: SQLiteDatabase):
    """`//evil.example` would hand control of the banner to whoever owns that
    host."""
    response = client.patch(
        SETTINGS_PATH,
        json={"blogBannerImageUrl": "//evil.example/x.png"},
        cookies=owner_cookies(db),
    )
    assert response.status_code == 422


def test_blog_banner_round_trips(client: TestClient, db: SQLiteDatabase):
    patched = client.patch(
        SETTINGS_PATH,
        json={"blogBannerImageUrl": "/media/banner.png", "blogBannerImageAlt": "Harvest table"},
        cookies=owner_cookies(db),
    )
    assert patched.status_code == 200, patched.text
    banners = client.get(PUBLIC_SETTINGS_PATH).json()["banners"]
    assert banners["blogImageUrl"] == "/media/banner.png"
    assert banners["blogImageAlt"] == "Harvest table"


def test_switches_require_settings_permission(client: TestClient, db: SQLiteDatabase):
    """The blogger role authors content; it has no business closing the shop."""
    response = client.get(
        SETTINGS_PATH, cookies={SESSION_COOKIE: create_session(db, "usr_blogger")}
    )
    assert response.status_code == 403

"""Integration tests for mobile-number authentication.

Weighted towards the properties that make OTP safe rather than the happy path:
single-use tokens, attempt ceilings, expiry, and not leaking who is registered.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, TEST_PHONE, verify_phone_token
from truegrit_api.config import get_settings

PHONE_E164 = f"+91{TEST_PHONE}"


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("pbkdf2_iterations", "1000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def start(client: TestClient, phone: str = TEST_PHONE, path: str = "/v1/public/auth/phone/start"):
    return client.post(path, json={"phone": phone})


def sign_up_by_phone(client: TestClient, sms_outbox, name: str = "Ravi Kumar", phone=TEST_PHONE):
    token = verify_phone_token(
        client, sms_outbox, phone=phone, start_path="/v1/public/auth/phone/start"
    )
    return client.post(
        "/v1/public/auth/phone/complete", json={"verificationToken": token, "name": name}
    )


# --- Sign-up and sign-in ----------------------------------------------------


def test_phone_signup_creates_account_and_session(client: TestClient, sms_outbox):
    response = sign_up_by_phone(client, sms_outbox)
    assert response.status_code == 200, response.text
    customer = response.json()["customer"]
    assert customer["displayName"] == "Ravi Kumar"
    assert customer["phone"] == PHONE_E164
    assert customer["phoneVerified"] is True
    # A phone-only account has no address; the synthetic placeholder that
    # satisfies users.email NOT NULL must never surface.
    assert customer["email"] is None
    assert SESSION_COOKIE in response.cookies

    me = client.get("/v1/public/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] is None
    assert me.json()["phone"] == PHONE_E164


def test_phone_signin_returns_existing_account(client: TestClient, sms_outbox):
    first = sign_up_by_phone(client, sms_outbox)
    user_id = first.json()["customer"]["id"]
    client.cookies.clear()

    token = verify_phone_token(
        client, sms_outbox, start_path="/v1/public/auth/phone/start"
    )
    again = client.post("/v1/public/auth/phone/complete", json={"verificationToken": token})
    assert again.status_code == 200
    # Same account, not a second one — the mobile is the identifier.
    assert again.json()["customer"]["id"] == user_id


def test_verify_reports_registration_state(client: TestClient, sms_outbox):
    started = start(client)
    code = sms_outbox[-1].body
    verified = client.post(
        "/v1/public/auth/phone/verify",
        json={"challengeId": started.json()["challengeId"], "code": code},
    )
    assert verified.json()["registered"] is False

    client.post(
        "/v1/public/auth/phone/complete",
        json={"verificationToken": verified.json()["verificationToken"], "name": "Ravi"},
    )
    client.cookies.clear()

    started2 = start(client)
    verified2 = client.post(
        "/v1/public/auth/phone/verify",
        json={"challengeId": started2.json()["challengeId"], "code": sms_outbox[-1].body},
    )
    assert verified2.json()["registered"] is True


def test_complete_without_name_for_new_number_is_rejected(client: TestClient, sms_outbox):
    token = verify_phone_token(client, sms_outbox, start_path="/v1/public/auth/phone/start")
    response = client.post("/v1/public/auth/phone/complete", json={"verificationToken": token})
    assert response.status_code == 422


# --- Enumeration ------------------------------------------------------------


def test_start_does_not_reveal_whether_number_is_registered(client: TestClient, sms_outbox):
    sign_up_by_phone(client, sms_outbox)
    client.cookies.clear()

    registered = start(client, TEST_PHONE)
    unregistered = start(client, "9999900007")
    assert registered.status_code == unregistered.status_code == 200
    # Same shape, same keys — nothing to distinguish the two.
    assert set(registered.json()) == set(unregistered.json())
    assert "registered" not in registered.json()


# --- Passcode handling ------------------------------------------------------


def test_wrong_code_is_rejected_and_burns_attempts(client: TestClient, sms_outbox):
    started = start(client)
    challenge_id = started.json()["challengeId"]

    for _ in range(get_settings().otp_max_attempts):
        bad = client.post(
            "/v1/public/auth/phone/verify",
            json={"challengeId": challenge_id, "code": "000000"},
        )
        assert bad.status_code == 422

    # The real code no longer helps: the guess budget is spent.
    real = client.post(
        "/v1/public/auth/phone/verify",
        json={"challengeId": challenge_id, "code": sms_outbox[-1].body},
    )
    assert real.status_code == 422


def test_code_is_single_use(client: TestClient, sms_outbox):
    started = start(client)
    challenge_id = started.json()["challengeId"]
    code = sms_outbox[-1].body

    assert (
        client.post(
            "/v1/public/auth/phone/verify", json={"challengeId": challenge_id, "code": code}
        ).status_code
        == 200
    )
    replay = client.post(
        "/v1/public/auth/phone/verify", json={"challengeId": challenge_id, "code": code}
    )
    assert replay.status_code == 422


def test_verification_token_is_single_use(client: TestClient, sms_outbox):
    token = verify_phone_token(client, sms_outbox, start_path="/v1/public/auth/phone/start")
    first = client.post(
        "/v1/public/auth/phone/complete", json={"verificationToken": token, "name": "Ravi"}
    )
    assert first.status_code == 200
    client.cookies.clear()

    # Replaying the token must not mint a second session for the same proof.
    replay = client.post(
        "/v1/public/auth/phone/complete", json={"verificationToken": token, "name": "Ravi"}
    )
    assert replay.status_code == 422
    assert SESSION_COOKIE not in replay.cookies


def test_resend_invalidates_the_previous_code(client: TestClient, sms_outbox, monkeypatch):
    monkeypatch.setenv("otp_resend_cooldown_seconds", "0")
    get_settings.cache_clear()
    started = start(client)
    challenge_id = started.json()["challengeId"]
    first_code = sms_outbox[-1].body

    resent = client.post("/v1/public/auth/phone/resend", json={"challengeId": challenge_id})
    assert resent.status_code == 200
    second_code = sms_outbox[-1].body
    assert first_code != second_code

    stale = client.post(
        "/v1/public/auth/phone/verify", json={"challengeId": challenge_id, "code": first_code}
    )
    assert stale.status_code == 422
    fresh = client.post(
        "/v1/public/auth/phone/verify", json={"challengeId": challenge_id, "code": second_code}
    )
    assert fresh.status_code == 200


def test_resend_respects_cooldown(client: TestClient, sms_outbox):
    started = start(client)
    challenge_id = started.json()["challengeId"]
    blocked = client.post("/v1/public/auth/phone/resend", json={"challengeId": challenge_id})
    assert blocked.status_code == 422


def test_expired_code_is_rejected(client: TestClient, sms_outbox, db, monkeypatch):
    started = start(client)
    challenge_id = started.json()["challengeId"]
    db._conn.execute(
        "UPDATE phone_otp_challenges SET expires_at = ? WHERE id = ?",
        ("2020-01-01T00:00:00Z", challenge_id),
    )
    db._conn.commit()
    expired = client.post(
        "/v1/public/auth/phone/verify",
        json={"challengeId": challenge_id, "code": sms_outbox[-1].body},
    )
    assert expired.status_code == 422


# --- Input handling ---------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    ["9999900001", "09999900001", "+91 99999-00001", "+919999900001", "0091 9999900001"],
)
def test_phone_formats_normalise_to_one_number(client: TestClient, sms_outbox, typed: str):
    assert start(client, typed).status_code == 200
    assert sms_outbox[-1].to_e164 == PHONE_E164


@pytest.mark.parametrize("bad", ["1234567890", "98765", "notaphone", "5999900001"])
def test_invalid_numbers_are_rejected(client: TestClient, bad: str):
    assert start(client, bad).status_code == 422


# --- Attaching a number to an existing account ------------------------------


def test_attach_phone_to_existing_account(client: TestClient, sms_outbox):
    from tests.integration.test_customer_auth_api import register

    registered = register(
        client, sms_outbox, phoneVerificationToken=verify_phone_token(client, sms_outbox)
    )
    assert registered.status_code == 200

    # A different number, verified through the authenticated add-phone route.
    token = verify_phone_token(
        client,
        sms_outbox,
        phone="9999900003",
        start_path="/v1/public/auth/phone/attach/start",
    )
    attached = client.post("/v1/public/auth/phone/attach", json={"verificationToken": token})
    assert attached.status_code == 200
    assert attached.json()["customer"]["phone"] == "+919999900003"


def test_attach_requires_authentication(client: TestClient, sms_outbox):
    unauth = client.post("/v1/public/auth/phone/attach", json={"verificationToken": "nope"})
    assert unauth.status_code == 401


def test_sign_in_token_cannot_be_used_to_attach(client: TestClient, sms_outbox):
    """Purpose scoping: proof minted for signing in must not mutate an account."""
    from tests.integration.test_customer_auth_api import register

    register(client, sms_outbox, phoneVerificationToken=verify_phone_token(client, sms_outbox))
    sign_in_token = verify_phone_token(
        client, sms_outbox, phone="9999900004", start_path="/v1/public/auth/phone/start"
    )
    response = client.post(
        "/v1/public/auth/phone/attach", json={"verificationToken": sign_in_token}
    )
    assert response.status_code == 422

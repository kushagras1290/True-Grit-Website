"""Integration tests for owner credential bootstrapping and self-service password
change.

The rule these pin down: `.env` opens the owner account only until that account
has a password of its own. Once adopted, the stored password is the only one that
works — which is what makes changing it in the console revoke the old one.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.auth.passwords import hash_password
from truegrit_api.config import get_settings
from truegrit_api.platform.database import SQLiteDatabase

ENV_EMAIL = "owner-login@truegrit.test"
ENV_PASSWORD = "owner-secret"
NEW_PASSWORD = "a-far-longer-owner-password"


@pytest.fixture(autouse=True)
def _owner_env(monkeypatch: pytest.MonkeyPatch):
    """Real PBKDF2 at 600k iterations would make every sign-in here take a second;
    the hashing itself is covered by the password unit tests."""
    monkeypatch.setenv("PBKDF2_ITERATIONS", "1000")
    monkeypatch.setenv("ADMIN_LOGIN_EMAIL", ENV_EMAIL)
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", ENV_PASSWORD)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def sign_in(client: TestClient, email: str, password: str):
    """Sign in through the real endpoint and, on success, attach the CSRF
    token it returns — mirroring how a real client presents it on the next
    state-changing request."""
    response = client.post("/v1/admin/auth/login", json={"email": email, "password": password})
    if response.status_code == 200:
        client.headers["x-csrf-token"] = response.json()["csrfToken"]
    return response


def stored_hash(db: SQLiteDatabase, user_id: str) -> str | None:
    row = db._conn.execute(  # test-only direct access
        "SELECT password_hash FROM user_credentials WHERE user_id = ?", (user_id,)
    ).fetchone()
    return row["password_hash"] if row is not None else None


# --- Bootstrap adoption -----------------------------------------------------


def test_env_login_adopts_the_owner_account(client: TestClient, db: SQLiteDatabase):
    assert stored_hash(db, "usr_admin") is None

    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200

    me = client.get("/v1/admin/me").json()
    assert me["id"] == "usr_admin"
    # The seeded placeholder is gone: the account now carries the real operator's
    # address, so reset mail reaches an inbox they actually read.
    assert me["email"] == ENV_EMAIL
    assert "users.manage_roles" in me["permissions"]
    assert stored_hash(db, "usr_admin") is not None


def test_env_login_is_case_insensitive_on_email(client: TestClient):
    assert sign_in(client, ENV_EMAIL.upper(), ENV_PASSWORD).status_code == 200


def test_adopted_owner_signs_in_again_with_the_same_password(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    client.post("/v1/admin/auth/logout")
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200


def test_editing_env_password_after_adoption_does_not_authenticate(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    client.post("/v1/admin/auth/logout")

    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "a-different-env-password")
    get_settings.cache_clear()

    assert sign_in(client, ENV_EMAIL, "a-different-env-password").status_code == 401
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200


def test_clearing_the_credential_hands_the_account_back_to_env(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
):
    """The documented break-glass: delete the credential row and `.env` boots the
    account again."""
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    db._conn.execute("DELETE FROM user_credentials WHERE user_id = 'usr_admin'")
    db._conn.commit()

    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "rescue-password")
    get_settings.cache_clear()

    assert sign_in(client, ENV_EMAIL, "rescue-password").status_code == 200


def test_env_login_repairs_over_budget_owner_hash(client: TestClient, db: SQLiteDatabase):
    db._conn.execute(
        "UPDATE users SET email = ? WHERE id = 'usr_admin'",
        (ENV_EMAIL,),
    )
    db._conn.execute(
        """
        INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)
        VALUES ('usr_admin', ?, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')
        """,
        (hash_password("old-password", iterations=60_000),),
    )
    db._conn.commit()

    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    assert stored_hash(db, "usr_admin").startswith("pbkdf2_sha256$1000$")


def test_env_email_taken_by_another_account_is_refused(client: TestClient, db: SQLiteDatabase):
    """users.email is UNIQUE: adopting over a customer's address would fail
    mid-write, so login refuses instead of half-adopting."""
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_clash', ?, 'Someone Else', 'customer', 'active', '2026-07-01T00:00:00Z',"
        " '2026-07-01T00:00:00Z')",
        (ENV_EMAIL,),
    )
    db._conn.commit()

    response = sign_in(client, ENV_EMAIL, ENV_PASSWORD)
    assert response.status_code == 409
    assert "already belongs to another account" in response.json()["error"]["message"]
    assert stored_hash(db, "usr_admin") is None


def test_wrong_env_password_is_rejected(client: TestClient, db: SQLiteDatabase):
    assert sign_in(client, ENV_EMAIL, "not-the-password").status_code == 401
    assert stored_hash(db, "usr_admin") is None


def test_production_refuses_the_shipped_default_password(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("ADMIN_LOGIN_EMAIL", "admin@truegrit.test")
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "admin123")
    get_settings.cache_clear()

    assert sign_in(client, "admin@truegrit.test", "admin123").status_code == 401


# --- Changing your own password ---------------------------------------------


def change_password(client: TestClient, current: str, new: str):
    return client.post(
        "/v1/admin/auth/change-password",
        json={"currentPassword": current, "newPassword": new},
    )


def test_owner_changes_password_and_the_old_one_stops_working(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200

    assert change_password(client, ENV_PASSWORD, NEW_PASSWORD).status_code == 200

    client.post("/v1/admin/auth/logout")
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 401
    assert sign_in(client, ENV_EMAIL, NEW_PASSWORD).status_code == 200


def test_changing_password_keeps_the_caller_signed_in(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    assert change_password(client, ENV_PASSWORD, NEW_PASSWORD).status_code == 200
    assert client.get("/v1/admin/me").status_code == 200


def test_changing_password_revokes_other_sessions(client: TestClient, db: SQLiteDatabase):
    """A rotation ejects whoever prompted it — every session but the caller's."""
    other_session = create_session(db, client, "usr_admin")
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    assert change_password(client, ENV_PASSWORD, NEW_PASSWORD).status_code == 200

    client.cookies.set(SESSION_COOKIE, other_session)
    assert client.get("/v1/admin/me").status_code == 401


def test_wrong_current_password_is_rejected(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    response = change_password(client, "not-my-password", NEW_PASSWORD)
    assert response.status_code == 401

    client.post("/v1/admin/auth/logout")
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200


def test_short_new_password_is_rejected(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    response = change_password(client, ENV_PASSWORD, "short")
    assert response.status_code == 422
    assert "at least" in response.json()["error"]["message"]


def test_reusing_the_current_password_is_rejected(client: TestClient):
    assert sign_in(client, ENV_EMAIL, ENV_PASSWORD).status_code == 200
    assert change_password(client, ENV_PASSWORD, ENV_PASSWORD).status_code == 422


def test_change_password_requires_a_session(client: TestClient):
    assert change_password(client, ENV_PASSWORD, NEW_PASSWORD).status_code == 401


def test_farm_owner_can_change_their_own_password(client: TestClient):
    """No permission gate: a farm-scoped sub-admin holds no users.* permission but
    still owns their own credential."""
    assert sign_in(client, "owner@devika.test", "devikafarm1").status_code == 200
    assert change_password(client, "devikafarm1", NEW_PASSWORD).status_code == 200

    client.post("/v1/admin/auth/logout")
    assert sign_in(client, "owner@devika.test", "devikafarm1").status_code == 401
    assert sign_in(client, "owner@devika.test", NEW_PASSWORD).status_code == 200

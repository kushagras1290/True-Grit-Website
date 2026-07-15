"""Integration fixtures: the real app on a SQLite database built from the real
migrations and development seed — the same SQL D1 will run."""

from __future__ import annotations

import os
import secrets

import pytest
from fastapi.testclient import TestClient

# Existing checkout tests place large carts; keep the cash-on-delivery ceiling
# out of their way. The ceiling itself (default ₹300) is enforced in production
# and covered by dedicated checkout tests below.
os.environ.setdefault("PAYMENT_COD_MAX_MINOR", "100000000")

from truegrit_api.auth.sessions import hash_token  # noqa: E402
from truegrit_api.config import get_settings  # noqa: E402
from truegrit_api.main import create_app  # noqa: E402
from truegrit_api.platform.database import SQLiteDatabase, build_local_database  # noqa: E402

get_settings.cache_clear()

SESSION_COOKIE = "tg_session"


@pytest.fixture()
def db() -> SQLiteDatabase:
    return build_local_database()


@pytest.fixture()
def client(db: SQLiteDatabase) -> TestClient:
    return TestClient(create_app(db=db), raise_server_exceptions=False)


def create_session(db: SQLiteDatabase, user_id: str) -> str:
    """Insert a real session row and return the raw cookie token."""
    token = secrets.token_urlsafe(32)
    db._conn.execute(  # test-only direct access
        "INSERT INTO sessions (id, user_id, token_hash, csrf_secret_hash, expires_at,"
        " last_seen_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            f"ses_{secrets.token_hex(8)}",
            user_id,
            hash_token(token),
            hash_token(secrets.token_urlsafe(16)),
            "2027-01-01T00:00:00Z",
            "2026-07-11T00:00:00Z",
            "2026-07-11T00:00:00Z",
        ),
    )
    db._conn.commit()
    return token

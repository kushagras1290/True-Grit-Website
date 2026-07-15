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
from truegrit_api.services.sms import OutboundSms  # noqa: E402

get_settings.cache_clear()

SESSION_COOKIE = "tg_session"

# Any Indian mobile works; this one is in the reserved-for-fiction 99999 block.
TEST_PHONE = "9999900001"


class RecordingSmsSender:
    """Captures messages instead of sending them, so a test can read the passcode
    the customer would have received."""

    def __init__(self, outbox: list[OutboundSms]) -> None:
        self._outbox = outbox

    async def send(self, message: OutboundSms) -> None:
        self._outbox.append(message)


@pytest.fixture(autouse=True)
def sms_outbox(monkeypatch: pytest.MonkeyPatch) -> list[OutboundSms]:
    """Every test gets a recording SMS sender. Autouse so no test can reach a
    real provider by forgetting to ask for it; request it as a parameter to read
    the codes."""
    outbox: list[OutboundSms] = []
    monkeypatch.setattr(
        "truegrit_api.services.sms.get_sms_sender",
        lambda settings=None: RecordingSmsSender(outbox),
    )
    return outbox


def verify_phone_token(
    client: TestClient,
    sms_outbox: list[OutboundSms],
    *,
    phone: str = TEST_PHONE,
    start_path: str = "/v1/public/auth/phone/register/start",
) -> str:
    """Drive a real OTP round-trip and return the proof token. Uses the actual
    endpoints — a test that fakes the token would not exercise the thing most
    likely to break."""
    started = client.post(start_path, json={"phone": phone})
    assert started.status_code == 200, started.text
    challenge_id = started.json()["challengeId"]
    code = sms_outbox[-1].body
    verified = client.post(
        "/v1/public/auth/phone/verify", json={"challengeId": challenge_id, "code": code}
    )
    assert verified.status_code == 200, verified.text
    return verified.json()["verificationToken"]


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

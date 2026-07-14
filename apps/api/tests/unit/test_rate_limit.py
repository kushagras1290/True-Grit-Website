"""Unit tests for the DB-backed fixed-window rate limiter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.errors import RateLimitError
from truegrit_api.platform.database import build_local_database


def run(coro):
    return asyncio.run(coro)


class FakeRequest:
    def __init__(self, headers: dict[str, str] | None = None, host: str | None = None):
        self.headers = headers or {}
        self.client = type("Client", (), {"host": host})() if host else None


def test_allows_up_to_limit_then_blocks():
    db = build_local_database()
    rule = RateLimitRule(max_attempts=3, window_seconds=900)
    for _ in range(3):
        run(enforce_rate_limit(db, key="login:acct:x", rule=rule))
    with pytest.raises(RateLimitError):
        run(enforce_rate_limit(db, key="login:acct:x", rule=rule))


def test_window_resets_after_expiry():
    db = build_local_database()
    rule = RateLimitRule(max_attempts=2, window_seconds=60)
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    run(enforce_rate_limit(db, key="k", rule=rule, now=base))
    run(enforce_rate_limit(db, key="k", rule=rule, now=base))
    with pytest.raises(RateLimitError):
        run(enforce_rate_limit(db, key="k", rule=rule, now=base))
    # A fresh window after expiry starts the count over.
    run(enforce_rate_limit(db, key="k", rule=rule, now=base + timedelta(seconds=61)))


def test_keys_are_independent():
    db = build_local_database()
    rule = RateLimitRule(max_attempts=1, window_seconds=60)
    run(enforce_rate_limit(db, key="a", rule=rule))
    run(enforce_rate_limit(db, key="b", rule=rule))
    with pytest.raises(RateLimitError):
        run(enforce_rate_limit(db, key="a", rule=rule))


def test_zero_limit_always_blocks():
    db = build_local_database()
    with pytest.raises(RateLimitError):
        run(enforce_rate_limit(db, key="k", rule=RateLimitRule(max_attempts=0, window_seconds=60)))


def test_client_ip_prefers_cf_then_forwarded_then_peer():
    assert client_ip(FakeRequest(headers={"cf-connecting-ip": "203.0.113.9"})) == "203.0.113.9"
    assert client_ip(FakeRequest(headers={"x-forwarded-for": "198.51.100.7, 10.0.0.1"})) == (
        "198.51.100.7"
    )
    assert client_ip(FakeRequest(host="192.0.2.4")) == "192.0.2.4"
    assert client_ip(FakeRequest()) == "unknown"


def test_hash_identifier_is_stable_and_opaque():
    hashed = hash_identifier("203.0.113.9")
    assert hashed == hash_identifier("203.0.113.9")
    assert "203.0.113.9" not in hashed
    assert len(hashed) == 64

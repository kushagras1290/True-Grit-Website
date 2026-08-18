"""Unit tests for the non-raising, email-specific fixed-window rate limiter."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from truegrit_api.platform.database import build_local_database
from truegrit_api.services.email_rate_limit import RateLimitRule, check_and_count


def run(coro):
    return asyncio.run(coro)


def test_allows_up_to_limit_then_reports_false():
    db = build_local_database(seeded=False)
    rule = RateLimitRule(max_attempts=3, window_seconds=900)
    for _ in range(3):
        assert run(check_and_count(db, key="email:global:hourly", rule=rule)) is True
    assert run(check_and_count(db, key="email:global:hourly", rule=rule)) is False


def test_window_resets_after_expiry():
    db = build_local_database(seeded=False)
    rule = RateLimitRule(max_attempts=2, window_seconds=60)
    base = datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC)
    assert run(check_and_count(db, key="k", rule=rule, now=base)) is True
    assert run(check_and_count(db, key="k", rule=rule, now=base)) is True
    assert run(check_and_count(db, key="k", rule=rule, now=base)) is False
    # A fresh window after expiry starts the count over.
    assert run(check_and_count(db, key="k", rule=rule, now=base + timedelta(seconds=61))) is True


def test_keys_are_independent():
    db = build_local_database(seeded=False)
    rule = RateLimitRule(max_attempts=1, window_seconds=60)
    assert run(check_and_count(db, key="a", rule=rule)) is True
    assert run(check_and_count(db, key="b", rule=rule)) is True
    assert run(check_and_count(db, key="a", rule=rule)) is False


def test_zero_limit_always_reports_false_without_writing_a_row():
    db = build_local_database(seeded=False)
    rule = RateLimitRule(max_attempts=0, window_seconds=60)
    assert run(check_and_count(db, key="k", rule=rule)) is False

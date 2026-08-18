"""Unit tests for the single email send/skip decision point and its log."""

from __future__ import annotations

import asyncio

import pytest

from truegrit_api.auth.principal import Principal
from truegrit_api.config import Settings
from truegrit_api.platform.database import build_local_database
from truegrit_api.services.email_gate import (
    check_email_gate,
    record_email_outcome,
    send_gated_email,
)
from truegrit_api.services.email_settings import update_email_settings


def run(coro):
    return asyncio.run(coro)


def principal() -> Principal:
    # "usr_admin" is the seeded super-admin (database/seeds/development.sql) --
    # app_settings.updated_by and audit_logs.actor_user_id both FK to users,
    # so any test that actually persists an update needs a real seeded user.
    return Principal(
        user_id="usr_admin", display_name="Owner", email="owner@truegrit.test", user_type="staff"
    )


def test_enabled_category_within_limits_is_allowed():
    db = build_local_database(seeded=False)
    result = run(check_email_gate(db, "order_confirmation"))
    assert result.allowed is True
    assert result.outcome == "sent"


def test_disabled_category_is_blocked_without_touching_rate_limit():
    db = build_local_database()
    run(
        update_email_settings(
            db,
            principal(),
            "req_1",
            updates={"categories": {"order_confirmation": {"enabled": False}}},
        )
    )
    result = run(check_email_gate(db, "order_confirmation"))
    assert result.allowed is False
    assert result.outcome == "blocked_disabled"


def test_global_hourly_cap_blocks_the_next_attempt():
    db = build_local_database()
    run(update_email_settings(db, principal(), "req_1", updates={"global_hourly_limit": 1}))
    first = run(check_email_gate(db, "order_confirmation"))
    second = run(check_email_gate(db, "customer_welcome"))
    assert first.allowed is True
    assert second.allowed is False
    assert second.outcome == "rate_limited"


def test_category_override_is_independent_of_other_categories():
    db = build_local_database()
    run(
        update_email_settings(
            db,
            principal(),
            "req_1",
            updates={"categories": {"order_confirmation": {"hourly_limit": 1}}},
        )
    )
    run(check_email_gate(db, "order_confirmation"))
    capped = run(check_email_gate(db, "order_confirmation"))
    other = run(check_email_gate(db, "customer_welcome"))
    assert capped.allowed is False
    assert capped.outcome == "rate_limited"
    assert other.allowed is True


def test_record_email_outcome_stores_domain_only():
    db = build_local_database(seeded=False)
    run(
        record_email_outcome(
            db,
            category="order_confirmation",
            provider="resend",
            outcome="sent",
            recipient="customer@example.com",
        )
    )
    rows = run(db.fetch_all("SELECT recipient_domain FROM email_send_log"))
    assert len(rows) == 1
    assert rows[0]["recipient_domain"] == "example.com"


def test_send_gated_email_skips_the_provider_when_disabled(monkeypatch: pytest.MonkeyPatch):
    db = build_local_database()
    run(
        update_email_settings(
            db, principal(), "req_1", updates={"categories": {"staff_account": {"enabled": False}}}
        )
    )

    def explode(*_args: object, **_kwargs: object) -> bool:
        raise AssertionError("send_email must not be called when the category is disabled")

    monkeypatch.setattr("truegrit_api.services.email_gate.send_email", explode)
    sent = run(
        send_gated_email(
            db,
            category="staff_account",
            to="staff@example.test",
            subject="Welcome",
            body="Hi",
            settings=Settings(),
        )
    )
    assert sent is False
    rows = run(db.fetch_all("SELECT outcome FROM email_send_log"))
    assert rows[0]["outcome"] == "blocked_disabled"


def test_send_gated_email_sends_and_logs_when_allowed(monkeypatch: pytest.MonkeyPatch):
    db = build_local_database(seeded=False)
    monkeypatch.setattr("truegrit_api.services.email_gate.send_email", lambda *a, **k: True)
    sent = run(
        send_gated_email(
            db,
            category="staff_account",
            to="staff@example.test",
            subject="Welcome",
            body="Hi",
            settings=Settings(),
        )
    )
    assert sent is True
    rows = run(db.fetch_all("SELECT outcome FROM email_send_log"))
    assert rows[0]["outcome"] == "sent"

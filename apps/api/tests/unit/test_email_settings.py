"""Unit tests for admin-controlled email provider, category toggles and limits."""

from __future__ import annotations

import asyncio

import pytest

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import build_local_database
from truegrit_api.services.email_settings import (
    EMAIL_CATEGORIES,
    category_enabled,
    load_email_settings,
    preferred_provider,
    update_email_settings,
)


def run(coro):
    return asyncio.run(coro)


def principal() -> Principal:
    # "usr_admin" is the seeded super-admin (database/seeds/development.sql) --
    # app_settings.updated_by and audit_logs.actor_user_id both FK to users,
    # so any test that actually persists an update needs a real seeded user.
    return Principal(
        user_id="usr_admin", display_name="Owner", email="owner@truegrit.test", user_type="staff"
    )


def test_defaults_when_nothing_stored():
    db = build_local_database(seeded=False)
    settings = run(load_email_settings(db))
    assert settings.provider is None
    assert settings.global_hourly_limit == 300
    assert settings.global_daily_limit == 3000
    assert set(settings.category_enabled) == set(EMAIL_CATEGORIES)
    assert all(settings.category_enabled.values())
    limits = settings.category_limits.values()
    assert all(entry.hourly is None and entry.daily is None for entry in limits)


def test_category_enabled_reads_a_single_category_without_the_full_load():
    db = build_local_database(seeded=False)
    assert run(category_enabled(db, "order_confirmation")) is True


def test_update_and_reload_round_trip():
    db = build_local_database()
    actor = principal()
    run(
        update_email_settings(
            db,
            actor,
            "req_1",
            updates={
                "provider": "brevo",
                "global_hourly_limit": 50,
                "global_daily_limit": 500,
                "categories": {"order_confirmation": {"enabled": False}},
            },
        )
    )
    reloaded = run(load_email_settings(db))
    assert reloaded.provider == "brevo"
    assert reloaded.global_hourly_limit == 50
    assert reloaded.global_daily_limit == 500
    assert reloaded.category_enabled["order_confirmation"] is False
    # Untouched categories keep their default.
    assert reloaded.category_enabled["customer_welcome"] is True
    assert run(preferred_provider(db)) == "brevo"


def test_partial_update_never_touches_unlisted_fields():
    db = build_local_database()
    actor = principal()
    run(update_email_settings(db, actor, "req_1", updates={"provider": "resend"}))
    run(update_email_settings(db, actor, "req_2", updates={"global_hourly_limit": 10}))
    reloaded = run(load_email_settings(db))
    # The second update must not have reset the provider set by the first.
    assert reloaded.provider == "resend"
    assert reloaded.global_hourly_limit == 10


def test_invalid_provider_is_rejected():
    db = build_local_database(seeded=False)
    with pytest.raises(ValidationAppError):
        run(update_email_settings(db, principal(), "req_1", updates={"provider": "sendgrid"}))


def test_out_of_range_global_limit_is_rejected():
    db = build_local_database(seeded=False)
    with pytest.raises(ValidationAppError):
        run(update_email_settings(db, principal(), "req_1", updates={"global_hourly_limit": 0}))


def test_category_limit_override_can_be_set_then_cleared():
    db = build_local_database()
    actor = principal()
    run(
        update_email_settings(
            db,
            actor,
            "req_1",
            updates={"categories": {"order_confirmation": {"hourly_limit": 5, "daily_limit": 20}}},
        )
    )
    with_override = run(load_email_settings(db))
    assert with_override.category_limits["order_confirmation"].hourly == 5
    assert with_override.category_limits["order_confirmation"].daily == 20

    run(
        update_email_settings(
            db,
            actor,
            "req_2",
            updates={
                "categories": {"order_confirmation": {"hourly_limit": None, "daily_limit": None}}
            },
        )
    )
    cleared = run(load_email_settings(db))
    assert cleared.category_limits["order_confirmation"].hourly is None
    assert cleared.category_limits["order_confirmation"].daily is None


def test_unknown_category_in_update_is_silently_ignored():
    db = build_local_database(seeded=False)
    run(
        update_email_settings(
            db,
            principal(),
            "req_1",
            updates={"categories": {"not_a_real_category": {"enabled": False}}},
        )
    )
    reloaded = run(load_email_settings(db))
    assert all(reloaded.category_enabled.values())

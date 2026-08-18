from __future__ import annotations

import asyncio

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import build_local_database
from truegrit_api.services.email import OutboundEmail
from truegrit_api.services.email_settings import update_email_settings
from truegrit_api.services.jobs import (
    dispatch_pending_outbox,
    enqueue_email,
    process_queue_job,
)


def principal() -> Principal:
    # "usr_admin" is the seeded super-admin (database/seeds/development.sql) --
    # app_settings.updated_by and audit_logs.actor_user_id both FK to users,
    # so any test that actually persists an update needs a real seeded user.
    return Principal(
        user_id="usr_admin", display_name="Owner", email="owner@truegrit.test", user_type="staff"
    )


class RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)


def test_email_job_is_dispatched_and_processed_once() -> None:
    async def scenario() -> None:
        database = build_local_database(seeded=False)
        publisher = RecordingPublisher()
        await enqueue_email(
            database,
            dedupe_key="order:one:customer",
            to="customer@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="one",
            category="order_confirmation",
        )
        await enqueue_email(
            database,
            dedupe_key="order:one:customer",
            to="customer@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="one",
            category="order_confirmation",
        )

        result = await dispatch_pending_outbox(database, publisher)
        delivered: list[OutboundEmail] = []

        def deliver(email: OutboundEmail, idempotency_key: str, category: str) -> bool:
            delivered.append(email)
            assert idempotency_key.startswith("evt_")
            assert category == "order_confirmation"
            return True

        first = await process_queue_job(database, publisher.messages[0], deliver_email=deliver)
        second = await process_queue_job(database, publisher.messages[0], deliver_email=deliver)

        assert result == {
            "selected": 1,
            "published": 1,
            "failed": 0,
            "blocked": 0,
            "rateLimited": 0,
        }
        assert first == "processed"
        assert second == "duplicate"
        assert [email.to for email in delivered] == ["customer@example.test"]

    asyncio.run(scenario())


def test_dispatch_marks_a_disabled_category_failed_without_publishing() -> None:
    async def scenario() -> None:
        database = build_local_database()
        await update_email_settings(
            database,
            principal(),
            "req_1",
            updates={"categories": {"order_confirmation": {"enabled": False}}},
        )
        await enqueue_email(
            database,
            dedupe_key="order:two:customer",
            to="customer@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="two",
            category="order_confirmation",
        )
        publisher = RecordingPublisher()

        result = await dispatch_pending_outbox(database, publisher)

        assert result["published"] == 0
        assert result["blocked"] == 1
        assert publisher.messages == []
        row = await database.fetch_one("SELECT status, attempt_count FROM outbox_events")
        assert row["status"] == "failed"
        assert row["attempt_count"] == 1
        log_row = await database.fetch_one("SELECT outcome FROM email_send_log")
        assert log_row["outcome"] == "blocked_disabled"

    asyncio.run(scenario())


def test_dispatch_defers_a_rate_limited_row_without_burning_attempts() -> None:
    async def scenario() -> None:
        database = build_local_database()
        await update_email_settings(
            database, principal(), "req_1", updates={"global_hourly_limit": 1}
        )
        await enqueue_email(
            database,
            dedupe_key="order:three:customer",
            to="first@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="three",
            category="order_confirmation",
        )
        await enqueue_email(
            database,
            dedupe_key="order:four:customer",
            to="second@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="four",
            category="order_confirmation",
        )
        publisher = RecordingPublisher()

        result = await dispatch_pending_outbox(database, publisher)

        assert result["published"] == 1
        assert result["rateLimited"] == 1
        deferred = await database.fetch_one(
            "SELECT status, attempt_count, available_at FROM outbox_events"
            " WHERE aggregate_id = 'four'"
        )
        assert deferred["status"] == "pending"
        # A throttle is not a delivery failure -- it must not consume the
        # row's retry budget on the way to the dead-letter queue.
        assert deferred["attempt_count"] == 0
        assert deferred["available_at"] > "2026-01-01T00:00:00Z"

    asyncio.run(scenario())

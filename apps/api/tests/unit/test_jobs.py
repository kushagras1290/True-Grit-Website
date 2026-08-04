from __future__ import annotations

import asyncio

from truegrit_api.platform.database import build_local_database
from truegrit_api.services.email import OutboundEmail
from truegrit_api.services.jobs import (
    dispatch_pending_outbox,
    enqueue_email,
    process_queue_job,
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
        )
        await enqueue_email(
            database,
            dedupe_key="order:one:customer",
            to="customer@example.test",
            subject="Order confirmed",
            body="Thanks",
            aggregate_type="order",
            aggregate_id="one",
        )

        result = await dispatch_pending_outbox(database, publisher)
        delivered: list[OutboundEmail] = []

        def deliver(email: OutboundEmail, idempotency_key: str) -> bool:
            delivered.append(email)
            assert idempotency_key.startswith("evt_")
            return True

        first = await process_queue_job(database, publisher.messages[0], deliver_email=deliver)
        second = await process_queue_job(database, publisher.messages[0], deliver_email=deliver)

        assert result == {"selected": 1, "published": 1, "failed": 0}
        assert first == "processed"
        assert second == "duplicate"
        assert [email.to for email in delivered] == ["customer@example.test"]

    asyncio.run(scenario())

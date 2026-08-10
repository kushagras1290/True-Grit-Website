"""Transactional outbox dispatch and idempotent queue job processing."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol

from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.email import OutboundEmail, send_email
from truegrit_api.util.timeutil import utc_now_iso

_EMAIL_EVENT = "notification.email.v1"
_MAX_DISPATCH_ATTEMPTS = 10
_MAX_BATCH_SIZE = 50
_MAX_EMAIL_FIELD = 200_000


class QueuePublisher(Protocol):
    async def send(self, message: Mapping[str, Any]) -> None: ...


class RetryableJobError(RuntimeError):
    """A job failed without completing its externally visible side effect."""


def _event_id(dedupe_key: str) -> str:
    digest = hashlib.sha256(dedupe_key.encode("utf-8")).hexdigest()[:32]
    return f"evt_{digest}"


async def enqueue_email(
    db: Database,
    *,
    dedupe_key: str,
    to: str,
    subject: str,
    body: str,
    html_body: str | None = None,
    aggregate_type: str,
    aggregate_id: str,
) -> str:
    """Persist one email job; repeating the same business event is a no-op."""
    event_id = _event_id(f"email:{dedupe_key}")
    now = utc_now_iso()
    payload = json.dumps(
        {"to": to, "subject": subject, "body": body, "htmlBody": html_body},
        separators=(",", ":"),
    )
    await db.execute(
        """
        INSERT OR IGNORE INTO outbox_events
          (id, event_type, event_version, aggregate_type, aggregate_id,
           payload_json, status, available_at, created_at)
        VALUES (?, ?, 1, ?, ?, ?, 'pending', ?, ?)
        """,
        (event_id, _EMAIL_EVENT, aggregate_type, aggregate_id, payload, now, now),
    )
    return event_id


def _retry_at(attempt_count: int) -> str:
    delay_seconds = min(300, 2 ** min(attempt_count, 8))
    return (datetime.now(UTC) + timedelta(seconds=delay_seconds)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def dispatch_pending_outbox(
    db: Database,
    publisher: QueuePublisher,
    *,
    limit: int = _MAX_BATCH_SIZE,
) -> dict[str, int]:
    """Publish pending rows; duplicates are safe because event IDs are stable."""
    bounded_limit = max(1, min(limit, _MAX_BATCH_SIZE))
    rows = await db.fetch_all(
        """
        SELECT id, event_type, event_version, aggregate_type, aggregate_id,
               payload_json, attempt_count, created_at
        FROM outbox_events
        WHERE status = 'pending' AND available_at <= ? AND attempt_count < ?
        ORDER BY available_at, created_at
        LIMIT ?
        """,
        (utc_now_iso(), _MAX_DISPATCH_ATTEMPTS, bounded_limit),
    )
    published = 0
    failed = 0
    for row in rows:
        message = {
            "idempotencyKey": row["id"],
            "eventType": row["event_type"],
            "eventVersion": row["event_version"],
            "aggregateType": row["aggregate_type"],
            "aggregateId": row["aggregate_id"],
            "payload": json.loads(row["payload_json"]),
            "createdAt": row["created_at"],
        }
        try:
            await publisher.send(message)
        except Exception as exc:
            attempt_count = int(row["attempt_count"]) + 1
            status = "failed" if attempt_count >= _MAX_DISPATCH_ATTEMPTS else "pending"
            await db.execute(
                """
                UPDATE outbox_events
                SET status = ?, attempt_count = ?, available_at = ?
                WHERE id = ? AND status = 'pending'
                """,
                (status, attempt_count, _retry_at(attempt_count), row["id"]),
            )
            log_event(
                "error",
                "outbox_publish_failed",
                event_id=row["id"],
                event_type=row["event_type"],
                attempt_count=attempt_count,
                error_type=type(exc).__name__,
            )
            failed += 1
            continue
        await db.execute(
            """
            UPDATE outbox_events
            SET status = 'published', attempt_count = attempt_count + 1, published_at = ?
            WHERE id = ? AND status = 'pending'
            """,
            (utc_now_iso(), row["id"]),
        )
        published += 1
    return {"selected": len(rows), "published": published, "failed": failed}


def _required_string(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > _MAX_EMAIL_FIELD:
        raise ValueError(f"Queue email field {key!r} is invalid.")
    return value


async def process_queue_job(
    db: Database,
    message: Mapping[str, Any],
    *,
    deliver_email: Callable[[OutboundEmail, str], bool | Awaitable[bool]] | None = None,
    invalidate_cache: Callable[[str, str], Awaitable[None]] | None = None,
    translate_task: Callable[[str], Awaitable[None]] | None = None,
) -> str:
    """Process one at-least-once queue delivery exactly once by idempotency key."""
    idempotency_key = _required_string(message, "idempotencyKey")
    event_type = _required_string(message, "eventType")
    existing = await db.fetch_one(
        "SELECT idempotency_key FROM processed_queue_messages WHERE idempotency_key = ?",
        (idempotency_key,),
    )
    if existing is not None:
        return "duplicate"

    payload = message.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("Queue job payload must be an object.")

    if event_type == _EMAIL_EVENT:
        html_value = payload.get("htmlBody")
        if html_value is not None and not isinstance(html_value, str):
            raise ValueError("Queue email htmlBody must be a string or null.")
        email = OutboundEmail(
            to=_required_string(payload, "to"),
            subject=_required_string(payload, "subject"),
            body=_required_string(payload, "body"),
            html_body=html_value,
        )
        sender = deliver_email or (
            lambda value, _key: send_email(
                value.to, value.subject, value.body, html_body=value.html_body
            )
        )
        delivery_result = sender(email, idempotency_key)
        accepted = (
            await delivery_result if inspect.isawaitable(delivery_result) else delivery_result
        )
        if not accepted:
            raise RetryableJobError("Email provider did not accept the message.")
    elif event_type.startswith("content."):
        if invalidate_cache is not None:
            await invalidate_cache(
                str(message.get("aggregateType") or "content"),
                str(message.get("aggregateId") or "all"),
            )
    elif event_type == "translation.batch-task.v1":
        if translate_task is None:
            raise RetryableJobError("Translation worker is not configured.")
        await translate_task(_required_string(payload, "taskId"))
    else:
        raise ValueError(f"Unsupported queue event type: {event_type}")

    await db.execute(
        """
        INSERT OR IGNORE INTO processed_queue_messages
          (idempotency_key, event_type, completed_at)
        VALUES (?, ?, ?)
        """,
        (idempotency_key, event_type, utc_now_iso()),
    )
    return "processed"


async def retain_dead_letter(db: Database, message: Mapping[str, Any], error: str) -> None:
    """Copy a poison message to D1 before acknowledging its DLQ delivery."""
    event_id = str(message.get("idempotencyKey") or "unknown")
    event_type = str(message.get("eventType") or "unknown")
    failure_id = _event_id(f"dead-letter:{event_id}")
    await db.execute(
        """
        INSERT OR IGNORE INTO job_failures
          (id, queue_name, event_type, event_id, payload_json, error_code,
           error_summary, attempt_count, failed_at)
        VALUES (?, 'truegrit-dlq', ?, ?, ?, 'retries_exhausted', ?, 1, ?)
        """,
        (
            failure_id,
            event_type,
            event_id,
            json.dumps(dict(message), default=str, separators=(",", ":")),
            error[:500],
            utc_now_iso(),
        ),
    )

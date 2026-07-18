"""Persists severe log events to the `application_logs` table.

`truegrit_api.logging.log_event()` writes every event to stdout only — that
covers Cloudflare's own log tailing. This module additionally persists the
rare, high-signal subset (5xx `AppError`s and unhandled exceptions, wired up
in `middleware/error_handler.py`) so the owner-only Server Logs admin page has
something queryable. It is deliberately not called from every log_event()
site: that would add a DB write to every request for events nobody reviews.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from truegrit_api.logging import redact_fields
from truegrit_api.platform.database import Database
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_RETENTION_DAYS = 30

_INSERT_SQL = (
    "INSERT INTO application_logs (id, level, event, fields_json, created_at)"
    " VALUES (?, ?, ?, ?, ?)"
)
_PRUNE_SQL = "DELETE FROM application_logs WHERE created_at < ?"


def _retention_cutoff(now: datetime) -> str:
    return (now - timedelta(days=_RETENTION_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def persist_log(db: Database, level: str, event: str, /, **fields: Any) -> None:
    """Insert one row and prune anything past the retention window in the same
    batch, so a burst of errors can never grow this table unbounded."""
    created_at = utc_now_iso()
    cutoff = _retention_cutoff(datetime.now(UTC))
    safe_fields = redact_fields(fields)
    await db.batch(
        [
            (
                _INSERT_SQL,
                (new_id("log"), level, event, json.dumps(safe_fields, default=str), created_at),
            ),
            (_PRUNE_SQL, (cutoff,)),
        ]
    )

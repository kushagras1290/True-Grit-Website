"""Shared audit-log statement builder.

Every sensitive admin mutation records who did what, to which entity, with a
before/after summary and the request id — appended in the SAME batch as the
mutation so a change can never land without its audit trail.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from truegrit_api.util.ids import new_id

_AUDIT_SQL = (
    "INSERT INTO audit_logs"
    " (id, actor_user_id, action, entity_type, entity_id,"
    "  before_summary_json, after_summary_json, request_id, source, created_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


def audit_statement(
    *,
    action: str,
    entity_type: str,
    entity_id: str,
    actor_id: str,
    request_id: str,
    created_at: str,
    source: str = "admin",
    before: Any = None,
    after: Any = None,
) -> tuple[str, Sequence[Any]]:
    """Build a (sql, params) tuple for an audit row, ready to include in db.batch."""
    return (
        _AUDIT_SQL,
        (
            new_id("aud"),
            actor_id,
            action,
            entity_type,
            entity_id,
            json.dumps(before) if before is not None else None,
            json.dumps(after) if after is not None else None,
            request_id,
            source,
            created_at,
        ),
    )

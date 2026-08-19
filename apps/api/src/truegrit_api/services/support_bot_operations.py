"""Operator surface for the deterministic storefront bot: the policy facts it
answers from, and the queue of conversations it handed to a person.

Both tables are created in migration 0109 and both are gated on the existing
`support_bot.manage` permission -- the same operator responsibility as the
knowledge base, so no new permission is introduced.

**Policy facts are the bot's only configurable truth.** They seed blank on
purpose: a template that needs an unset fact refuses to render and the question
escalates, rather than the bot stating a return window nobody entered. That
makes this screen the difference between a bot that answers policy questions
and one that quietly forwards all of them, so `list_facts` reports
`isConfigured` per row and the admin UI can say which are still empty.

**Escalations are the feedback loop.** The queue is the work list, but the
`alternatives_json` on each row is the more valuable half: it records what the
classifier nearly matched, which is exactly the phrasing that should be added
to `support_bot/phrasebook.py`. `intent_summary` aggregates that into "these
intents keep escalating", which is the report worth acting on.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

EscalationStatus = Literal["open", "in_progress", "resolved", "dismissed"]

_MAX_FACT_LENGTH = 200
_MAX_NOTE_LENGTH = 2000
_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 200

# Sorted so the queue reads worst-first. SQLite has no enum ordering, so the
# severity ranking is expressed in SQL rather than assumed from the string.
_SEVERITY_ORDER = "CASE severity WHEN 'critical' THEN 0 WHEN 'high' THEN 1 ELSE 2 END"


# --- Policy facts -----------------------------------------------------------


async def list_facts(db: Database) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT key, value, label, hint, updated_at FROM support_bot_policy_facts"
        " ORDER BY sort_order, key"
    )
    return [
        {
            "key": row["key"],
            "value": row["value"] or "",
            "label": row["label"],
            "hint": row["hint"],
            # The UI's cue for "this answer is currently switched off".
            "isConfigured": bool(str(row["value"] or "").strip()),
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


async def set_fact(
    db: Database, actor: Principal, request_id: str, key: str, value: str
) -> dict[str, Any]:
    """Set one fact. Blanking it is allowed and switches the richer wording back
    off, which is the correct way to retract a policy figure that has changed
    and not yet been replaced."""
    cleaned = value.strip()
    if len(cleaned) > _MAX_FACT_LENGTH:
        raise ValidationAppError(f"Value must be {_MAX_FACT_LENGTH} characters or fewer.")
    existing = await db.fetch_one(
        "SELECT key, value FROM support_bot_policy_facts WHERE key = ?", (key,)
    )
    if existing is None:
        # Keys are seeded by migration, never created here: a template can only
        # read a fact it names, so an arbitrary new key would be dead data.
        raise NotFoundError("No such policy fact.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE support_bot_policy_facts SET value = ?, updated_at = ?, updated_by = ?"
                " WHERE key = ?",
                (cleaned, now, actor.user_id, key),
            ),
            audit_statement(
                action="support_bot.policy_fact_changed",
                entity_type="support_bot_policy_fact",
                entity_id=key,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"value": existing["value"] or ""},
                after={"value": cleaned},
            ),
        ]
    )
    return {"key": key, "value": cleaned, "isConfigured": bool(cleaned)}


# --- Escalation queue -------------------------------------------------------


def _row_to_escalation(row: dict[str, Any]) -> dict[str, Any]:
    def parsed(column: str) -> Any:
        raw = row.get(column)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except ValueError:
            # Stored JSON is truncated to a size cap on write, so a very long
            # payload can be cut mid-token. That is worth surfacing as absent
            # rather than failing the whole queue listing.
            return None

    return {
        "id": row["id"],
        "createdAt": row["created_at"],
        "customerUserId": row["customer_user_id"],
        "requestId": row["request_id"],
        "message": row["message"],
        "intent": row["intent"],
        "confidence": row["confidence"],
        "tier": row["tier"],
        "reason": row["reason"],
        "severity": row["severity"],
        "status": row["status"],
        "alternatives": parsed("alternatives_json") or [],
        "slots": parsed("slots_json") or {},
        "context": parsed("context_json") or {},
        "resolvedAt": row["resolved_at"],
        "resolutionNote": row["resolution_note"],
    }


async def list_escalations(
    db: Database,
    *,
    status: EscalationStatus | None = "open",
    severity: str | None = None,
    limit: int = _DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> dict[str, Any]:
    """The queue, worst-first then oldest-first."""
    limit = max(1, min(_MAX_PAGE_SIZE, limit))
    offset = max(0, offset)

    conditions: list[str] = []
    params: list[Any] = []
    if status is not None:
        conditions.append("status = ?")
        params.append(status)
    if severity is not None:
        conditions.append("severity = ?")
        params.append(severity)
    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""

    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS total FROM support_bot_escalations{where}", tuple(params)
    )
    rows = await db.fetch_all(
        f"""
        SELECT id, created_at, customer_user_id, request_id, message, intent, confidence,
               tier, reason, severity, status, alternatives_json, slots_json, context_json,
               resolved_at, resolution_note
        FROM support_bot_escalations{where}
        ORDER BY {_SEVERITY_ORDER}, created_at
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "total": int(total_row["total"]) if total_row else 0,
        "items": [_row_to_escalation(row) for row in rows],
    }


async def intent_summary(db: Database, *, limit: int = 20) -> list[dict[str, Any]]:
    """Which intents escalate most, and how confident the bot was when they did.

    This is the report that tells an operator what to fix. A high count with a
    *low* average confidence means the phrasebook is missing those phrasings. A
    high count at high confidence means the intent is one that escalates by
    policy, and no phrasing will change that.
    """
    rows = await db.fetch_all(
        """
        SELECT intent, reason, COUNT(*) AS count, AVG(confidence) AS average_confidence,
               MAX(created_at) AS last_seen
        FROM support_bot_escalations
        GROUP BY intent, reason
        ORDER BY count DESC, intent
        LIMIT ?
        """,
        (max(1, min(_MAX_PAGE_SIZE, limit)),),
    )
    return [
        {
            "intent": row["intent"],
            "reason": row["reason"],
            "count": int(row["count"]),
            "averageConfidence": round(float(row["average_confidence"] or 0.0), 4),
            "lastSeen": row["last_seen"],
        }
        for row in rows
    ]


async def set_escalation_status(
    db: Database,
    actor: Principal,
    request_id: str,
    escalation_id: str,
    *,
    status: EscalationStatus,
    note: str = "",
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT id, status FROM support_bot_escalations WHERE id = ?", (escalation_id,)
    )
    if existing is None:
        raise NotFoundError("Escalation not found.")
    cleaned_note = note.strip()[:_MAX_NOTE_LENGTH]
    now = utc_now_iso()
    # `resolved_at` marks when it stopped needing attention, so it is set for
    # dismissed as well as resolved and cleared if the row is reopened.
    finished = status in ("resolved", "dismissed")

    await db.batch(
        [
            (
                "UPDATE support_bot_escalations"
                " SET status = ?, resolved_at = ?, resolved_by = ?, resolution_note = ?"
                " WHERE id = ?",
                (
                    status,
                    now if finished else None,
                    actor.user_id if finished else None,
                    cleaned_note or None,
                    escalation_id,
                ),
            ),
            audit_statement(
                action="support_bot.escalation_status_changed",
                entity_type="support_bot_escalation",
                entity_id=escalation_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": existing["status"]},
                after={"status": status},
            ),
        ]
    )
    return {"id": escalation_id, "status": status, "resolutionNote": cleaned_note}

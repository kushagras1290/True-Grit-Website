"""Community discussions: signed-in customers open a thread and comment.

Anyone signed in may comment on a visible discussion. Starting a new
discussion additionally requires an account at least
`discussions.min_account_age_months` old (`app_settings`, admin-editable,
default 6 -- see `get_min_account_age_months`/`set_min_account_age_months`),
so the first voices shaping the community are established customers rather
than throwaway accounts. Staff with `discussions.moderate` (checked by the
route, not here -- see `services.returns` for the same split) can hide,
archive, restore or permanently delete any thread or comment.
"""

from __future__ import annotations

import calendar
from datetime import UTC, datetime
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MIN_ACCOUNT_AGE_KEY = "discussions.min_account_age_months"
_DEFAULT_MIN_ACCOUNT_AGE_MONTHS = 6
_MAX_MIN_ACCOUNT_AGE_MONTHS = 120
_MIN_TITLE = 5
_MAX_TITLE = 200
_MIN_BODY = 20
_MAX_BODY = 10_000
_MIN_COMMENT = 2
_MAX_COMMENT = 4_000

_DISCUSSION_MODERATION_ACTIONS = {
    "hide": "hidden",
    "restore": "visible",
    "archive": "archived",
    "remove": "removed",
}
_COMMENT_MODERATION_ACTIONS = {"hide": "hidden", "restore": "visible", "remove": "removed"}


def _months_ago(now: datetime, months: int) -> datetime:
    """Calendar-accurate month subtraction (stdlib only): day-of-month is
    clamped to the target month's last valid day, e.g. Mar 31 minus 1 month
    lands on Feb 28/29 rather than overflowing into March."""
    month_index = now.month - 1 - months
    year = now.year + month_index // 12
    month = month_index % 12 + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


async def get_min_account_age_months(db: Database) -> int:
    row = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = ?", (_MIN_ACCOUNT_AGE_KEY,)
    )
    if row is None:
        return _DEFAULT_MIN_ACCOUNT_AGE_MONTHS
    try:
        return max(0, int(row["value"]))
    except (TypeError, ValueError):
        return _DEFAULT_MIN_ACCOUNT_AGE_MONTHS


async def set_min_account_age_months(
    db: Database, actor: Principal, request_id: str, months: int
) -> dict[str, Any]:
    if months < 0 or months > _MAX_MIN_ACCOUNT_AGE_MONTHS:
        raise ValidationAppError(
            f"Enter a value between 0 and {_MAX_MIN_ACCOUNT_AGE_MONTHS} months."
        )
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (_MIN_ACCOUNT_AGE_KEY, str(months), now, actor.user_id),
            ),
            audit_statement(
                action="settings.community_updated",
                entity_type="app_setting",
                entity_id=_MIN_ACCOUNT_AGE_KEY,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"minAccountAgeMonths": months},
            ),
        ]
    )
    return {"minAccountAgeMonths": months}


async def assert_can_start_discussion(db: Database, customer: Principal) -> None:
    user = await db.fetch_one("SELECT created_at FROM users WHERE id = ?", (customer.user_id,))
    if user is None:
        raise NotFoundError("Account not found.")
    months = await get_min_account_age_months(db)
    if months <= 0:
        return
    created_at = datetime.strptime(user["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    cutoff = _months_ago(datetime.now(UTC), months)
    if created_at > cutoff:
        plural = "" if months == 1 else "s"
        raise PermissionDeniedError(
            f"Starting a discussion needs an account at least {months} month{plural} old."
        )


async def create_discussion(
    db: Database, customer: Principal, request_id: str, *, title: str, body: str
) -> dict[str, Any]:
    title = title.strip()
    body = body.strip()
    if len(title) < _MIN_TITLE or len(title) > _MAX_TITLE:
        raise ValidationAppError(f"Title must be between {_MIN_TITLE} and {_MAX_TITLE} characters.")
    if len(body) < _MIN_BODY or len(body) > _MAX_BODY:
        raise ValidationAppError(f"Write between {_MIN_BODY} and {_MAX_BODY} characters.")
    await assert_can_start_discussion(db, customer)

    now = utc_now_iso()
    discussion_id = new_id("dsc")
    await db.batch(
        [
            (
                "INSERT INTO discussions"
                " (id, author_user_id, title, body, status, comment_count, last_activity_at,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'visible', 0, ?, ?, ?)",
                (discussion_id, customer.user_id, title, body, now, now, now),
            ),
            audit_statement(
                action="discussion.created",
                entity_type="discussion",
                entity_id=discussion_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"title": title},
            ),
        ]
    )
    return {"id": discussion_id, "status": "visible"}


async def create_comment(
    db: Database, customer: Principal, request_id: str, discussion_id: str, *, body: str
) -> dict[str, Any]:
    body = body.strip()
    if len(body) < _MIN_COMMENT or len(body) > _MAX_COMMENT:
        raise ValidationAppError(
            f"Comments must be between {_MIN_COMMENT} and {_MAX_COMMENT} characters."
        )
    discussion = await db.fetch_one(
        "SELECT id, status FROM discussions WHERE id = ?", (discussion_id,)
    )
    if discussion is None or discussion["status"] == "removed":
        raise NotFoundError("Discussion not found.")
    if discussion["status"] != "visible":
        raise ConflictError("This discussion is not open for comments.")

    now = utc_now_iso()
    comment_id = new_id("cmt")
    await db.batch(
        [
            (
                "INSERT INTO discussion_comments"
                " (id, discussion_id, author_user_id, body, status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'visible', ?, ?)",
                (comment_id, discussion_id, customer.user_id, body, now, now),
            ),
            (
                "UPDATE discussions SET comment_count = comment_count + 1, last_activity_at = ?,"
                " updated_at = ? WHERE id = ?",
                (now, now, discussion_id),
            ),
            audit_statement(
                action="discussion_comment.created",
                entity_type="discussion_comment",
                entity_id=comment_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"discussionId": discussion_id},
            ),
        ]
    )
    return {"id": comment_id, "status": "visible"}


async def moderate_discussion(
    db: Database,
    actor: Principal,
    request_id: str,
    discussion_id: str,
    *,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    target = _DISCUSSION_MODERATION_ACTIONS.get(action)
    if target is None:
        raise ValidationAppError("Unsupported moderation action.")
    current = await db.fetch_one("SELECT * FROM discussions WHERE id = ?", (discussion_id,))
    if current is None:
        raise NotFoundError("Discussion not found.")
    reason = (reason or "").strip()[:500] or None

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE discussions SET status = ?, moderated_by = ?, moderated_at = ?,"
                " moderation_reason = ?, updated_at = ? WHERE id = ?",
                (target, actor.user_id, now, reason, now, discussion_id),
            ),
            audit_statement(
                action=f"discussion.{action}",
                entity_type="discussion",
                entity_id=discussion_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": target, "reason": reason},
            ),
        ]
    )
    return {"id": discussion_id, "status": target}


async def delete_discussion(
    db: Database, actor: Principal, request_id: str, discussion_id: str
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT id FROM discussions WHERE id = ?", (discussion_id,))
    if current is None:
        raise NotFoundError("Discussion not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM discussions WHERE id = ?", (discussion_id,)),
            audit_statement(
                action="discussion.deleted",
                entity_type="discussion",
                entity_id=discussion_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": discussion_id, "deleted": True}


async def moderate_comment(
    db: Database,
    actor: Principal,
    request_id: str,
    comment_id: str,
    *,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    target = _COMMENT_MODERATION_ACTIONS.get(action)
    if target is None:
        raise ValidationAppError("Unsupported moderation action.")
    current = await db.fetch_one("SELECT * FROM discussion_comments WHERE id = ?", (comment_id,))
    if current is None:
        raise NotFoundError("Comment not found.")
    reason = (reason or "").strip()[:500] or None

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE discussion_comments SET status = ?, moderated_by = ?, moderated_at = ?,"
                " moderation_reason = ?, updated_at = ? WHERE id = ?",
                (target, actor.user_id, now, reason, now, comment_id),
            ),
            audit_statement(
                action=f"discussion_comment.{action}",
                entity_type="discussion_comment",
                entity_id=comment_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": target, "reason": reason},
            ),
        ]
    )
    return {"id": comment_id, "status": target}


async def delete_comment(
    db: Database, actor: Principal, request_id: str, comment_id: str
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id, discussion_id FROM discussion_comments WHERE id = ?", (comment_id,)
    )
    if current is None:
        raise NotFoundError("Comment not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM discussion_comments WHERE id = ?", (comment_id,)),
            (
                "UPDATE discussions SET comment_count = MAX(0, comment_count - 1), updated_at = ?"
                " WHERE id = ?",
                (now, current["discussion_id"]),
            ),
            audit_statement(
                action="discussion_comment.deleted",
                entity_type="discussion_comment",
                entity_id=comment_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": comment_id, "deleted": True}

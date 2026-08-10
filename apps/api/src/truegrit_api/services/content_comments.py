"""Reader comments on published blog posts and recipes.

Reads are public; writing requires a signed-in customer, the same "public read,
authenticated write" split the rest of the storefront uses. Staff with
`discussions.moderate` hide, restore or permanently delete any comment -- see
migration 0043 for why this shares the discussions permission rather than
minting a second one.

Two invariants are enforced here rather than left to the caller:

* **Only published content accepts comments.** A comment on a draft would
  become visible the moment the draft was published, with no editor having seen
  it, so the parent's `status` is checked on every write.
* **The discriminator and the foreign key always agree.** `content_type` and
  the article/recipe id are resolved together by `_resolve_parent`, so no code
  path can construct the pair by hand and drift from the CHECK constraint.
"""

from __future__ import annotations

from typing import Any, Final

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

ENABLED_SETTING_KEY: Final = "content_comments.enabled"

# Matches migration 0043: a missing or unparseable row resolves to the
# permissive value, so a corrupted settings table degrades to the shipped
# behaviour rather than silently closing every comment thread.
_ENABLED_DEFAULT: Final = True
_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})

CONTENT_TYPES: Final = frozenset({"article", "recipe"})

_MIN_BODY: Final = 2
_MAX_BODY: Final = 4000
_MAX_REASON: Final = 500

_MODERATION_ACTIONS: Final[dict[str, str]] = {
    "hide": "hidden",
    "restore": "visible",
    "remove": "removed",
}


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


async def is_enabled(db: Database) -> bool:
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (ENABLED_SETTING_KEY,))
    return _parse_bool(row["value"] if row else None, default=_ENABLED_DEFAULT)


async def set_enabled(
    db: Database, actor: Principal, request_id: str, *, enabled: bool
) -> dict[str, Any]:
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                "  updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (ENABLED_SETTING_KEY, "1" if enabled else "0", now, actor.user_id),
            ),
            audit_statement(
                action="settings.content_comments_updated",
                entity_type="app_setting",
                entity_id=ENABLED_SETTING_KEY,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"enabled": enabled},
            ),
        ]
    )
    return {"enabled": enabled}


def _assert_content_type(content_type: str) -> str:
    if content_type not in CONTENT_TYPES:
        raise NotFoundError("Content not found.")
    return content_type


async def _resolve_parent(db: Database, content_type: str, slug: str) -> dict[str, Any]:
    """The published article or recipe behind `slug`, or 404.

    Returns `{"id", "title", "column"}` where `column` is the foreign-key column
    to populate. Resolving the column here — rather than at each call site — is
    what keeps `content_type` and the id in agreement with the CHECK constraint
    in migration 0043.
    """
    _assert_content_type(content_type)
    table = "articles" if content_type == "article" else "recipes"
    row = await db.fetch_one(f"SELECT id, title, status FROM {table} WHERE slug = ?", (slug,))
    # Articles and recipes carry their whole lifecycle in `status` — there is no
    # separate `archived_at` column here as there is on products — so
    # 'published' is the single condition, and 'unpublished' and 'archived' fall
    # out of it for free.
    if row is None or row["status"] != "published":
        raise NotFoundError("Content not found.")
    return {
        "id": row["id"],
        "title": row["title"],
        "column": "article_id" if content_type == "article" else "recipe_id",
    }


async def list_public_comments(
    db: Database, content_type: str, slug: str, *, locale: str | None = None
) -> list[dict[str, Any]]:
    """Visible comments for one post, oldest first — how a conversation reads."""
    parent = await _resolve_parent(db, content_type, slug)
    rows = await db.fetch_all(
        f"""
        SELECT c.id, c.body, c.created_at, u.display_name AS author_name
        FROM content_comments c
        JOIN users u ON u.id = c.author_user_id
        WHERE c.{parent["column"]} = ? AND c.status = 'visible'
        ORDER BY c.created_at ASC
        """,
        (parent["id"],),
    )
    if locale and locale != "en":
        from truegrit_api.services.translation_hub import override_map

        for row in rows:
            fields = await override_map(db, "content_comment", row["id"], locale)
            row["body"] = fields.get("body") or row["body"]
    return [
        {
            "id": row["id"],
            "body": row["body"],
            "authorName": row["author_name"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


async def create_comment(
    db: Database,
    customer: Principal,
    request_id: str,
    content_type: str,
    slug: str,
    *,
    body: str,
) -> dict[str, Any]:
    """Post one comment against a published article or recipe."""
    if not await is_enabled(db):
        raise PermissionDeniedError("Comments are closed at the moment.")
    text = (body or "").strip()
    if len(text) < _MIN_BODY or len(text) > _MAX_BODY:
        raise ValidationAppError(
            f"Comments must be between {_MIN_BODY} and {_MAX_BODY} characters."
        )
    parent = await _resolve_parent(db, content_type, slug)

    now = utc_now_iso()
    comment_id = new_id("ccm")
    article_id = parent["id"] if content_type == "article" else None
    recipe_id = parent["id"] if content_type == "recipe" else None
    await db.batch(
        [
            (
                "INSERT INTO content_comments"
                " (id, content_type, article_id, recipe_id, author_user_id, body, status,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, 'visible', ?, ?)",
                (
                    comment_id,
                    content_type,
                    article_id,
                    recipe_id,
                    customer.user_id,
                    text,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="content_comment.created",
                entity_type="content_comment",
                entity_id=comment_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"contentType": content_type, "slug": slug},
            ),
        ]
    )
    return {"id": comment_id, "status": "visible"}


async def moderate_comment(
    db: Database,
    actor: Principal,
    request_id: str,
    comment_id: str,
    *,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Hide, restore or soft-remove one comment. Reversible; the reason and the
    moderator stay on the row so a decision can be explained later."""
    target = _MODERATION_ACTIONS.get(action)
    if target is None:
        raise ValidationAppError("Unsupported moderation action.")
    current = await db.fetch_one("SELECT * FROM content_comments WHERE id = ?", (comment_id,))
    if current is None:
        raise NotFoundError("Comment not found.")
    if current["status"] == target:
        raise ConflictError(f"This comment is already {target}.")
    reason = (reason or "").strip()[:_MAX_REASON] or None

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE content_comments SET status = ?, moderated_by = ?, moderated_at = ?,"
                " moderation_reason = ?, updated_at = ? WHERE id = ?",
                (target, actor.user_id, now, reason, now, comment_id),
            ),
            audit_statement(
                action=f"content_comment.{action}",
                entity_type="content_comment",
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
    """Permanent removal. `moderate_comment(action="remove")` is the reversible
    option; this one is for content that must not persist at all."""
    current = await db.fetch_one("SELECT id FROM content_comments WHERE id = ?", (comment_id,))
    if current is None:
        raise NotFoundError("Comment not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM content_comments WHERE id = ?", (comment_id,)),
            audit_statement(
                action="content_comment.deleted",
                entity_type="content_comment",
                entity_id=comment_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": comment_id, "deleted": True}

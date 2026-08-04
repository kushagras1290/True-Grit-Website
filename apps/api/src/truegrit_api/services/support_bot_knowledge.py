"""Admin-editable knowledge base shared by both support bots
(`services.support_bot` for the admin panel, `services.support_bot_public`
for the storefront).

Rows live in `support_bot_knowledge` (migrations 0076/0077), split by
`scope` ('admin' | 'storefront') into one table and one
`support_bot.manage`-gated admin-panel screen rather than building two
parallel CRUD surfaces -- customers never edit what their bot knows, so both
scopes stay admin-managed. `select_relevant` (read by whichever bot is
answering) only ever reads its own scope.

`keywords` stays a plain space-separated column matched by simple overlap
against the asker's question -- the corpus is small enough (dozens of short
entries per scope) that this stays adequate; a real embeddings/vector-search
pipeline would be a drop-in replacement for `select_relevant` alone if a
corpus grows past what keyword matching handles well.
"""

from __future__ import annotations

from typing import Any, Literal

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

Scope = Literal["admin", "storefront"]

_MAX_TITLE_LENGTH = 120
_MAX_CONTENT_LENGTH = 2000


def _clean_keywords(raw: str) -> str:
    words = {word.strip().lower() for word in raw.split() if word.strip()}
    return " ".join(sorted(words))


def _validate_title_and_content(title: str, content: str) -> tuple[str, str]:
    title = title.strip()
    content = content.strip()
    if not title or len(title) > _MAX_TITLE_LENGTH:
        raise ValidationAppError(f"Title must be 1-{_MAX_TITLE_LENGTH} characters.")
    if not content or len(content) > _MAX_CONTENT_LENGTH:
        raise ValidationAppError(f"Content must be 1-{_MAX_CONTENT_LENGTH} characters.")
    return title, content


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "scope": row["scope"],
        "title": row["title"],
        "keywords": row["keywords"],
        "content": row["content"],
        "isBuiltin": bool(row["is_builtin"]),
        "updatedAt": row["updated_at"],
    }


async def list_entries(db: Database, *, scope: Scope | None = None) -> list[dict[str, Any]]:
    if scope is None:
        rows = await db.fetch_all(
            "SELECT id, scope, title, keywords, content, is_builtin, updated_at"
            " FROM support_bot_knowledge ORDER BY scope, title"
        )
    else:
        rows = await db.fetch_all(
            "SELECT id, scope, title, keywords, content, is_builtin, updated_at"
            " FROM support_bot_knowledge WHERE scope = ? ORDER BY title",
            (scope,),
        )
    return [_row_to_dict(row) for row in rows]


async def create_entry(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    scope: Scope,
    title: str,
    keywords: str,
    content: str,
) -> dict[str, Any]:
    title, content = _validate_title_and_content(title, content)
    clean_keywords = _clean_keywords(keywords)
    if not clean_keywords:
        raise ValidationAppError("Add at least one keyword so the bot can find this entry.")

    entry_id = new_id("sbk")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO support_bot_knowledge (id, scope, title, keywords, content,"
                " is_builtin, created_at, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)",
                (entry_id, scope, title, clean_keywords, content, now, now, actor.user_id),
            ),
            audit_statement(
                action="support_bot_knowledge.created",
                entity_type="support_bot_knowledge",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"scope": scope, "title": title},
            ),
        ]
    )
    return {
        "id": entry_id,
        "scope": scope,
        "title": title,
        "keywords": clean_keywords,
        "content": content,
        "isBuiltin": False,
        "updatedAt": now,
    }


async def update_entry(
    db: Database,
    actor: Principal,
    request_id: str,
    entry_id: str,
    *,
    title: str,
    keywords: str,
    content: str,
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT id, scope, title FROM support_bot_knowledge WHERE id = ?", (entry_id,)
    )
    if existing is None:
        raise NotFoundError("Knowledge entry not found.")
    title, content = _validate_title_and_content(title, content)
    clean_keywords = _clean_keywords(keywords)
    if not clean_keywords:
        raise ValidationAppError("Add at least one keyword so the bot can find this entry.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE support_bot_knowledge"
                " SET title = ?, keywords = ?, content = ?, updated_at = ?, updated_by = ?"
                " WHERE id = ?",
                (title, clean_keywords, content, now, actor.user_id, entry_id),
            ),
            audit_statement(
                action="support_bot_knowledge.updated",
                entity_type="support_bot_knowledge",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"title": existing["title"]},
                after={"title": title},
            ),
        ]
    )
    return {
        "id": entry_id,
        "scope": existing["scope"],
        "title": title,
        "keywords": clean_keywords,
        "content": content,
        "updatedAt": now,
    }


async def delete_entry(db: Database, actor: Principal, request_id: str, entry_id: str) -> None:
    existing = await db.fetch_one(
        "SELECT id, title FROM support_bot_knowledge WHERE id = ?", (entry_id,)
    )
    if existing is None:
        raise NotFoundError("Knowledge entry not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM support_bot_knowledge WHERE id = ?", (entry_id,)),
            audit_statement(
                action="support_bot_knowledge.deleted",
                entity_type="support_bot_knowledge",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"title": existing["title"]},
            ),
        ]
    )


async def select_relevant(db: Database, question: str, *, scope: Scope, limit: int) -> list[str]:
    """The `limit` most keyword-relevant entries' content within `scope`, or
    the first `limit` entries alphabetically if nothing matched -- so an
    off-topic question still gets a reasonably sized, non-empty reference
    block instead of the entire table."""
    question_words = {word for word in question.lower().split() if len(word) > 2}
    rows = await db.fetch_all(
        "SELECT keywords, content FROM support_bot_knowledge WHERE scope = ?", (scope,)
    )
    scored = [(len(question_words & set(row["keywords"].split())), row["content"]) for row in rows]
    scored = [pair for pair in scored if pair[0] > 0]
    scored.sort(key=lambda pair: pair[0], reverse=True)
    top = [content for _, content in scored[:limit]]
    if top:
        return top
    fallback_rows = await db.fetch_all(
        "SELECT content FROM support_bot_knowledge WHERE scope = ? ORDER BY title LIMIT ?",
        (scope, limit),
    )
    return [row["content"] for row in fallback_rows]

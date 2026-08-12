"""Staff messaging: groups and direct messages.

Membership (creating conversations, adding/removing participants, renaming
groups) is provisioned by the super administrator only. Callers here never
re-check that -- `api.messages` calls `auth.dependencies.require_owner`
before invoking any of the management functions below, the same split
`api.admin` already uses for its own owner-only actions (server logs, the DB
browser). Every function in this module assumes that gate has already run
where the docstring says "owner-only".

Live delivery of a just-sent message goes over a WebSocket to a
per-conversation Durable Object (`realtime.chat_room.ChatRoomDO`), not
through this module -- these functions cover conversation/participant
management and history/unread reads, which is what a client needs before a
socket is even open, and what backs the initial page load and scrollback.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_GROUP_NAME_LENGTH = 120
_HISTORY_DEFAULT_LIMIT = 50
_HISTORY_MAX_LIMIT = 200
# A "translate this chat" request only ever covers messages the caller
# already has loaded (the frontend sends exactly the ids on screen), but
# this still caps it -- the same reasoning as _HISTORY_MAX_LIMIT -- so a
# crafted request cannot force hundreds of sequential Workers AI calls into
# one request and blow the Worker's CPU budget.
_MAX_TRANSLATE_BATCH = 100


async def _require_participant(db: Database, conversation_id: str, user_id: str) -> None:
    row = await db.fetch_one(
        "SELECT 1 FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    if row is None:
        # Not found, not forbidden: a non-participant should not learn
        # whether this conversation id even exists.
        raise NotFoundError("Conversation not found.")


async def _validate_staff_user_ids(db: Database, user_ids: list[str]) -> list[str]:
    unique = list(dict.fromkeys(user_ids))
    if not unique:
        raise ValidationAppError("Select at least one participant.")
    placeholders = ", ".join("?" for _ in unique)
    rows = await db.fetch_all(
        f"SELECT id FROM users WHERE id IN ({placeholders})"
        " AND user_type = 'staff' AND deleted_at IS NULL",
        unique,
    )
    found = {row["id"] for row in rows}
    missing = [user_id for user_id in unique if user_id not in found]
    if missing:
        raise ValidationAppError("Unknown staff member.", details={"userIds": missing})
    return unique


async def _participants_by_conversation(
    db: Database, conversation_ids: list[str]
) -> dict[str, list[dict[str, Any]]]:
    """Each participant's role names ride along so the UI can show who it is
    talking to (e.g. "Riya Nair -- Farm Owner") without a second round trip
    per participant -- same GROUP_CONCAT shape as the admin user list."""
    if not conversation_ids:
        return {}
    placeholders = ", ".join("?" for _ in conversation_ids)
    rows = await db.fetch_all(
        f"""
        SELECT cp.conversation_id, u.id AS user_id, u.display_name,
          (SELECT GROUP_CONCAT(r.name, ', ') FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id WHERE ur.user_id = u.id) AS role_names
        FROM conversation_participants cp
        JOIN users u ON u.id = cp.user_id
        WHERE cp.conversation_id IN ({placeholders})
        ORDER BY u.display_name
        """,
        conversation_ids,
    )
    result: dict[str, list[dict[str, Any]]] = {cid: [] for cid in conversation_ids}
    for row in rows:
        result[row["conversation_id"]].append(
            {
                "userId": row["user_id"],
                "displayName": row["display_name"],
                "roles": row["role_names"].split(", ") if row["role_names"] else [],
            }
        )
    return result


async def list_my_conversations(db: Database, actor: Principal) -> list[dict[str, Any]]:
    rows = await db.fetch_all(
        """
        SELECT
          c.id, c.type, c.name, c.created_at,
          lm.body AS last_message_body,
          lm.created_at AS last_message_at,
          (
            SELECT COUNT(*) FROM messages m
            WHERE m.conversation_id = c.id
              AND m.created_at > COALESCE(cr.last_read_at, '')
          ) AS unread_count
        FROM conversations c
        JOIN conversation_participants cp ON cp.conversation_id = c.id AND cp.user_id = ?
        LEFT JOIN conversation_reads cr ON cr.conversation_id = c.id AND cr.user_id = ?
        LEFT JOIN messages lm ON lm.id = (
          SELECT id FROM messages
          WHERE conversation_id = c.id
          ORDER BY created_at DESC
          LIMIT 1
        )
        WHERE c.archived_at IS NULL
        ORDER BY COALESCE(lm.created_at, c.created_at) DESC
        """,
        (actor.user_id, actor.user_id),
    )
    participants_by_conversation = await _participants_by_conversation(
        db, [row["id"] for row in rows]
    )
    return [
        {
            "id": row["id"],
            "type": row["type"],
            "name": row["name"],
            "createdAt": row["created_at"],
            "lastMessageBody": row["last_message_body"],
            "lastMessageAt": row["last_message_at"],
            "unreadCount": row["unread_count"],
            "participants": participants_by_conversation.get(row["id"], []),
        }
        for row in rows
    ]


async def get_conversation_history(
    db: Database,
    actor: Principal,
    conversation_id: str,
    *,
    limit: int = _HISTORY_DEFAULT_LIMIT,
    offset: int = 0,
) -> dict[str, Any]:
    await _require_participant(db, conversation_id, actor.user_id)
    limit = min(max(limit, 1), _HISTORY_MAX_LIMIT)
    rows = await db.fetch_all(
        """
        SELECT m.id, m.sender_id, u.display_name AS sender_name, m.body, m.created_at
        FROM messages m
        JOIN users u ON u.id = m.sender_id
        WHERE m.conversation_id = ?
        ORDER BY m.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (conversation_id, limit, offset),
    )
    messages = [
        {
            "id": row["id"],
            "senderId": row["sender_id"],
            "senderName": row["sender_name"],
            "body": row["body"],
            "createdAt": row["created_at"],
        }
        for row in reversed(rows)
    ]
    return {"conversationId": conversation_id, "messages": messages, "limit": limit}


async def mark_read(
    db: Database,
    actor: Principal,
    conversation_id: str,
    *,
    last_read_message_id: str | None,
) -> dict[str, Any]:
    await _require_participant(db, conversation_id, actor.user_id)
    now = utc_now_iso()
    await db.execute(
        """
        INSERT INTO conversation_reads
          (conversation_id, user_id, last_read_message_id, last_read_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(conversation_id, user_id) DO UPDATE SET
          last_read_message_id = excluded.last_read_message_id,
          last_read_at = excluded.last_read_at
        """,
        (conversation_id, actor.user_id, last_read_message_id, now),
    )
    return {"conversationId": conversation_id, "lastReadAt": now}


async def create_conversation(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    type_: str,
    name: str | None,
    participant_user_ids: list[str],
) -> dict[str, Any]:
    """Owner-only. Creates a group or direct conversation. For 'direct', an
    existing conversation between exactly the same two people is reused
    rather than duplicated."""
    if type_ not in ("group", "direct"):
        raise ValidationAppError("Conversation type must be 'group' or 'direct'.")

    participants = await _validate_staff_user_ids(db, participant_user_ids)

    clean_name: str | None
    if type_ == "group":
        clean_name = (name or "").strip()
        if not clean_name:
            raise ValidationAppError("Group conversations need a name.")
        if len(clean_name) > _MAX_GROUP_NAME_LENGTH:
            raise ValidationAppError(
                f"Group name must be {_MAX_GROUP_NAME_LENGTH} characters or fewer."
            )
        if len(participants) < 1:
            raise ValidationAppError("A group needs at least one participant.")
    else:
        clean_name = None
        if len(participants) != 2:
            raise ValidationAppError("A direct conversation needs exactly two participants.")
        existing = await db.fetch_one(
            """
            SELECT c.id
            FROM conversations c
            WHERE c.type = 'direct'
              AND (SELECT COUNT(*) FROM conversation_participants WHERE conversation_id = c.id) = 2
              AND EXISTS (
                SELECT 1 FROM conversation_participants
                WHERE conversation_id = c.id AND user_id = ?
              )
              AND EXISTS (
                SELECT 1 FROM conversation_participants
                WHERE conversation_id = c.id AND user_id = ?
              )
            """,
            (participants[0], participants[1]),
        )
        if existing is not None:
            return {"id": existing["id"], "type": "direct", "name": None, "reused": True}

    conversation_id = new_id("conv")
    now = utc_now_iso()
    statements: list[Any] = [
        (
            "INSERT INTO conversations (id, type, name, created_by, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (conversation_id, type_, clean_name, actor.user_id, now),
        )
    ]
    for user_id in participants:
        statements.append(
            (
                "INSERT INTO conversation_participants"
                " (conversation_id, user_id, added_at, added_by) VALUES (?, ?, ?, ?)",
                (conversation_id, user_id, now, actor.user_id),
            )
        )
    statements.append(
        audit_statement(
            action="conversation.created",
            entity_type="conversation",
            entity_id=conversation_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"type": type_, "name": clean_name, "participantIds": participants},
        )
    )
    await db.batch(statements)
    return {"id": conversation_id, "type": type_, "name": clean_name, "reused": False}


async def rename_conversation(
    db: Database,
    actor: Principal,
    request_id: str,
    conversation_id: str,
    *,
    name: str,
) -> dict[str, Any]:
    """Owner-only. Group conversations only -- a direct conversation's label
    is always derived from its two participants, so it has nothing to rename."""
    conversation = await db.fetch_one(
        "SELECT id, type, name FROM conversations WHERE id = ? AND archived_at IS NULL",
        (conversation_id,),
    )
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    if conversation["type"] != "group":
        raise ValidationAppError("Only group conversations can be renamed.")
    clean_name = name.strip()
    if not clean_name:
        raise ValidationAppError("Group name cannot be empty.")
    if len(clean_name) > _MAX_GROUP_NAME_LENGTH:
        raise ValidationAppError(
            f"Group name must be {_MAX_GROUP_NAME_LENGTH} characters or fewer."
        )

    now = utc_now_iso()
    await db.batch(
        [
            ("UPDATE conversations SET name = ? WHERE id = ?", (clean_name, conversation_id)),
            audit_statement(
                action="conversation.renamed",
                entity_type="conversation",
                entity_id=conversation_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"name": conversation["name"]},
                after={"name": clean_name},
            ),
        ]
    )
    return {"id": conversation_id, "name": clean_name}


async def add_participants(
    db: Database,
    actor: Principal,
    request_id: str,
    conversation_id: str,
    *,
    user_ids: list[str],
) -> dict[str, Any]:
    """Owner-only."""
    conversation = await db.fetch_one(
        "SELECT id, type FROM conversations WHERE id = ? AND archived_at IS NULL",
        (conversation_id,),
    )
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    if conversation["type"] == "direct":
        raise ValidationAppError("Direct conversations always have exactly two participants.")

    candidates = await _validate_staff_user_ids(db, user_ids)
    existing_rows = await db.fetch_all(
        "SELECT user_id FROM conversation_participants WHERE conversation_id = ?",
        (conversation_id,),
    )
    already_in = {row["user_id"] for row in existing_rows}
    to_add = [user_id for user_id in candidates if user_id not in already_in]
    if not to_add:
        return {"id": conversation_id, "addedUserIds": []}

    now = utc_now_iso()
    statements: list[Any] = [
        (
            "INSERT INTO conversation_participants"
            " (conversation_id, user_id, added_at, added_by) VALUES (?, ?, ?, ?)",
            (conversation_id, user_id, now, actor.user_id),
        )
        for user_id in to_add
    ]
    statements.append(
        audit_statement(
            action="conversation.participants_added",
            entity_type="conversation",
            entity_id=conversation_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"addedUserIds": to_add},
        )
    )
    await db.batch(statements)
    return {"id": conversation_id, "addedUserIds": to_add}


async def remove_participant(
    db: Database,
    actor: Principal,
    request_id: str,
    conversation_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Owner-only."""
    conversation = await db.fetch_one(
        "SELECT id, type FROM conversations WHERE id = ? AND archived_at IS NULL",
        (conversation_id,),
    )
    if conversation is None:
        raise NotFoundError("Conversation not found.")
    if conversation["type"] == "direct":
        raise ValidationAppError(
            "Direct conversations always have exactly two participants; archive it instead."
        )
    member = await db.fetch_one(
        "SELECT 1 FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
        (conversation_id, user_id),
    )
    if member is None:
        raise NotFoundError("This person is not in the conversation.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "DELETE FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
                (conversation_id, user_id),
            ),
            (
                "DELETE FROM conversation_reads WHERE conversation_id = ? AND user_id = ?",
                (conversation_id, user_id),
            ),
            audit_statement(
                action="conversation.participant_removed",
                entity_type="conversation",
                entity_id=conversation_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"removedUserId": user_id},
            ),
        ]
    )
    return {"id": conversation_id, "removedUserId": user_id}


async def _cached_message_translations(
    db: Database, message_ids: list[str], locale: str
) -> dict[str, str]:
    if not message_ids:
        return {}
    placeholders = ", ".join("?" for _ in message_ids)
    rows = await db.fetch_all(
        f"SELECT message_id, translated_body FROM message_translations"
        f" WHERE locale = ? AND message_id IN ({placeholders})",
        (locale, *message_ids),
    )
    return {row["message_id"]: row["translated_body"] for row in rows}


async def translate_message(
    db: Database,
    translator: Translator,
    conversation_id: str,
    message_id: str,
    actor_user_id: str,
    locale: str,
) -> dict[str, Any]:
    """Translate one message into `locale` -- the per-message "Translate"
    action. Cached by (message_id, locale): a message's text never changes
    after it is sent, so a repeat view of an already-translated message never
    calls the translator again."""
    await _require_participant(db, conversation_id, actor_user_id)
    message = await db.fetch_one(
        "SELECT id, body FROM messages WHERE id = ? AND conversation_id = ?",
        (message_id, conversation_id),
    )
    if message is None:
        raise NotFoundError("Message not found.")

    cached = await _cached_message_translations(db, [message_id], locale)
    if message_id in cached:
        return {"messageId": message_id, "locale": locale, "translated": cached[message_id]}

    translated = await translator.translate(message["body"], target_lang=locale)
    now = utc_now_iso()
    await db.execute(
        """
        INSERT INTO message_translations (message_id, locale, translated_body, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(message_id, locale) DO UPDATE SET
          translated_body = excluded.translated_body,
          created_at = excluded.created_at
        """,
        (message_id, locale, translated, now),
    )
    return {"messageId": message_id, "locale": locale, "translated": translated}


async def translate_conversation(
    db: Database,
    translator: Translator,
    conversation_id: str,
    actor_user_id: str,
    locale: str,
    message_ids: list[str],
) -> list[dict[str, Any]]:
    """Translate a batch of this conversation's messages into `locale` -- the
    "Translate chat" action, covering whichever messages the caller currently
    has loaded (never the full unbounded history; see _MAX_TRANSLATE_BATCH).
    Already-cached messages are served without a translator call; only the
    remainder are actually translated (and then cached for next time)."""
    await _require_participant(db, conversation_id, actor_user_id)
    unique_ids = list(dict.fromkeys(message_ids))[:_MAX_TRANSLATE_BATCH]
    if not unique_ids:
        return []

    placeholders = ", ".join("?" for _ in unique_ids)
    rows = await db.fetch_all(
        f"SELECT id, body FROM messages"
        f" WHERE conversation_id = ? AND id IN ({placeholders})"
        f" ORDER BY created_at",
        (conversation_id, *unique_ids),
    )
    if not rows:
        return []

    cached = await _cached_message_translations(db, [row["id"] for row in rows], locale)
    now = utc_now_iso()
    statements: list[tuple[str, tuple[Any, ...]]] = []
    results: list[dict[str, Any]] = []
    for row in rows:
        if row["id"] in cached:
            results.append({"messageId": row["id"], "translated": cached[row["id"]]})
            continue
        translated = await translator.translate(row["body"], target_lang=locale)
        statements.append(
            (
                """
                INSERT INTO message_translations (message_id, locale, translated_body, created_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(message_id, locale) DO UPDATE SET
                  translated_body = excluded.translated_body,
                  created_at = excluded.created_at
                """,
                (row["id"], locale, translated, now),
            )
        )
        results.append({"messageId": row["id"], "translated": translated})
    if statements:
        await db.batch(statements)
    return results

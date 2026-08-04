"""ChatRoomDO — a Durable Object that fans a conversation's new messages out
to every currently-connected admin, live.

One instance per conversation (`env.CHAT_ROOMS.getByName(conversation_id)`
in `worker.py`), using the WebSocket Hibernation API
(https://developers.cloudflare.com/durable-objects/best-practices/websockets/)
so an idle connection does not hold the isolate — and its duration billing —
awake between messages.

Unlike `platform.d1`/`platform.translation`, this module is NOT required to be
import-safe outside the Workers runtime: it is only ever imported by
`worker.py`, itself a Workers-only entry point, so importing `js`/`workers` at
module load is fine here.

Message history is NOT kept in this Durable Object's own storage — `messages`
in D1 (migration 0073) is the single source of truth, so a conversation's
scrollback is one ordinary table anyone with `messages.use` and a
`conversation_participants` row can read, the same as everything else in this
API. This object only ever holds the live fan-out: who is currently
connected, and broadcasting a just-persisted message to them. The one piece
of state that must survive hibernation (`__init__` reruns on every wakeup —
see the docs above) is which conversation this instance is for, so that is
kept in durable storage rather than a plain instance attribute; each
connected socket's user id is kept via `serializeAttachment`, the mechanism
designed for exactly that.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from js import WebSocketPair
from pyodide.ffi import to_js
from workers import DurableObject, Response

from truegrit_api.platform.d1 import D1Database
from truegrit_api.util.cookies import cookie_value
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_MESSAGE_LENGTH = 4_000
_CONVERSATION_ID_KEY = "conversation_id"


def _to_py(value: Any) -> Any:
    """Same discipline as `platform.d1`: a Pyodide JsProxy (e.g. the Map
    `deserializeAttachment()` hands back) exposes `.to_py()`; an already-native
    Python value does not, so convert only when needed."""
    to_py = getattr(value, "to_py", None)
    return to_py() if callable(to_py) else value


class ChatRoomDO(DurableObject):
    def __init__(self, state: Any, env: Any):
        super().__init__(state, env)
        self.ctx = state
        self.env = env

    async def fetch(self, request: Any) -> Any:
        from urllib.parse import urlparse

        conversation_id = urlparse(str(request.url)).path.rsplit("/", 1)[-1]
        if not conversation_id:
            return Response("Not found.", status=404)
        if str(request.headers.get("upgrade") or "").lower() != "websocket":
            return Response("Expected a WebSocket upgrade.", status=426)

        user_id = await self._authenticated_participant(request, conversation_id)
        if user_id is None:
            return Response("Unauthorized", status=401)

        # Durable, not just a plain attribute: hibernation re-runs __init__
        # before the next webSocketMessage, so anything this instance needs
        # to remember between messages has to live in storage.
        await self.ctx.storage.put(_CONVERSATION_ID_KEY, conversation_id)

        client, server = WebSocketPair.new().object_values()
        # acceptWebSocket (not ws.accept()) is what allows this DO to
        # hibernate between messages instead of staying billed-awake. Pyodide
        # does not auto-marshal a Python list into a JS Array across this
        # particular bound-method call (confirmed live: passing a raw list
        # raises "parameter 2 is not of type 'Array'"), so tags and the
        # attachment both go through to_js explicitly.
        self.ctx.acceptWebSocket(server, to_js([user_id]))
        server.serializeAttachment(to_js({"userId": user_id}))
        return Response(None, status=101, web_socket=client)

    async def webSocketMessage(self, ws: Any, message: Any) -> None:  # noqa: N802 -- runtime hook name
        attachment = _to_py(ws.deserializeAttachment()) or {}
        user_id = attachment.get("userId") if isinstance(attachment, dict) else None
        conversation_id = await self.ctx.storage.get(_CONVERSATION_ID_KEY)
        if not user_id or not conversation_id:
            return

        try:
            payload = json.loads(str(message))
        except (TypeError, ValueError):
            return
        body = str(payload.get("body", "")).strip()
        if not body or len(body) > _MAX_MESSAGE_LENGTH:
            return

        db = D1Database(self.env.DB)
        # The handshake in `fetch` already checked membership once, but a
        # hibernated connection can outlive a participant being removed from
        # the conversation, so re-check on every send.
        member = await db.fetch_one(
            "SELECT 1 FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        if member is None:
            ws.close(4403, "Removed from this conversation.")
            return

        message_id = new_id("msg")
        created_at = utc_now_iso()
        await db.execute(
            "INSERT INTO messages (id, conversation_id, sender_id, body, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (message_id, conversation_id, user_id, body, created_at),
        )

        outgoing = json.dumps(
            {
                "type": "message",
                "id": message_id,
                "conversationId": conversation_id,
                "senderId": user_id,
                "body": body,
                "createdAt": created_at,
            }
        )
        for socket in self.ctx.get_websockets():
            socket.send(outgoing)

    async def webSocketClose(  # noqa: N802 -- runtime hook name
        self, ws: Any, code: int, reason: str, was_clean: bool
    ) -> None:
        # web_socket_auto_reply_to_close (this Worker's compatibility date is
        # past 2026-04-07) already auto-replies to Close frames; calling
        # close() here is safe but no longer strictly required.
        ws.close(code, reason)

    async def _authenticated_participant(self, request: Any, conversation_id: str) -> str | None:
        """The connecting staff user's id, or None if the session is
        missing/expired or they are not a participant of this conversation.
        Mirrors worker.py's `_authorized_media_uploader`: a raw, direct-D1
        cookie check, since this runs outside FastAPI entirely."""
        token = cookie_value(request, getattr(self.env, "SESSION_COOKIE_NAME", "tg_session"))
        if not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        db = D1Database(self.env.DB)
        session_row = await db.fetch_one(
            """
            SELECT u.id
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
              AND s.revoked_at IS NULL
              AND s.expires_at > ?
              AND u.status = 'active'
              AND u.user_type = 'staff'
            """,
            (token_hash, utc_now_iso()),
        )
        if session_row is None:
            return None
        user_id = session_row["id"]
        member_row = await db.fetch_one(
            "SELECT 1 FROM conversation_participants WHERE conversation_id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        return user_id if member_row is not None else None

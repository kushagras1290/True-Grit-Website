"""Integration tests for staff messaging (migration 0073): conversation
creation/membership is owner-only (`require_owner`, not a permission —
see `services.messages`), while any participant with `messages.use` can
read history and mark a conversation read. Sending a message itself is not
covered here — it happens over the ChatRoomDO WebSocket, which needs a real
Workers runtime (`js`/`workers`) and cannot run under plain pytest."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

# usr_admin holds rol_super_admin (the owner); usr_editor/usr_pm are ordinary
# staff with messages.use but no owner role (see database/seeds/development.sql).


class FakeTranslator:
    """Deterministic stand-in for Workers AI, matching
    `test_entity_translations.FakeTranslator`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        self.calls.append((text, target_lang))
        return f"[{target_lang}] {text.upper()}"


def _insert_message(db: SQLiteDatabase, conversation_id: str, sender_id: str, body: str) -> str:
    """Sending goes over the ChatRoomDO WebSocket in production (not
    reachable from plain pytest -- see the module docstring), so tests that
    need an existing message insert one directly, the same shortcut
    `test_admin_management.py` takes for other Worker-only paths."""
    message_id = new_id("msg")
    db._conn.execute(
        "INSERT INTO messages (id, conversation_id, sender_id, body, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (message_id, conversation_id, sender_id, body, utc_now_iso()),
    )
    db._conn.commit()
    return message_id


def as_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_editor(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))


def as_product_manager(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_pm"))


def test_owner_can_create_group_and_manage_participants(client: TestClient, db: SQLiteDatabase):
    as_owner(client, db)

    created = client.post(
        "/v1/admin/messages/conversations",
        json={
            "type": "group",
            "name": "Ops Room",
            # The owner is deliberately not in this list: creating a group
            # for other staff to use does not require the owner to join it.
            "participantUserIds": ["usr_editor", "usr_pm"],
        },
    )
    assert created.status_code == 200, created.text
    conversation_id = created.json()["id"]

    # Verify membership from a participant's own view of the conversation
    # list, not the owner's — the owner is not a member of this group.
    as_editor(client, db)
    conversations = client.get("/v1/admin/messages/conversations").json()
    match = next(c for c in conversations if c["id"] == conversation_id)
    assert {p["userId"] for p in match["participants"]} == {"usr_editor", "usr_pm"}

    as_owner(client, db)
    renamed = client.patch(
        f"/v1/admin/messages/conversations/{conversation_id}", json={"name": "Ops Room (renamed)"}
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Ops Room (renamed)"

    removed = client.delete(
        f"/v1/admin/messages/conversations/{conversation_id}/participants/usr_pm"
    )
    assert removed.status_code == 200

    as_editor(client, db)
    conversations = client.get("/v1/admin/messages/conversations").json()
    match = next(c for c in conversations if c["id"] == conversation_id)
    assert {p["userId"] for p in match["participants"]} == {"usr_editor"}


def test_participants_carry_their_role_names(client: TestClient, db: SQLiteDatabase):
    as_owner(client, db)
    created = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor"]},
    )
    assert created.status_code == 200, created.text
    conversation_id = created.json()["id"]

    conversations = client.get("/v1/admin/messages/conversations").json()
    match = next(c for c in conversations if c["id"] == conversation_id)
    by_user = {p["userId"]: p["roles"] for p in match["participants"]}
    assert by_user["usr_admin"] != []
    assert isinstance(by_user["usr_editor"], list)


def test_non_owner_cannot_create_or_manage_conversations(client: TestClient, db: SQLiteDatabase):
    as_editor(client, db)  # holds messages.use, but is not the super admin

    response = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "group", "name": "Blocked", "participantUserIds": ["usr_pm"]},
    )
    assert response.status_code == 403


def test_direct_conversation_is_reused_not_duplicated(client: TestClient, db: SQLiteDatabase):
    as_owner(client, db)
    first = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_editor", "usr_pm"]},
    )
    assert first.status_code == 200
    assert first.json()["reused"] is False

    second = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_pm", "usr_editor"]},
    )
    assert second.status_code == 200
    assert second.json()["reused"] is True
    assert second.json()["id"] == first.json()["id"]


def test_non_participant_cannot_read_history(client: TestClient, db: SQLiteDatabase):
    as_owner(client, db)
    created = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor"]},
    )
    conversation_id = created.json()["id"]

    as_product_manager(client, db)  # never added to this conversation
    response = client.get(f"/v1/admin/messages/conversations/{conversation_id}/history")
    assert response.status_code == 404


def test_participant_can_read_history_and_mark_read(client: TestClient, db: SQLiteDatabase):
    as_owner(client, db)
    created = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor"]},
    )
    conversation_id = created.json()["id"]

    as_editor(client, db)
    history = client.get(f"/v1/admin/messages/conversations/{conversation_id}/history")
    assert history.status_code == 200
    assert history.json()["messages"] == []

    marked = client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/read", json={"lastReadMessageId": None}
    )
    assert marked.status_code == 200
    assert marked.json()["conversationId"] == conversation_id


def test_group_requires_a_name_and_direct_requires_exactly_two(
    client: TestClient, db: SQLiteDatabase
):
    as_owner(client, db)

    missing_name = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "group", "participantUserIds": ["usr_editor"]},
    )
    assert missing_name.status_code == 422

    too_many = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor", "usr_pm"]},
    )
    assert too_many.status_code == 422


def test_translate_message_is_cached_and_only_for_participants(db: SQLiteDatabase):
    fake = FakeTranslator()
    app = create_app(db=db, translator=fake)
    client = TestClient(app, raise_server_exceptions=False)
    as_owner(client, db)

    conversation_id = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor"]},
    ).json()["id"]
    message_id = _insert_message(db, conversation_id, "usr_editor", "Where is the shipment?")

    translated = client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/messages/{message_id}/translate",
        json={"locale": "hi"},
    )
    assert translated.status_code == 200, translated.text
    body = translated.json()
    assert body == {
        "messageId": message_id,
        "locale": "hi",
        "translated": "[hi] WHERE IS THE SHIPMENT?",
    }
    assert len(fake.calls) == 1

    # A repeat request for the same (message, locale) is served from the
    # message_translations cache -- the translator is not called again.
    again = client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/messages/{message_id}/translate",
        json={"locale": "hi"},
    )
    assert again.status_code == 200
    assert again.json()["translated"] == body["translated"]
    assert len(fake.calls) == 1

    # usr_pm was never added to this direct conversation.
    as_product_manager(client, db)
    blocked = client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/messages/{message_id}/translate",
        json={"locale": "hi"},
    )
    assert blocked.status_code == 404


def test_translate_conversation_translates_only_uncached_messages(db: SQLiteDatabase):
    fake = FakeTranslator()
    app = create_app(db=db, translator=fake)
    client = TestClient(app, raise_server_exceptions=False)
    as_owner(client, db)

    conversation_id = client.post(
        "/v1/admin/messages/conversations",
        json={"type": "direct", "participantUserIds": ["usr_admin", "usr_editor"]},
    ).json()["id"]
    first_id = _insert_message(db, conversation_id, "usr_admin", "Order shipped today.")
    second_id = _insert_message(db, conversation_id, "usr_editor", "Great, thank you!")

    # Pre-warm the cache for the first message only.
    client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/messages/{first_id}/translate",
        json={"locale": "fr"},
    )
    assert len(fake.calls) == 1

    batch = client.post(
        f"/v1/admin/messages/conversations/{conversation_id}/translate",
        json={"locale": "fr", "messageIds": [first_id, second_id]},
    )
    assert batch.status_code == 200, batch.text
    payload = batch.json()
    assert payload["locale"] == "fr"
    by_id = {row["messageId"]: row["translated"] for row in payload["messages"]}
    assert by_id[first_id] == "[fr] ORDER SHIPPED TODAY."
    assert by_id[second_id] == "[fr] GREAT, THANK YOU!"
    # Only the second message actually needed a fresh translator call.
    assert len(fake.calls) == 2

"""Integration tests for the admin support bot. The real WorkersAIChat only
runs inside the Workers runtime (needs `js`/`workers`), so these exercise the
tool-calling loop in services.support_bot against a scripted fake ChatModel
instead -- what matters here is that the loop wires tool results back to the
model correctly and that every tool re-checks the caller's own permissions,
not the wording of a real LLM response."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.ai_chat import ChatCompletion, ToolCall, ToolDefinition
from truegrit_api.platform.database import SQLiteDatabase


class ScriptedChat:
    """Replays a fixed sequence of ChatCompletion turns, one per `complete`
    call, and records every call it received for assertions."""

    def __init__(self, turns: list[ChatCompletion]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    async def complete(
        self,
        *,
        system_prompt: str,
        messages: list[dict[str, Any]],
        tools: list[ToolDefinition] | None = None,
    ) -> ChatCompletion:
        self.calls.append({"system_prompt": system_prompt, "messages": messages, "tools": tools})
        return self._turns[len(self.calls) - 1]


def _client_with_chat(db: SQLiteDatabase, chat: ScriptedChat) -> TestClient:
    return TestClient(create_app(db=db, chat=chat), raise_server_exceptions=False)


def test_direct_answer_needs_no_tool_call(db: SQLiteDatabase):
    chat = ScriptedChat([ChatCompletion(text="Go to Products and click Publish.", tool_calls=[])])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.post(
        "/v1/admin/support-bot/chat", json={"message": "How do I publish a product?"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"reply": "Go to Products and click Publish."}
    assert len(chat.calls) == 1


def test_tool_call_round_trip_returns_live_data(db: SQLiteDatabase):
    tool_call = ToolCall(id="call_1", name="count_pending_orders", arguments={})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="There are 0 pending orders.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.post(
        "/v1/admin/support-bot/chat", json={"message": "How many orders are pending?"}
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"reply": "There are 0 pending orders."}
    assert len(chat.calls) == 2
    # The tool result was actually threaded back into the second call, stated
    # as plain text rather than an OpenAI-style tool message -- see
    # platform.ai_chat.tool_results_message.
    follow_up = chat.calls[1]["messages"][-1]
    assert follow_up["role"] == "user"
    assert '"pendingOrders"' in follow_up["content"]
    # The second call must not re-offer the tools, or the model can loop.
    assert chat.calls[1]["tools"] is None


def test_tool_denies_when_caller_lacks_permission(db: SQLiteDatabase):
    """usr_blogger has messages.use etc. but not orders.view -- the tool
    itself must refuse, not just the UI."""
    tool_call = ToolCall(id="call_1", name="count_pending_orders", arguments={})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="I can't check that for your account.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_blogger"))

    response = client.post(
        "/v1/admin/support-bot/chat", json={"message": "How many orders are pending?"}
    )
    assert response.status_code == 200, response.text
    assert "permission" in chat.calls[1]["messages"][-1]["content"]


def test_requires_staff_authentication(db: SQLiteDatabase):
    chat = ScriptedChat([ChatCompletion(text="unused", tool_calls=[])])
    client = _client_with_chat(db, chat)

    response = client.post("/v1/admin/support-bot/chat", json={"message": "hello"})
    assert response.status_code == 401
    assert chat.calls == []


def test_knowledge_base_seeded_and_matched(db: SQLiteDatabase):
    """Migration 0076's seed data should already answer a products question
    without any tool call."""
    chat = ScriptedChat([ChatCompletion(text="See the Products page.", tool_calls=[])])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.post(
        "/v1/admin/support-bot/chat", json={"message": "How do I publish a product?"}
    )
    assert response.status_code == 200, response.text
    system_prompt = chat.calls[0]["system_prompt"]
    assert "Products (/products)" in system_prompt


def test_knowledge_crud_requires_manage_permission(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))  # no support_bot.manage

    response = client.get("/v1/admin/support-bot/knowledge")
    assert response.status_code == 403


def test_knowledge_crud_round_trip(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))  # super admin

    listed = client.get("/v1/admin/support-bot/knowledge", params={"scope": "admin"})
    assert listed.status_code == 200
    assert len(listed.json()) == 36  # migration 0076's seed rows

    created = client.post(
        "/v1/admin/support-bot/knowledge",
        json={
            "scope": "admin",
            "title": "Test Section",
            "keywords": "test example",
            "content": "Test Section (/test): a page added for this test.",
        },
    )
    assert created.status_code == 200, created.text
    entry_id = created.json()["id"]
    assert created.json()["isBuiltin"] is False

    updated = client.patch(
        f"/v1/admin/support-bot/knowledge/{entry_id}",
        json={
            "title": "Test Section",
            "keywords": "test example renamed",
            "content": "Test Section (/test): updated content.",
        },
    )
    assert updated.status_code == 200
    assert "renamed" in updated.json()["keywords"]

    deleted = client.delete(f"/v1/admin/support-bot/knowledge/{entry_id}")
    assert deleted.status_code == 200

    listed_after = client.get("/v1/admin/support-bot/knowledge", params={"scope": "admin"})
    assert len(listed_after.json()) == 36


def test_knowledge_list_defaults_to_all_scopes(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    listed = client.get("/v1/admin/support-bot/knowledge")
    assert listed.status_code == 200
    assert len(listed.json()) == 42  # 36 admin + 6 storefront (migrations 0076/0077)

    storefront_only = client.get("/v1/admin/support-bot/knowledge", params={"scope": "storefront"})
    assert storefront_only.status_code == 200
    assert len(storefront_only.json()) == 6
    assert all(entry["scope"] == "storefront" for entry in storefront_only.json())


def test_bot_enabled_by_default(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    settings = client.get("/v1/admin/support-bot/settings")
    assert settings.status_code == 200
    # `searchResults`, `policyChars` and `policyPages` were removed with the
    # storefront bot's model: all three only shaped that bot's prompt, and it
    # no longer has one. What remains applies to the admin bot alone.
    assert settings.json() == {
        "admin": True,
        "storefront": True,
        "historyTurns": 10,
        "knowledgeSnippets": 6,
        "widgetColor": "",  # blank = inherit the site brand colour
    }


def test_disabling_the_bot_blocks_chat_and_is_reversible(db: SQLiteDatabase):
    chat = ScriptedChat([ChatCompletion(text="Go to Products.", tool_calls=[])])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    toggled = client.patch("/v1/admin/support-bot/settings/admin", json={"enabled": False})
    assert toggled.status_code == 200
    assert toggled.json() == {"scope": "admin", "enabled": False}

    blocked = client.post("/v1/admin/support-bot/chat", json={"message": "hello"})
    assert blocked.status_code == 422, blocked.text
    assert "turned off" in blocked.json()["error"]["message"]
    assert chat.calls == []  # never reached the model

    client.patch("/v1/admin/support-bot/settings/admin", json={"enabled": True})
    working = client.post("/v1/admin/support-bot/chat", json={"message": "hello"})
    assert working.status_code == 200
    assert working.json() == {"reply": "Go to Products."}


def test_toggle_requires_manage_permission(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))

    response = client.patch("/v1/admin/support-bot/settings/admin", json={"enabled": False})
    assert response.status_code == 403


def test_tuning_is_editable_and_takes_effect(db: SQLiteDatabase):
    """The knobs are admin-editable rather than module constants, so a change
    has to actually reach the next answer's prompt."""
    chat = ScriptedChat(
        [
            ChatCompletion(text="First.", tool_calls=[]),
            ChatCompletion(text="Second.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    history = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
        {"role": "user", "content": "three"},
        {"role": "assistant", "content": "four"},
    ]
    client.post(
        "/v1/admin/support-bot/chat", json={"message": "How do I publish?", "history": history}
    )
    # Default depth (10) keeps every one of the four prior turns, plus the
    # new question.
    assert len(chat.calls[0]["messages"]) == 5

    updated = client.patch("/v1/admin/support-bot/tuning/historyTurns", json={"value": 2})
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"key": "historyTurns", "value": 2}

    client.post(
        "/v1/admin/support-bot/chat", json={"message": "How do I publish?", "history": history}
    )
    assert len(chat.calls[1]["messages"]) == 3  # 2 kept turns + the question


def test_tuning_clamps_out_of_range_values(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    # Past the field's own outer bound: rejected outright rather than stored.
    rejected = client.patch("/v1/admin/support-bot/tuning/historyTurns", json={"value": 99999})
    assert rejected.status_code == 422

    # Within the field bound but above this key's own maximum: clamped down.
    clamped = client.patch("/v1/admin/support-bot/tuning/historyTurns", json={"value": 999})
    assert clamped.status_code == 200
    assert clamped.json() == {"key": "historyTurns", "value": 40}

    # Each key keeps its own range, not a shared one.
    snippets = client.patch("/v1/admin/support-bot/tuning/knowledgeSnippets", json={"value": 999})
    assert snippets.status_code == 200
    assert snippets.json() == {"key": "knowledgeSnippets", "value": 30}


def test_widget_color_round_trips_and_reaches_the_storefront(db: SQLiteDatabase):
    """The colour has to be readable without `support_bot.manage` -- both the
    storefront widget and the admin widget (shown to every staff member) read
    it from the public settings payload."""
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    assert client.get("/v1/public/settings").json()["supportBotColor"] == ""

    saved = client.patch("/v1/admin/support-bot/widget-color", json={"widgetColor": "#1f7a4d"})
    assert saved.status_code == 200, saved.text
    assert saved.json() == {"widgetColor": "#1f7a4d"}
    assert client.get("/v1/public/settings").json()["supportBotColor"] == "#1f7a4d"

    cleared = client.patch("/v1/admin/support-bot/widget-color", json={"widgetColor": ""})
    assert cleared.status_code == 200
    assert client.get("/v1/public/settings").json()["supportBotColor"] == ""


def test_widget_color_rejects_anything_that_is_not_a_hex_colour(db: SQLiteDatabase):
    """The value lands in an inline style attribute, so a CSS function or a
    stray semicolon must never be storable."""
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    for bad in ("red", "#12", "url(x)", "#fff;color:red"):
        response = client.patch("/v1/admin/support-bot/widget-color", json={"widgetColor": bad})
        assert response.status_code in {422}, f"{bad!r} was accepted"
    assert client.get("/v1/public/settings").json()["supportBotColor"] == ""


def test_widget_color_requires_manage_permission(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))

    response = client.patch("/v1/admin/support-bot/widget-color", json={"widgetColor": "#1f7a4d"})
    assert response.status_code == 403


def test_tuning_requires_manage_permission(db: SQLiteDatabase):
    chat = ScriptedChat([])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))

    response = client.patch("/v1/admin/support-bot/tuning/historyTurns", json={"value": 3})
    assert response.status_code == 403

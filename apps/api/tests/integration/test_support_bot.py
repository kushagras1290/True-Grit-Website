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
    # The tool result was actually threaded back into the second call.
    second_call_messages = chat.calls[1]["messages"]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert len(tool_messages) == 1
    assert '"pendingOrders"' in tool_messages[0]["content"]


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
    second_call_messages = chat.calls[1]["messages"]
    tool_messages = [m for m in second_call_messages if m.get("role") == "tool"]
    assert "permission" in tool_messages[0]["content"]


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
    assert settings.json() == {"admin": True, "storefront": True}


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

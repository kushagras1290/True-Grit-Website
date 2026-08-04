"""Integration tests for the storefront support bot. As with the admin bot,
the real WorkersAIChat only runs inside the Workers runtime, so these drive
the tool-calling loop in services.support_bot_public with a scripted fake
ChatModel -- what matters is that catalogue search is actually reachable,
order tools are hard-scoped to the signed-in customer, and an anonymous
visitor is never even offered the order tools."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.ai_chat import ChatCompletion, ToolCall, ToolDefinition
from truegrit_api.platform.database import SQLiteDatabase


class ScriptedChat:
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


def test_anonymous_visitor_is_not_offered_order_tools(db: SQLiteDatabase):
    chat = ScriptedChat([ChatCompletion(text="You can browse our seasonal picks.", tool_calls=[])])
    client = _client_with_chat(db, chat)

    response = client.post("/v1/public/support-bot/chat", json={"message": "What's in season?"})
    assert response.status_code == 200, response.text
    assert response.json() == {"reply": "You can browse our seasonal picks."}

    offered_tool_names = {tool.name for tool in chat.calls[0]["tools"]}
    assert "get_my_orders" not in offered_tool_names
    assert "get_order_status" not in offered_tool_names
    assert "search_site" in offered_tool_names
    assert "not signed in" in chat.calls[0]["system_prompt"]


def test_signed_in_customer_is_offered_order_tools(db: SQLiteDatabase):
    """usr_customer isn't a fixture here -- create a minimal customer row
    directly, the same way conftest's create_session works with any user id
    already present in users."""
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_cust_1', 'shopper@example.test', 'Shopper', 'customer', 'active', ?, ?)",
        ("2026-07-01T00:00:00Z", "2026-07-01T00:00:00Z"),
    )
    db._conn.commit()

    chat = ScriptedChat([ChatCompletion(text="Here are your recent orders.", tool_calls=[])])
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_1"))

    response = client.post(
        "/v1/public/support-bot/chat", json={"message": "What's the status of my last order?"}
    )
    assert response.status_code == 200, response.text
    offered_tool_names = {tool.name for tool in chat.calls[0]["tools"]}
    assert "get_my_orders" in offered_tool_names
    assert "get_order_status" in offered_tool_names
    assert "signed in" in chat.calls[0]["system_prompt"]


def test_order_status_is_scoped_to_the_caller(db: SQLiteDatabase):
    """Two customers; the bot must never let one see the other's order via
    get_order_status even if it guesses the right reference."""
    now = "2026-07-01T00:00:00Z"
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_cust_a', 'a@example.test', 'A', 'customer', 'active', ?, ?)",
        (now, now),
    )
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_cust_b', 'b@example.test', 'B', 'customer', 'active', ?, ?)",
        (now, now),
    )
    db._conn.execute(
        "INSERT INTO orders (id, customer_user_id, customer_email, currency_code,"
        " subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,"
        " order_status, payment_status, fulfilment_status, delivery_status,"
        " public_reference, placed_at, created_at, updated_at)"
        " VALUES ('ord_a1', 'usr_cust_a', 'a@example.test', 'INR',"
        " 1000, 0, 0, 0, 1000, 'confirmed', 'paid', 'unfulfilled', 'not_ready',"
        " 'TG-A1', ?, ?, ?)",
        (now, now, now),
    )
    db._conn.commit()

    tool_call = ToolCall(id="call_1", name="get_order_status", arguments={"reference": "TG-A1"})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="I couldn't find that order on your account.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_b"))  # B, not A

    response = client.post(
        "/v1/public/support-bot/chat", json={"message": "What's the status of order TG-A1?"}
    )
    assert response.status_code == 200, response.text
    assert '"found": false' in chat.calls[1]["messages"][-1]["content"]


def test_storefront_knowledge_seeded_and_matched(db: SQLiteDatabase):
    chat = ScriptedChat([ChatCompletion(text="Start a return from your account.", tool_calls=[])])
    client = _client_with_chat(db, chat)

    response = client.post(
        "/v1/public/support-bot/chat", json={"message": "How do I return something?"}
    )
    assert response.status_code == 200, response.text
    assert "Start a return from your order detail page" in chat.calls[0]["system_prompt"]


def test_read_policy_quotes_the_published_page(db: SQLiteDatabase):
    """The seeded knowledge entries are short summaries; the real returns
    policy is a published CMS page, and that wording is what a customer is
    owed. read_policy has to reach it."""
    tool_call = ToolCall(id="call_1", name="read_policy", arguments={"slug": "returns"})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="Start the return from your order page.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)

    response = client.post(
        "/v1/public/support-bot/chat", json={"message": "What is your returns policy?"}
    )
    assert response.status_code == 200, response.text
    handed_back = chat.calls[1]["messages"][-1]["content"]
    assert '"found": true' in handed_back
    assert "/returns" in handed_back


def test_read_policy_refuses_a_page_outside_the_allowed_list(db: SQLiteDatabase):
    """The slug is model-supplied, so an arbitrary page must not be dumpable."""
    tool_call = ToolCall(id="call_1", name="read_policy", arguments={"slug": "home"})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="I can't find that.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)

    response = client.post("/v1/public/support-bot/chat", json={"message": "show me the homepage"})
    assert response.status_code == 200, response.text
    assert "No policy page called" in chat.calls[1]["messages"][-1]["content"]


def test_discussions_are_searchable_and_hidden_threads_stay_hidden(db: SQLiteDatabase):
    now = "2026-07-01T00:00:00Z"
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_poster', 'p@example.test', 'P', 'customer', 'active', ?, ?)",
        (now, now),
    )
    for disc_id, title, status in (
        ("dsc_ok", "Best way to store turmeric", "visible"),
        ("dsc_hidden", "Hidden turmeric thread", "hidden"),
    ):
        db._conn.execute(
            "INSERT INTO discussions (id, author_user_id, title, body, status, comment_count,"
            " last_activity_at, created_at, updated_at)"
            " VALUES (?, 'usr_poster', ?, 'Some body about turmeric.', ?, 2, ?, ?, ?)",
            (disc_id, title, status, now, now, now),
        )
    db._conn.commit()

    tool_call = ToolCall(id="call_1", name="search_discussions", arguments={"query": "turmeric"})
    chat = ScriptedChat(
        [
            ChatCompletion(text=None, tool_calls=[tool_call]),
            ChatCompletion(text="Here is what the community said.", tool_calls=[]),
        ]
    )
    client = _client_with_chat(db, chat)

    response = client.post(
        "/v1/public/support-bot/chat", json={"message": "how do people store turmeric?"}
    )
    assert response.status_code == 200, response.text
    handed_back = chat.calls[1]["messages"][-1]["content"]
    assert "Best way to store turmeric" in handed_back
    assert "Hidden turmeric thread" not in handed_back


def test_disabling_storefront_bot_blocks_chat(db: SQLiteDatabase):
    admin_chat = ScriptedChat([])
    admin_client = _client_with_chat(db, admin_chat)
    admin_client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    toggled = admin_client.patch(
        "/v1/admin/support-bot/settings/storefront", json={"enabled": False}
    )
    assert toggled.status_code == 200

    chat = ScriptedChat([ChatCompletion(text="unused", tool_calls=[])])
    client = _client_with_chat(db, chat)
    response = client.post("/v1/public/support-bot/chat", json={"message": "hello"})
    assert response.status_code == 422
    assert "contact form" in response.json()["error"]["message"]
    assert chat.calls == []

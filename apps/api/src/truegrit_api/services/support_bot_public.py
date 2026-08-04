"""Storefront support bot: mixes admin-curated policy/how-to knowledge
(`support_bot_knowledge` rows with scope='storefront') with retrieval-style
tools over the live catalogue and content -- products, categories, articles,
and recipes -- plus, for a signed-in customer, their own order history.

This is the RAG half of the two bots: instead of a static product corpus,
the model calls a search tool at answer time and grounds its reply in
whatever the live catalogue actually returns right now, reusing the same
`SearchRepository` the storefront's own /search endpoint uses (synonym
expansion, geo-release filtering, translated names) rather than
reimplementing catalogue search.

No mutating tools exist here -- same posture as the admin bot
(`services.support_bot`). Order tools are hard-scoped to `customer.user_id`;
a customer's bot can never see another customer's orders, and an anonymous
visitor simply is not offered those tools at all, not merely hidden in the UI.
"""

from __future__ import annotations

import json
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.ai_chat import ChatModel, ChatUnavailableError, ToolCall, ToolDefinition
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import SearchRepository
from truegrit_api.services import support_bot_knowledge, support_bot_settings

_MAX_HISTORY_TURNS = 10
_MAX_TOOL_ROUNDS = 4
_KNOWLEDGE_SNIPPETS_PER_ANSWER = 6
_SEARCH_RESULT_LIMIT = 5

_SYSTEM_PROMPT_HEADER = (
    "You are True Grit's storefront help assistant, talking to a customer or"
    " visitor. Answer questions about how the site works using the reference"
    " below, and use search_site or search_categories to find real products,"
    " categories, articles, or recipes when the question is about what's"
    " actually available -- never invent a product, price, or availability."
    " Keep answers short, friendly, and concrete."
)


def _build_system_prompt(knowledge: list[str], *, signed_in: bool) -> str:
    reference = "\n\n".join(knowledge)
    identity_note = (
        "The visitor is signed in, so get_my_orders and get_order_status are"
        " available for their own orders."
        if signed_in
        else "The visitor is not signed in, so order-lookup tools are not"
        " available -- suggest they sign in to check an order."
    )
    return f"{_SYSTEM_PROMPT_HEADER}\n\n{identity_note}\n\nSite reference:\n{reference}"


# --- Retrieval tools (open to anyone) ---------------------------------------


async def _search_site(
    db: Database, *, query: str, country: str | None, locale: str | None
) -> dict[str, Any]:
    return await SearchRepository(db).search(
        query, limit=_SEARCH_RESULT_LIMIT, country=country, locale=locale
    )


async def _search_categories(db: Database, *, query: str) -> dict[str, Any]:
    like = f"%{query}%"
    rows = await db.fetch_all(
        """
        SELECT name, slug, short_description
        FROM categories
        WHERE status = 'published' AND visibility = 'public'
          AND (name LIKE ? OR short_description LIKE ?)
        ORDER BY name
        LIMIT ?
        """,
        (like, like, _SEARCH_RESULT_LIMIT),
    )
    return {
        "categories": [
            {
                "name": row["name"],
                "path": f"/category/{row['slug']}",
                "description": row["short_description"],
            }
            for row in rows
        ]
    }


# --- Order tools (signed-in customer only, hard-scoped to their own id) ----


async def _get_my_orders(db: Database, customer: Principal) -> dict[str, Any]:
    rows = await db.fetch_all(
        """
        SELECT public_reference, order_status, payment_status, total_minor, currency_code,
               COALESCE(placed_at, created_at) AS placed_at
        FROM orders
        WHERE customer_user_id = ?
        ORDER BY COALESCE(placed_at, created_at) DESC
        LIMIT 10
        """,
        (customer.user_id,),
    )
    return {
        "orders": [
            {
                "reference": row["public_reference"],
                "orderStatus": row["order_status"],
                "paymentStatus": row["payment_status"],
                "totalMinor": row["total_minor"],
                "currency": row["currency_code"],
                "placedAt": row["placed_at"],
            }
            for row in rows
        ]
    }


async def _get_order_status(db: Database, customer: Principal, reference: str) -> dict[str, Any]:
    order = await db.fetch_one(
        """
        SELECT public_reference, order_status, payment_status, fulfilment_status,
               delivery_status, total_minor, currency_code,
               COALESCE(placed_at, created_at) AS placed_at
        FROM orders WHERE public_reference = ? AND customer_user_id = ?
        """,
        (reference, customer.user_id),
    )
    if order is None:
        return {"found": False}
    return {
        "found": True,
        "reference": order["public_reference"],
        "orderStatus": order["order_status"],
        "paymentStatus": order["payment_status"],
        "fulfilmentStatus": order["fulfilment_status"],
        "deliveryStatus": order["delivery_status"],
        "totalMinor": order["total_minor"],
        "currency": order["currency_code"],
        "placedAt": order["placed_at"],
    }


_PUBLIC_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="search_site",
        description="Search live products, blog articles, and recipes for a keyword or phrase.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "What to search for."}},
            "required": ["query"],
        },
    ),
    ToolDefinition(
        name="search_categories",
        description="Search product categories by name or topic.",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Category name or topic."}},
            "required": ["query"],
        },
    ),
]

_CUSTOMER_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="get_my_orders",
        description="List the signed-in customer's own recent orders.",
    ),
    ToolDefinition(
        name="get_order_status",
        description=(
            "Look up the status of one of the signed-in customer's own orders"
            " by its reference number."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "The order's public reference number.",
                }
            },
            "required": ["reference"],
        },
    ),
]


async def _run_tool(
    db: Database,
    customer: Principal | None,
    call: ToolCall,
    *,
    country: str | None,
    locale: str | None,
) -> dict[str, Any]:
    if call.name == "search_site":
        query = str(call.arguments.get("query", "")).strip()
        if not query:
            return {"error": "No search query was given."}
        return await _search_site(db, query=query, country=country, locale=locale)
    if call.name == "search_categories":
        query = str(call.arguments.get("query", "")).strip()
        if not query:
            return {"error": "No search query was given."}
        return await _search_categories(db, query=query)
    if call.name == "get_my_orders":
        if customer is None:
            return {"error": "Sign in to check your orders."}
        return await _get_my_orders(db, customer)
    if call.name == "get_order_status":
        if customer is None:
            return {"error": "Sign in to check your orders."}
        reference = str(call.arguments.get("reference", "")).strip()
        if not reference:
            return {"error": "No order reference was given."}
        return await _get_order_status(db, customer, reference)
    return {"error": f"Unknown tool: {call.name}"}


async def ask(
    db: Database,
    customer: Principal | None,
    chat: ChatModel,
    *,
    message: str,
    history: list[dict[str, str]],
    country: str | None = None,
    locale: str | None = None,
) -> dict[str, Any]:
    """One turn of the storefront support bot. `customer` is None for an
    anonymous visitor -- order tools are left out of what the model is
    offered entirely, not merely hidden in a UI the model never sees."""
    if not await support_bot_settings.is_enabled(db, "storefront"):
        raise ChatUnavailableError(
            "The help assistant is currently unavailable. Please use the contact form instead."
        )

    knowledge = await support_bot_knowledge.select_relevant(
        db, message, scope="storefront", limit=_KNOWLEDGE_SNIPPETS_PER_ANSWER
    )
    system_prompt = _build_system_prompt(knowledge, signed_in=customer is not None)
    tools = _PUBLIC_TOOLS + _CUSTOMER_TOOLS if customer is not None else _PUBLIC_TOOLS

    trimmed_history = history[-_MAX_HISTORY_TURNS:]
    messages: list[dict[str, Any]] = [*trimmed_history, {"role": "user", "content": message}]

    for _ in range(_MAX_TOOL_ROUNDS):
        completion = await chat.complete(
            system_prompt=system_prompt, messages=messages, tools=tools
        )
        if completion.text is not None:
            return {"reply": completion.text}

        messages.append(
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.name,
                            "arguments": json.dumps(call.arguments),
                        },
                    }
                    for call in completion.tool_calls
                ],
            }
        )
        for call in completion.tool_calls:
            result = await _run_tool(db, customer, call, country=country, locale=locale)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(result),
                }
            )

    return {
        "reply": (
            "I wasn't able to finish looking that up. Try rephrasing, or use the contact form."
        )
    }

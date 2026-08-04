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
from truegrit_api.platform.ai_chat import (
    ChatModel,
    ChatUnavailableError,
    ToolCall,
    ToolDefinition,
    tool_results_message,
)
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import PageRepository, SearchRepository
from truegrit_api.services import support_bot_knowledge, support_bot_settings

# History depth and reference size are admin-editable
# (services.support_bot_settings), shared with the admin bot.

_SYSTEM_PROMPT_HEADER = (
    "You are True Grit's storefront help assistant, talking to a customer or"
    " visitor.\n"
    "- For returns, refunds, delivery, terms, privacy, sourcing standards, or"
    " how the company works: call read_policy and answer from the page's own"
    " wording. The reference below is only a summary; the policy page is what"
    " the store actually committed to, so prefer it and quote its specifics"
    " (timeframes, conditions, what the customer has to do).\n"
    "- For what is available to buy: call search_site or search_categories."
    " Never invent a product, price, or availability.\n"
    "- Give the specific detail the customer asked for, not a general"
    " description of the topic. If the policy genuinely does not cover their"
    " case, say so plainly and point them to /contact.\n"
    "- Keep it short, friendly, and concrete, and link the relevant page path."
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
    db: Database, *, query: str, country: str | None, locale: str | None, limit: int
) -> dict[str, Any]:
    return await SearchRepository(db).search(query, limit=limit, country=country, locale=locale)


def _blocks_to_text(content_json: Any, max_chars: int) -> str:
    """Flatten a page's blocks into readable prose.

    Block props are free-form per block type, so this walks the whole tree and
    keeps the human-readable strings rather than trying to know every schema.
    Keys that carry markup, ids, or URLs are skipped -- they are noise the
    model would otherwise try to quote back at a customer.
    """
    skip_keys = {"id", "type", "version", "href", "url", "src", "layout", "imageUrl", "imageAlt"}
    parts: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            text = node.strip()
            if len(text) > 2 and not text.startswith(("/", "http")):
                parts.append(text)
        elif isinstance(node, list):
            for item in node:
                walk(item)
        elif isinstance(node, dict):
            for key, value in node.items():
                if key not in skip_keys:
                    walk(value)

    try:
        walk(json.loads(content_json) if isinstance(content_json, str) else content_json)
    except (TypeError, ValueError):
        return ""
    return "\n".join(dict.fromkeys(parts))[:max_chars]


async def _read_policy(
    db: Database,
    *,
    slug: str,
    locale: str | None,
    allowed: tuple[str, ...],
    max_chars: int,
) -> dict[str, Any]:
    """Quote a published page verbatim. `allowed` is the operator's list, so
    the tool cannot be talked into dumping arbitrary CMS content."""
    if slug not in allowed:
        return {"error": f"No policy page called {slug!r}.", "available": list(allowed)}
    page = await PageRepository(db).get_published_by_slug(slug, locale=locale)
    if page is None:
        return {"found": False, "slug": slug}
    return {
        "found": True,
        "slug": slug,
        "title": page.get("title"),
        "path": f"/{slug}",
        "content": _blocks_to_text(page.get("content_json"), max_chars),
    }


async def _search_discussions(db: Database, *, query: str, limit: int) -> dict[str, Any]:
    """Community threads. Not part of `search_site` (SearchRepository covers
    products, articles, recipes and farms), but often where the real answer to
    a "has anyone tried..." question already lives. Only `visible` threads --
    hidden, archived and removed ones are moderation states a customer must
    never be shown."""
    like = f"%{query}%"
    rows = await db.fetch_all(
        """
        SELECT id, title, body, comment_count, last_activity_at
        FROM discussions
        WHERE status = 'visible' AND (title LIKE ? OR body LIKE ?)
        ORDER BY last_activity_at DESC
        LIMIT ?
        """,
        (like, like, limit),
    )
    return {
        "discussions": [
            {
                "title": row["title"],
                "path": f"/discussion/{row['id']}",
                "excerpt": str(row["body"] or "")[:300],
                "replies": row["comment_count"],
            }
            for row in rows
        ]
    }


async def _search_categories(db: Database, *, query: str, limit: int) -> dict[str, Any]:
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
        (like, like, limit),
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


def _public_tools(policy_slugs: tuple[str, ...]) -> list[ToolDefinition]:
    """Built per request, not module-level: which policy pages `read_policy`
    may quote is admin-editable, and the model is offered them as an enum."""
    return [
        ToolDefinition(
            name="search_site",
            description=(
                "Search live products, blog articles, and recipes for a keyword or phrase."
            ),
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
                "properties": {
                    "query": {"type": "string", "description": "Category name or topic."}
                },
                "required": ["query"],
            },
        ),
        ToolDefinition(
            name="search_discussions",
            description=(
                "Search the community discussion threads other customers and growers have"
                " posted. Good for opinions, experiences and 'has anyone tried' questions."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Topic or keyword to look for."}
                },
                "required": ["query"],
            },
        ),
        ToolDefinition(
            name="read_policy",
            description=(
                "Read the site's own published policy page, word for word. Use this for any"
                " question about returns, refunds, delivery, shipping, terms, privacy, sourcing"
                " standards, or how the company works -- always prefer it over answering from"
                " memory, because it is what the store actually committed to in writing."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "slug": {
                        "type": "string",
                        "enum": list(policy_slugs),
                        "description": "Which policy page to read.",
                    }
                },
                "required": ["slug"],
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
    search_limit: int,
    policy_slugs: tuple[str, ...],
    policy_chars: int,
) -> dict[str, Any]:
    if call.name == "search_site":
        query = str(call.arguments.get("query", "")).strip()
        if not query:
            return {"error": "No search query was given."}
        return await _search_site(
            db, query=query, country=country, locale=locale, limit=search_limit
        )
    if call.name == "search_categories":
        query = str(call.arguments.get("query", "")).strip()
        if not query:
            return {"error": "No search query was given."}
        return await _search_categories(db, query=query, limit=search_limit)
    if call.name == "search_discussions":
        query = str(call.arguments.get("query", "")).strip()
        if not query:
            return {"error": "No search query was given."}
        return await _search_discussions(db, query=query, limit=search_limit)
    if call.name == "read_policy":
        return await _read_policy(
            db,
            slug=str(call.arguments.get("slug", "")).strip(),
            locale=locale,
            allowed=policy_slugs,
            max_chars=policy_chars,
        )
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
        db,
        message,
        scope="storefront",
        limit=await support_bot_settings.get_tuning(db, "knowledgeSnippets"),
    )
    system_prompt = _build_system_prompt(knowledge, signed_in=customer is not None)
    policy_slugs = await support_bot_settings.get_policy_pages(db)
    public_tools = _public_tools(policy_slugs)
    tools = public_tools + _CUSTOMER_TOOLS if customer is not None else public_tools

    history_turns = await support_bot_settings.get_tuning(db, "historyTurns")
    trimmed_history = history[-history_turns:] if history_turns else []
    messages: list[dict[str, Any]] = [*trimmed_history, {"role": "user", "content": message}]

    completion = await chat.complete(system_prompt=system_prompt, messages=messages, tools=tools)
    if completion.text is not None:
        return {"reply": completion.text}

    # Exactly one round of tools, then a final answer -- see the admin bot's
    # `ask` and `tool_results_message` for why this is not a loop.
    search_limit = await support_bot_settings.get_tuning(db, "searchResults")
    policy_chars = await support_bot_settings.get_tuning(db, "policyChars")
    results = [
        (
            call,
            await _run_tool(
                db,
                customer,
                call,
                country=country,
                locale=locale,
                search_limit=search_limit,
                policy_slugs=policy_slugs,
                policy_chars=policy_chars,
            ),
        )
        for call in completion.tool_calls
    ]
    final = await chat.complete(
        system_prompt=system_prompt,
        messages=[*messages, tool_results_message(results)],
        tools=None,
    )
    if final.text is None:
        return {
            "reply": (
                "I wasn't able to finish looking that up. Try rephrasing, or use the contact form."
            )
        }
    return {"reply": final.text}

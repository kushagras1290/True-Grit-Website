"""Admin support bot: mixes the curated knowledge base
(`services.support_bot_knowledge`) with a small set of permission-scoped
live-data tools, so it can answer both "how do I..." questions and "how
many..." questions without ever inventing a number.

No mutating tools exist here on purpose -- the bot explains and deep-links,
it does not act. Every tool re-checks the asking admin's own permissions
before it queries anything, so the bot can never surface data the admin
could not already see themselves on the matching admin page (mirrors how
`services.access`'s farm-owner scoping works: the API enforces this
independently of what the UI happens to show).
"""

from __future__ import annotations

from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import PermissionDeniedError
from truegrit_api.platform.ai_chat import (
    ChatModel,
    ChatUnavailableError,
    ToolCall,
    ToolDefinition,
    tool_results_message,
)
from truegrit_api.platform.database import Database
from truegrit_api.services import support_bot_knowledge, support_bot_settings

# No server-side conversation storage -- the client resends the turns it
# wants remembered (components/support-bot-widget.tsx keeps them in React
# state). How many of those turns are kept, and how much reference material
# is embedded, are admin-editable (services.support_bot_settings) so answer
# quality can be tuned without a deploy; both are clamped there so the
# prompt can never grow without bound.

_SYSTEM_PROMPT_HEADER = (
    "You are the True Grit admin panel's built-in help assistant. You help "
    "staff understand what each admin page does and how to use it, and you "
    "can look up a small set of live figures using the tools you're given. "
    "Only call a tool when the question genuinely needs live data; for "
    "how-to questions, answer directly from the reference below. Never "
    "invent a number -- if no tool covers what's being asked, say so and "
    "name the admin page to check instead. Keep answers short and concrete."
)


async def _build_system_prompt(db: Database, question: str) -> str:
    entries = await support_bot_knowledge.select_relevant(
        db,
        question,
        scope="admin",
        limit=await support_bot_settings.get_tuning(db, "knowledgeSnippets"),
    )
    knowledge = "\n\n".join(entries)
    return f"{_SYSTEM_PROMPT_HEADER}\n\nAdmin panel reference:\n{knowledge}"


# --- Live-data tools -------------------------------------------------------


async def _count_pending_orders(db: Database, actor: Principal) -> dict[str, Any]:
    if not actor.has("orders.view"):
        raise PermissionDeniedError("You do not have permission to view orders.")
    row = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM orders"
        " WHERE order_status IN ('pending_payment', 'processing')"
    )
    return {"pendingOrders": row["count"] if row else 0}


async def _count_low_stock_variants(db: Database, actor: Principal) -> dict[str, Any]:
    if not actor.has("inventory.view"):
        raise PermissionDeniedError("You do not have permission to view inventory.")
    row = await db.fetch_one(
        "SELECT COUNT(*) AS count FROM inventory_levels"
        " WHERE (on_hand - reserved) <= reorder_threshold"
    )
    return {"lowStockVariants": row["count"] if row else 0}


async def _get_order_status(db: Database, actor: Principal, reference: str) -> dict[str, Any]:
    if not actor.has("orders.view"):
        raise PermissionDeniedError("You do not have permission to view orders.")
    order = await db.fetch_one(
        """
        SELECT public_reference, order_status, payment_status, fulfilment_status,
               total_minor, currency_code, COALESCE(placed_at, created_at) AS placed_at
        FROM orders WHERE public_reference = ?
        """,
        (reference,),
    )
    if order is None:
        return {"found": False}
    return {
        "found": True,
        "reference": order["public_reference"],
        "orderStatus": order["order_status"],
        "paymentStatus": order["payment_status"],
        "fulfilmentStatus": order["fulfilment_status"],
        "totalMinor": order["total_minor"],
        "currency": order["currency_code"],
        "placedAt": order["placed_at"],
    }


_TOOLS: list[ToolDefinition] = [
    ToolDefinition(
        name="count_pending_orders",
        description=(
            "Count orders currently awaiting payment or in processing (not yet completed)."
        ),
    ),
    ToolDefinition(
        name="count_low_stock_variants",
        description=(
            "Count product variants whose available stock (on hand minus reserved) is at"
            " or below their reorder threshold."
        ),
    ),
    ToolDefinition(
        name="get_order_status",
        description=(
            "Look up one order's status and total by its customer-facing order reference number."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reference": {
                    "type": "string",
                    "description": "The order's public reference number, exactly as shown.",
                }
            },
            "required": ["reference"],
        },
    ),
]


async def _run_tool(db: Database, actor: Principal, call: ToolCall) -> dict[str, Any]:
    try:
        if call.name == "count_pending_orders":
            return await _count_pending_orders(db, actor)
        if call.name == "count_low_stock_variants":
            return await _count_low_stock_variants(db, actor)
        if call.name == "get_order_status":
            reference = str(call.arguments.get("reference", "")).strip()
            if not reference:
                return {"error": "No order reference was given."}
            return await _get_order_status(db, actor, reference)
        return {"error": f"Unknown tool: {call.name}"}
    except PermissionDeniedError as exc:
        return {"error": str(exc)}


async def ask(
    db: Database,
    actor: Principal,
    chat: ChatModel,
    *,
    message: str,
    history: list[dict[str, str]],
) -> dict[str, Any]:
    """One turn of the admin support bot."""
    if not await support_bot_settings.is_enabled(db, "admin"):
        raise ChatUnavailableError(
            "The support bot is currently turned off. A super admin can turn it back"
            " on from Site Settings."
        )
    history_turns = await support_bot_settings.get_tuning(db, "historyTurns")
    trimmed_history = history[-history_turns:] if history_turns else []
    messages: list[dict[str, Any]] = [*trimmed_history, {"role": "user", "content": message}]
    system_prompt = await _build_system_prompt(db, message)

    completion = await chat.complete(system_prompt=system_prompt, messages=messages, tools=_TOOLS)
    if completion.text is not None:
        return {"reply": completion.text}

    # Exactly one round of tools, then a final answer -- not a loop. The model
    # is asked again with the results stated as plain text and no tools on
    # offer, so it has to reply in prose; see `tool_results_message` for why
    # the OpenAI-style tool-result messages cannot be used here.
    results = [(call, await _run_tool(db, actor, call)) for call in completion.tool_calls]
    final = await chat.complete(
        system_prompt=system_prompt,
        messages=[*messages, tool_results_message(results)],
        tools=None,
    )
    if final.text is None:
        return {
            "reply": (
                "I wasn't able to finish looking that up. Try rephrasing, or check"
                " the relevant admin page directly."
            )
        }
    return {"reply": final.text}

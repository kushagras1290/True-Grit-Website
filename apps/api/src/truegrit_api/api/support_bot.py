"""Admin support bot: available to any signed-in staff member (no extra
permission -- it's a help tool, and every live-data tool it can call
re-checks the caller's own permissions independently in
`services.support_bot`).

Also serves the knowledge-base management screen both bots' reference
material is edited from (`support_bot.manage`) -- see
`services.support_bot_knowledge`'s module docstring for why one screen
covers both the admin and storefront bot's knowledge via a `scope` filter
rather than two separate CRUD surfaces.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import (
    get_chat_model,
    get_current_staff,
    get_database,
    require_permission,
)
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.ai_chat import ChatModel
from truegrit_api.platform.database import Database
from truegrit_api.services import (
    support_bot,
    support_bot_knowledge,
    support_bot_operations,
    support_bot_settings,
)
from truegrit_api.services.support_bot_knowledge import Scope
from truegrit_api.services.support_bot_operations import EscalationStatus
from truegrit_api.services.support_bot_settings import BotScope, TuningKey

router = APIRouter(tags=["admin-support-bot"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatTurn(_CamelModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class SupportBotChatRequest(_CamelModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


class KnowledgeEntryRequest(_CamelModel):
    scope: Scope
    title: str = Field(min_length=1, max_length=120)
    keywords: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=2000)


class KnowledgeEntryUpdateRequest(_CamelModel):
    title: str = Field(min_length=1, max_length=120)
    keywords: str = Field(min_length=1, max_length=500)
    content: str = Field(min_length=1, max_length=2000)


class BotToggleRequest(_CamelModel):
    enabled: bool


class BotWidgetColorRequest(_CamelModel):
    """Blank clears the override and returns the widgets to the site brand colour."""

    widget_color: str = Field(default="", max_length=7)


class BotTuningRequest(_CamelModel):
    # Widest of the per-key ranges in services.support_bot_settings; that
    # module clamps to the specific key's own bounds. Anything past this is
    # rejected outright rather than silently stored as something else.
    value: int = Field(ge=0, le=12000)


class PolicyFactRequest(_CamelModel):
    """One standing fact the deterministic storefront bot quotes.

    Blank is meaningful and therefore allowed: it switches the wording that
    depends on this fact back off, which is how an operator retracts a figure
    that has changed before they know the replacement.
    """

    value: str = Field(default="", max_length=200)


class EscalationStatusRequest(_CamelModel):
    status: EscalationStatus
    note: str = Field(default="", max_length=2000)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.post("/support-bot/chat")
async def support_bot_chat(
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(get_current_staff)],
    chat: Annotated[ChatModel, Depends(get_chat_model)],
    body: SupportBotChatRequest,
) -> dict[str, Any]:
    return await support_bot.ask(
        db,
        actor,
        chat,
        message=body.message,
        history=[{"role": turn.role, "content": turn.content} for turn in body.history],
    )


# --- Knowledge base management (support_bot.manage) -------------------------
# The bot itself (above) is read-only over this data and available to any
# staff member; only these routes can change what either bot knows.

_ManageActor = Annotated[Principal, Depends(require_permission("support_bot.manage"))]


@router.get("/support-bot/knowledge")
async def list_knowledge(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    scope: Annotated[Scope | None, Query()] = None,
) -> list[dict[str, Any]]:
    return await support_bot_knowledge.list_entries(db, scope=scope)


@router.post("/support-bot/knowledge")
async def create_knowledge(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    body: KnowledgeEntryRequest,
) -> dict[str, Any]:
    return await support_bot_knowledge.create_entry(
        db,
        actor,
        _request_id(request),
        scope=body.scope,
        title=body.title,
        keywords=body.keywords,
        content=body.content,
    )


@router.patch("/support-bot/knowledge/{entry_id}")
async def update_knowledge(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    entry_id: str,
    body: KnowledgeEntryUpdateRequest,
) -> dict[str, Any]:
    return await support_bot_knowledge.update_entry(
        db,
        actor,
        _request_id(request),
        entry_id,
        title=body.title,
        keywords=body.keywords,
        content=body.content,
    )


@router.delete("/support-bot/knowledge/{entry_id}")
async def delete_knowledge(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    entry_id: str,
) -> dict[str, str]:
    await support_bot_knowledge.delete_entry(db, actor, _request_id(request), entry_id)
    return {"id": entry_id}


# --- On/off switches (support_bot.manage) -----------------------------------


@router.get("/support-bot/settings")
async def get_support_bot_settings(
    db: Annotated[Database, Depends(get_database)], actor: _ManageActor
) -> dict[str, Any]:
    return await support_bot_settings.get_all(db)


@router.patch("/support-bot/settings/{scope}")
async def set_support_bot_enabled(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    scope: BotScope,
    body: BotToggleRequest,
) -> dict[str, Any]:
    return await support_bot_settings.set_enabled(
        db, actor, _request_id(request), scope, body.enabled
    )


@router.patch("/support-bot/tuning/{key}")
async def set_support_bot_tuning(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    key: TuningKey,
    body: BotTuningRequest,
) -> dict[str, Any]:
    return await support_bot_settings.set_tuning(db, actor, _request_id(request), key, body.value)


@router.patch("/support-bot/widget-color")
async def set_support_bot_widget_color(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    body: BotWidgetColorRequest,
) -> dict[str, str]:
    return await support_bot_settings.set_widget_color(
        db, actor, _request_id(request), body.widget_color
    )


# --- Deterministic storefront bot: facts and escalations --------------------
# The storefront bot (truegrit_api.support_bot) has no prompt to tune. What it
# needs from an operator instead is the standing facts it quotes and attention
# on the conversations it could not finish.


@router.get("/support-bot/policy-facts")
async def list_policy_facts(
    db: Annotated[Database, Depends(get_database)], actor: _ManageActor
) -> list[dict[str, Any]]:
    return await support_bot_operations.list_facts(db)


@router.patch("/support-bot/policy-facts/{key}")
async def set_policy_fact(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    key: str,
    body: PolicyFactRequest,
) -> dict[str, Any]:
    return await support_bot_operations.set_fact(db, actor, _request_id(request), key, body.value)


@router.get("/support-bot/escalations")
async def list_escalations(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    status: Annotated[EscalationStatus | None, Query()] = "open",
    severity: Annotated[str | None, Query(pattern="^(normal|high|critical)$")] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return await support_bot_operations.list_escalations(
        db, status=status, severity=severity, limit=limit, offset=offset
    )


@router.get("/support-bot/escalations/summary")
async def escalation_summary(
    db: Annotated[Database, Depends(get_database)], actor: _ManageActor
) -> list[dict[str, Any]]:
    """Which intents keep escalating. The report that says what to fix next."""
    return await support_bot_operations.intent_summary(db)


@router.patch("/support-bot/escalations/{escalation_id}")
async def set_escalation_status(
    db: Annotated[Database, Depends(get_database)],
    actor: _ManageActor,
    request: Request,
    escalation_id: str,
    body: EscalationStatusRequest,
) -> dict[str, Any]:
    return await support_bot_operations.set_escalation_status(
        db,
        actor,
        _request_id(request),
        escalation_id,
        status=body.status,
        note=body.note,
    )

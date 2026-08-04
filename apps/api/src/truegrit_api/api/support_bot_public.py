"""Storefront support bot: open to anyone, signed in or not. Order-lookup
tools are simply omitted from what the model can call when there is no
signed-in customer (`services.support_bot_public`), not merely hidden in
the widget."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_chat_model, get_database, get_optional_customer
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.ai_chat import ChatModel
from truegrit_api.platform.database import Database
from truegrit_api.services import support_bot_public

router = APIRouter(tags=["storefront-support-bot"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatTurn(_CamelModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class SupportBotChatRequest(_CamelModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    # Same signal the storefront's own /search and geo-aware endpoints read
    # (see api/public.py's `_normalize_country`) -- lets search_site apply
    # the same geo-release filtering a normal browse/search request would.
    country: str | None = Field(default=None, max_length=2)
    locale: str | None = Field(default=None, max_length=10)


@router.post("/support-bot/chat")
async def support_bot_chat(
    db: Annotated[Database, Depends(get_database)],
    customer: Annotated[Principal | None, Depends(get_optional_customer)],
    chat: Annotated[ChatModel, Depends(get_chat_model)],
    body: SupportBotChatRequest,
) -> dict[str, Any]:
    return await support_bot_public.ask(
        db,
        customer,
        chat,
        message=body.message,
        history=[{"role": turn.role, "content": turn.content} for turn in body.history],
        country=body.country,
        locale=body.locale,
    )

"""Storefront support bot: open to anyone, signed in or not.

The handler is thin on purpose. Everything that decides what the customer is
told lives in `truegrit_api.support_bot`, which is a pure async pipeline over
the `Database` protocol -- no model binding, no `get_chat_model` dependency,
and therefore fully exercisable in the test suite.

Order-scoped answers are gated inside the pipeline (`IntentSpec.requires_auth`)
and the resolvers put `customer_user_id` in the WHERE clause themselves, so an
anonymous visitor is never in a position to read an order regardless of what
they type. Nothing here is enforcing that; this route only supplies who is
asking.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, get_optional_customer
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.support_bot import ask

router = APIRouter(tags=["storefront-support-bot"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ChatTurn(_CamelModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(min_length=1, max_length=4000)


class SupportBotChatRequest(_CamelModel):
    message: str = Field(min_length=1, max_length=2000)
    # History is only read to notice a customer asking the same thing twice
    # (`gate.is_repeat`), which escalates instead of clarifying again. It is
    # never replayed into an answer, because there is no prompt to replay it
    # into.
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    # Same signal the storefront's own /search and geo-aware endpoints read
    # (see api/public.py's `_normalize_country`), so catalogue answers apply
    # the same geo-release filtering a normal browse would.
    country: str | None = Field(default=None, max_length=2)
    locale: str | None = Field(default=None, max_length=10)


@router.post("/support-bot/chat")
async def support_bot_chat(
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    customer: Annotated[Principal | None, Depends(get_optional_customer)],
    body: SupportBotChatRequest,
) -> dict[str, Any]:
    return await ask(
        db,
        customer,
        message=body.message,
        history=[{"role": turn.role, "content": turn.content} for turn in body.history],
        request_id=getattr(request.state, "request_id", "unknown"),
        country=body.country,
        locale=body.locale,
    )

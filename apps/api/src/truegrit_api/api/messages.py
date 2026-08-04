"""Staff messaging: conversation/participant management and history reads.

Every route requires `messages.use` (you can use messaging at all). Routes
that reshape membership -- create, rename, add/remove participants -- also
call `require_owner`, hard-gating them to the `super_admin` role itself, the
same belt-and-suspenders technique `api.admin` uses for server logs and the
DB browser. See `services.messages` for why that is a role check and not a
second permission.

Sending a message is NOT a route here -- it happens over the WebSocket to
`realtime.chat_room.ChatRoomDO` (routed directly in `worker.py`, bypassing
FastAPI entirely). This router covers everything a client needs before that
socket is even open: the conversation list, history/scrollback, unread
tracking, and membership management.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_owner, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services import messages as message_service

router = APIRouter(tags=["admin-messages"])

_Actor = Annotated[Principal, Depends(require_permission("messages.use"))]
_Db = Annotated[Database, Depends(get_database)]


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CreateConversationRequest(_CamelModel):
    type: str = Field(pattern="^(group|direct)$")
    name: str | None = Field(default=None, max_length=120)
    participant_user_ids: list[str] = Field(min_length=1, max_length=200)


class RenameConversationRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=120)


class AddParticipantsRequest(_CamelModel):
    user_ids: list[str] = Field(min_length=1, max_length=200)


class MarkReadRequest(_CamelModel):
    last_read_message_id: str | None = None


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.get("/messages/conversations")
async def list_conversations(db: _Db, actor: _Actor) -> list[dict[str, Any]]:
    return await message_service.list_my_conversations(db, actor)


@router.get("/messages/conversations/{conversation_id}/history")
async def get_history(
    db: _Db,
    actor: _Actor,
    conversation_id: str,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict[str, Any]:
    return await message_service.get_conversation_history(
        db, actor, conversation_id, limit=limit, offset=offset
    )


@router.post("/messages/conversations/{conversation_id}/read")
async def mark_read(
    db: _Db, actor: _Actor, conversation_id: str, body: MarkReadRequest
) -> dict[str, Any]:
    return await message_service.mark_read(
        db, actor, conversation_id, last_read_message_id=body.last_read_message_id
    )


@router.post("/messages/conversations")
async def create_conversation(
    db: _Db, actor: _Actor, request: Request, body: CreateConversationRequest
) -> dict[str, Any]:
    await require_owner(db, actor)
    return await message_service.create_conversation(
        db,
        actor,
        _request_id(request),
        type_=body.type,
        name=body.name,
        participant_user_ids=body.participant_user_ids,
    )


@router.patch("/messages/conversations/{conversation_id}")
async def rename_conversation(
    db: _Db,
    actor: _Actor,
    request: Request,
    conversation_id: str,
    body: RenameConversationRequest,
) -> dict[str, Any]:
    await require_owner(db, actor)
    return await message_service.rename_conversation(
        db, actor, _request_id(request), conversation_id, name=body.name
    )


@router.post("/messages/conversations/{conversation_id}/participants")
async def add_participants(
    db: _Db,
    actor: _Actor,
    request: Request,
    conversation_id: str,
    body: AddParticipantsRequest,
) -> dict[str, Any]:
    await require_owner(db, actor)
    return await message_service.add_participants(
        db, actor, _request_id(request), conversation_id, user_ids=body.user_ids
    )


@router.delete("/messages/conversations/{conversation_id}/participants/{user_id}")
async def remove_participant(
    db: _Db, actor: _Actor, request: Request, conversation_id: str, user_id: str
) -> dict[str, Any]:
    await require_owner(db, actor)
    return await message_service.remove_participant(
        db, actor, _request_id(request), conversation_id, user_id
    )

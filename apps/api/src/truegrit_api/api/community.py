"""Community discussions: public reads, customer-authenticated writes.

Anyone (signed in or not) can browse visible discussions and their comments --
the same "public read, authenticated write" split as the rest of the
storefront's catalogue. Starting a thread or commenting requires
`get_current_customer`; `services.discussions` enforces the minimum-account-age
rule for starting a thread. Staff moderation lives in `api.admin`.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import DiscussionRepository
from truegrit_api.services.discussions import (
    create_comment,
    create_discussion,
    get_min_account_age_months,
)

router = APIRouter(tags=["storefront-community"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class DiscussionCreateRequest(_CamelModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class CommentCreateRequest(_CamelModel):
    body: str = Field(min_length=1, max_length=4_000)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _discussion_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "excerpt": row["body"][:240],
        "authorName": row["author_name"],
        "commentCount": row["comment_count"],
        "lastActivityAt": row["last_activity_at"],
        "createdAt": row["created_at"],
    }


@router.get("/community/settings")
async def community_settings(db: Annotated[Database, Depends(get_database)]) -> Any:
    return {"minAccountAgeMonths": await get_min_account_age_months(db)}


@router.get("/community/discussions")
async def list_discussions(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await DiscussionRepository(db).list_public(limit=limit, offset=offset)
    return {"items": [_discussion_summary(row) for row in rows], "limit": limit, "offset": offset}


@router.get("/community/discussions/{discussion_id}")
async def discussion_detail(
    discussion_id: str, db: Annotated[Database, Depends(get_database)]
) -> Any:
    repo = DiscussionRepository(db)
    row = await repo.get_public_detail(discussion_id)
    if row is None:
        raise NotFoundError("Discussion not found.")
    comments = await repo.list_comments_public(discussion_id)
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "authorName": row["author_name"],
        "commentCount": row["comment_count"],
        "lastActivityAt": row["last_activity_at"],
        "createdAt": row["created_at"],
        "comments": [
            {
                "id": comment["id"],
                "body": comment["body"],
                "authorName": comment["author_name"],
                "createdAt": comment["created_at"],
            }
            for comment in comments
        ],
    }


@router.post("/community/discussions")
async def create_discussion_endpoint(
    payload: DiscussionCreateRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await create_discussion(
        db, customer, _request_id(request), title=payload.title, body=payload.body
    )


@router.post("/community/discussions/{discussion_id}/comments")
async def create_comment_endpoint(
    discussion_id: str,
    payload: CommentCreateRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await create_comment(
        db, customer, _request_id(request), discussion_id, body=payload.body
    )

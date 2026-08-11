"""Community: discussion threads, and reader comments on blog posts/recipes.

Anyone (signed in or not) can browse visible discussions and their comments --
the same "public read, authenticated write" split as the rest of the
storefront's catalogue. Starting a thread or commenting requires
`get_current_customer`; `services.discussions` enforces the minimum-account-age
rule for starting a thread. Staff moderation lives in `api.admin`.

Comments on published articles and recipes live here too rather than in
`api.storefront`: they are the same conversation surface, authored by the same
customers and policed by the same `discussions.moderate` permission. What they
are *not* is the same table -- see migration 0043 for why a comment on a post
cannot be a `discussion_comments` row. Note the deliberate asymmetry with
threads: commenting on a post has no account-age requirement, because the
tenure rule exists to stop throwaway accounts *starting* conversations, and a
post's conversation is started by the editorial team.
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
from truegrit_api.services import content_comments
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
        "imageUrl": row["image_url"],
        "imageAlt": row["image_alt"],
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
    locale: Annotated[str | None, Query(max_length=35)] = None,
) -> Any:
    repository = DiscussionRepository(db)
    rows = await repository.list_public(limit=limit, offset=offset, locale=locale)
    return {
        "items": [_discussion_summary(row) for row in rows],
        "total": await repository.count_public(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/community/discussions/{discussion_id}")
async def discussion_detail(
    discussion_id: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=35)] = None,
) -> Any:
    repo = DiscussionRepository(db)
    row = await repo.get_public_detail(discussion_id, locale=locale)
    if row is None:
        raise NotFoundError("Discussion not found.")
    comments = await repo.list_comments_public(discussion_id, locale=locale)
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "imageUrl": row["image_url"],
        "imageAlt": row["image_alt"],
        "authorName": row["author_name"],
        "commentCount": row["comment_count"],
        "lastActivityAt": row["last_activity_at"],
        "createdAt": row["created_at"],
        "seo": {
            "title": row["title"],
            "description": row["body"][:240],
            "canonicalPath": f"/community/{row['id']}",
            "indexing": row["indexing_policy"],
            "keywords": None,
        },
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


@router.get("/content/{content_type}/{slug}/comments")
async def list_content_comments_endpoint(
    content_type: str,
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=35)] = None,
) -> Any:
    """The visible comment thread on a published article or recipe.

    `enabled` rides along with the list so the storefront can render an
    existing thread read-only when the owner has closed commenting, rather than
    hiding a conversation that already happened.
    """
    items = await content_comments.list_public_comments(db, content_type, slug, locale=locale)
    return {
        "items": items,
        "total": len(items),
        "enabled": await content_comments.is_enabled(db),
    }


@router.post("/content/{content_type}/{slug}/comments")
async def create_content_comment_endpoint(
    content_type: str,
    slug: str,
    payload: CommentCreateRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await content_comments.create_comment(
        db, customer, _request_id(request), content_type, slug, body=payload.body
    )

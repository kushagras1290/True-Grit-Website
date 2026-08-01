"""Customer-facing community blog/recipe submissions.

Every route requires a signed-in customer session (`get_current_customer`) --
confirmed product decision: no anonymous submissions, so a submission always
has a real account behind it. Reads are always scoped to the calling
customer's own submissions; staff review lives in `api.admin`.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.domain.phone import MAX_PHONE_INPUT_LENGTH
from truegrit_api.errors import NotFoundError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import ContentSubmissionRepository
from truegrit_api.services.submissions import create_submission, update_submission

router = APIRouter(tags=["storefront-submissions"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class IngredientInput(_CamelModel):
    label: str = Field(min_length=1, max_length=200)
    quantity_text: str = Field(default="", max_length=120)


class SubmissionCreateRequest(_CamelModel):
    content_type: str = Field(max_length=16)
    contact_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(min_length=3, max_length=254)
    # Required, not optional as it was: an editor's one clarifying question is
    # a phone call. `services.submissions` normalises it to E.164 and rejects
    # anything unringable with a message naming the expected format.
    contact_phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    title: str = Field(min_length=1, max_length=200)
    excerpt: str | None = Field(default=None, max_length=400)
    body: str = Field(min_length=1, max_length=40_000)
    prep_minutes: int | None = Field(default=None, ge=0, le=100_000)
    cook_minutes: int | None = Field(default=None, ge=0, le=100_000)
    servings: int | None = Field(default=None, ge=0, le=100_000)
    dietary_tags: list[str] = Field(default_factory=list, max_length=12)
    ingredients: list[IngredientInput] = Field(default_factory=list, max_length=40)
    steps: list[str] = Field(default_factory=list, max_length=30)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _submission_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "contentType": row["content_type"],
        "status": row["status"],
        "title": row["title"],
        "excerpt": row["excerpt"],
        "body": row["body"],
        "contactName": row["contact_name"],
        "contactEmail": row["contact_email"],
        "contactPhone": row["contact_phone"],
        "prepMinutes": row["prep_minutes"],
        "cookMinutes": row["cook_minutes"],
        "servings": row["servings"],
        "dietaryTags": _json_list(row["dietary_tags_json"]),
        "ingredients": _json_list(row["ingredients_json"]),
        "steps": _json_list(row["steps_json"]),
        "reviewerNotes": row["reviewer_notes"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "publishedArticleId": row["published_article_id"],
        "publishedRecipeId": row["published_recipe_id"],
    }


def _json_list(raw: str | None) -> list[Any]:
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []


@router.post("/submissions")
async def create_my_submission(
    payload: SubmissionCreateRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await create_submission(
        db,
        customer,
        _request_id(request),
        content_type=payload.content_type,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        title=payload.title,
        excerpt=payload.excerpt,
        body=payload.body,
        prep_minutes=payload.prep_minutes,
        cook_minutes=payload.cook_minutes,
        servings=payload.servings,
        dietary_tags=payload.dietary_tags,
        ingredients=[item.model_dump(by_alias=True) for item in payload.ingredients],
        steps=payload.steps,
    )


@router.get("/submissions")
async def my_submissions(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    rows = await ContentSubmissionRepository(db).list_for_customer(customer.user_id)
    return {"items": [_submission_detail(row) for row in rows]}


@router.get("/submissions/{submission_id}")
async def my_submission_detail(
    submission_id: str,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    row = await ContentSubmissionRepository(db).get_for_customer(customer.user_id, submission_id)
    if row is None:
        raise NotFoundError("Submission not found.")
    return _submission_detail(row)


@router.patch("/submissions/{submission_id}")
async def update_my_submission(
    submission_id: str,
    payload: SubmissionCreateRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await update_submission(
        db,
        customer,
        _request_id(request),
        submission_id,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        title=payload.title,
        excerpt=payload.excerpt,
        body=payload.body,
        prep_minutes=payload.prep_minutes,
        cook_minutes=payload.cook_minutes,
        servings=payload.servings,
        dietary_tags=payload.dietary_tags,
        ingredients=[item.model_dump(by_alias=True) for item in payload.ingredients],
        steps=payload.steps,
    )

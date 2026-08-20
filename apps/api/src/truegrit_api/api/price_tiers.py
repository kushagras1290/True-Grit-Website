"""Admin routes for country pricing brackets. See `services/price_tiers.py`
for how a bracket maps onto the existing `price_adjustments` engine."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services import price_tiers

router = APIRouter(tags=["price-tiers"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class BracketSave(_CamelModel):
    label: str = Field(min_length=1, max_length=80)
    percent: int = Field(ge=price_tiers.MIN_PERCENT, le=price_tiers.MAX_PERCENT)


class CountryAssign(_CamelModel):
    country_code: str = Field(min_length=2, max_length=2)
    bracket_id: str = Field(min_length=1)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.get("/price-tiers")
async def list_price_tiers(
    db: Annotated[Database, Depends(get_database)],
    _actor: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"brackets": await price_tiers.list_brackets(db)}


@router.post("/price-tiers")
async def create_price_tier(
    payload: BracketSave,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    bracket = await price_tiers.create_bracket(
        db, actor, _request_id(request), label=payload.label, percent=payload.percent
    )
    return {"bracket": bracket, "brackets": await price_tiers.list_brackets(db)}


@router.put("/price-tiers/{bracket_id}")
async def update_price_tier(
    bracket_id: str,
    payload: BracketSave,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    bracket = await price_tiers.update_bracket(
        db, actor, _request_id(request), bracket_id, label=payload.label, percent=payload.percent
    )
    return {"bracket": bracket, "brackets": await price_tiers.list_brackets(db)}


@router.delete("/price-tiers/{bracket_id}")
async def delete_price_tier(
    bracket_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await price_tiers.delete_bracket(db, actor, _request_id(request), bracket_id)
    return {"brackets": await price_tiers.list_brackets(db)}


@router.post("/price-tiers/countries")
async def assign_price_tier_country(
    payload: CountryAssign,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await price_tiers.assign_country(
        db,
        actor,
        _request_id(request),
        country_code=payload.country_code,
        bracket_id=payload.bracket_id,
    )
    return {"brackets": await price_tiers.list_brackets(db)}


@router.delete("/price-tiers/countries/{country_code}")
async def unassign_price_tier_country(
    country_code: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await price_tiers.unassign_country(db, actor, _request_id(request), country_code=country_code)
    return {"brackets": await price_tiers.list_brackets(db)}

"""Public display rates and their audited admin controls."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services import currency_rates

admin_router = APIRouter(tags=["currency-rates"])
public_router = APIRouter(tags=["currency-rates"])


class CurrencyRateSave(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    currency_code: str = Field(min_length=3, max_length=3)
    locale: str = Field(min_length=2, max_length=35)
    rate_per_inr: Decimal
    active: bool = True


@public_router.get("/currency-rates")
async def public_currency_rates(
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return {"baseCurrency": "INR", "rates": await currency_rates.list_rates(db, active_only=True)}


@admin_router.get("/currency-rates")
async def admin_currency_rates(
    db: Annotated[Database, Depends(get_database)],
    _actor: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"baseCurrency": "INR", "rates": await currency_rates.list_rates(db)}


@admin_router.put("/currency-rates/{currency_code}")
async def update_currency_rate(
    currency_code: str,
    payload: CurrencyRateSave,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    actor: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    if payload.currency_code.upper() != currency_code.upper():
        from truegrit_api.errors import ValidationAppError

        raise ValidationAppError("The URL and submitted currency code must match.")
    saved = await currency_rates.save_rate(
        db,
        actor,
        getattr(request.state, "request_id", "unknown"),
        currency_code=currency_code,
        locale=payload.locale,
        rate_per_inr=payload.rate_per_inr,
        active=payload.active,
    )
    return {"rate": saved}

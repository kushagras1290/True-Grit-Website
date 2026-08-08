"""Customer-facing endpoints for the catalogue-expansion features."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services import b2b, delivery_zones, loyalty, pickup_points, preorders
from truegrit_api.services.feature_settings import (
    b2b_enabled,
    delivery_zones_enabled,
    loyalty_enabled,
    pickup_enabled,
    preorders_enabled,
)

router = APIRouter(tags=["storefront-expanded-commerce"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ReferralCodeRequest(_CamelModel):
    referral_code: str = Field(min_length=4, max_length=32)


async def _require_enabled(db: Database, enabled: bool, feature: str) -> None:
    if not enabled:
        raise ValidationAppError(f"{feature} is not available right now.")


@router.get("/loyalty")
async def get_loyalty_account(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await _require_enabled(db, await loyalty_enabled(db), "Loyalty rewards")
    account = await loyalty.get_customer_loyalty(db, customer.user_id)
    account["transactions"] = (
        await loyalty.get_transaction_history(db, customer.user_id, limit=50)
    )["items"]
    return account


@router.post("/loyalty/referral")
async def redeem_referral_code(
    payload: ReferralCodeRequest,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await _require_enabled(db, await loyalty_enabled(db), "Loyalty rewards")
    return await loyalty.apply_referral_code(db, customer.user_id, payload.referral_code)


@router.get("/pickup-points")
async def list_public_pickup_points(
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await _require_enabled(db, await pickup_enabled(db), "Local pickup")
    return await pickup_points.list_pickup_points(db, active_only=True, limit=100)


@router.get("/delivery/check")
async def check_delivery_area(
    db: Annotated[Database, Depends(get_database)],
    postal_code: Annotated[str, Query(alias="postalCode", min_length=1, max_length=20)],
) -> Any:
    await _require_enabled(db, await delivery_zones_enabled(db), "Delivery zones")
    return await delivery_zones.check_delivery(db, postal_code)


@router.get("/delivery/zones/{zone_id}/slots")
async def list_public_delivery_slots(
    zone_id: str,
    db: Annotated[Database, Depends(get_database)],
    delivery_date: Annotated[str, Query(alias="deliveryDate", min_length=10, max_length=10)],
) -> Any:
    await _require_enabled(db, await delivery_zones_enabled(db), "Delivery zones")
    return {
        "items": await delivery_zones.get_available_slots(db, zone_id, delivery_date)
    }


@router.get("/seasonal-calendar")
async def get_seasonal_calendar(
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await _require_enabled(db, await preorders_enabled(db), "Seasonal pre-orders")
    return {"items": await preorders.get_public_seasonal_calendar(db)}


@router.get("/b2b/account")
async def get_customer_b2b_account(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await _require_enabled(db, await b2b_enabled(db), "Business ordering")
    return {"account": await b2b.is_b2b_customer(db, customer.user_id)}


@router.get("/b2b/price-breaks")
async def list_customer_price_breaks(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
    variant_id: Annotated[str | None, Query(alias="variantId", max_length=64)] = None,
) -> Any:
    await _require_enabled(db, await b2b_enabled(db), "Business ordering")
    if await b2b.is_b2b_customer(db, customer.user_id) is None:
        return {"items": [], "total": 0, "limit": 100, "offset": 0}
    return await b2b.list_price_breaks(db, variant_id=variant_id, limit=100)

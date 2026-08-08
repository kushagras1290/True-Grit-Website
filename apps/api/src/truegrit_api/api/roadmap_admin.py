"""Permission-gated administration for expanded commerce features."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services import b2b, delivery_zones, loyalty, pickup_points, preorders

router = APIRouter(tags=["admin-expanded-commerce"])


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _updates(payload: BaseModel) -> dict[str, Any]:
    return payload.model_dump(by_alias=True, exclude_unset=True)


class LoyaltyAdjustmentRequest(_CamelModel):
    customer_user_id: str = Field(min_length=1, max_length=64)
    points: int = Field(ge=-1_000_000, le=1_000_000)
    reason: str = Field(min_length=2, max_length=300)


@router.get("/loyalty/accounts")
async def list_loyalty_accounts(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("loyalty.view"))],
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await loyalty.list_loyalty_accounts(db, search=search, limit=limit, offset=offset)


@router.get("/loyalty/referrals")
async def list_loyalty_referrals(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("loyalty.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await loyalty.list_referrals(db, limit=limit, offset=offset)


@router.post("/loyalty/adjustments")
async def adjust_loyalty_points(
    payload: LoyaltyAdjustmentRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("loyalty.manage"))],
) -> Any:
    return await loyalty.admin_adjust_points(
        db,
        principal,
        _request_id(request),
        customer_user_id=payload.customer_user_id,
        points=payload.points,
        reason=payload.reason,
    )


class PickupPointCreateRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=160)
    address: dict[str, Any] = Field(default_factory=dict)
    hours: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class PickupPointUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    address: dict[str, Any] | None = None
    hours: str | None = Field(default=None, max_length=500)
    phone: str | None = Field(default=None, max_length=32)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    status: Literal["active", "inactive"] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


@router.get("/pickup-points")
async def list_admin_pickup_points(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pickup_points.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await pickup_points.list_pickup_points(db, limit=limit, offset=offset)


@router.post("/pickup-points")
async def create_pickup_point(
    payload: PickupPointCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("pickup_points.manage"))],
) -> Any:
    return await pickup_points.create_pickup_point(
        db, principal, _request_id(request), **payload.model_dump()
    )


@router.patch("/pickup-points/{point_id}")
async def update_pickup_point(
    point_id: str,
    payload: PickupPointUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("pickup_points.manage"))],
) -> Any:
    return await pickup_points.update_pickup_point(
        db, principal, _request_id(request), point_id, updates=_updates(payload)
    )


@router.delete("/pickup-points/{point_id}")
async def delete_pickup_point(
    point_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("pickup_points.manage"))],
) -> Any:
    await pickup_points.delete_pickup_point(db, principal, _request_id(request), point_id)
    return {"deleted": True}


class HarvestWindowCreateRequest(_CamelModel):
    product_id: str = Field(min_length=1, max_length=64)
    expected_start: str = Field(min_length=10, max_length=32)
    expected_end: str = Field(min_length=10, max_length=32)
    title: str | None = Field(default=None, max_length=160)
    max_preorders: int | None = Field(default=None, ge=1, le=1_000_000)
    notes: str | None = Field(default=None, max_length=2_000)


class HarvestWindowUpdateRequest(_CamelModel):
    title: str | None = Field(default=None, max_length=160)
    expected_start: str | None = Field(default=None, min_length=10, max_length=32)
    expected_end: str | None = Field(default=None, min_length=10, max_length=32)
    actual_start: str | None = Field(default=None, max_length=32)
    actual_end: str | None = Field(default=None, max_length=32)
    max_preorders: int | None = Field(default=None, ge=1, le=1_000_000)
    status: Literal["upcoming", "active", "harvesting", "completed", "cancelled"] | None = None
    notes: str | None = Field(default=None, max_length=2_000)


@router.get("/harvest-windows")
async def list_harvest_windows(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("preorders.view"))],
    product_id: Annotated[str | None, Query(alias="productId", max_length=64)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await preorders.list_harvest_windows(
        db, product_id=product_id, status=status, limit=limit, offset=offset
    )


@router.post("/harvest-windows")
async def create_harvest_window(
    payload: HarvestWindowCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("preorders.manage"))],
) -> Any:
    return await preorders.create_harvest_window(
        db, principal, _request_id(request), **payload.model_dump()
    )


@router.patch("/harvest-windows/{window_id}")
async def update_harvest_window(
    window_id: str,
    payload: HarvestWindowUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("preorders.manage"))],
) -> Any:
    return await preorders.update_harvest_window(
        db, principal, _request_id(request), window_id, updates=_updates(payload)
    )


@router.delete("/harvest-windows/{window_id}")
async def delete_harvest_window(
    window_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("preorders.manage"))],
) -> Any:
    await preorders.delete_harvest_window(db, principal, _request_id(request), window_id)
    return {"deleted": True}


@router.get("/preorders")
async def list_preorders(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("preorders.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    harvest_window_id: Annotated[
        str | None, Query(alias="harvestWindowId", max_length=64)
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await preorders.list_preorders(
        db,
        status=status,
        harvest_window_id=harvest_window_id,
        limit=limit,
        offset=offset,
    )


@router.post("/harvest-windows/{window_id}/ready")
async def mark_harvest_ready(
    window_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("preorders.manage"))],
) -> Any:
    count = await preorders.mark_preorders_ready(
        db, principal, _request_id(request), window_id
    )
    return {"updated": count}


@router.post("/preorders/{preorder_id}/fulfill")
async def fulfill_preorder(
    preorder_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("preorders.manage"))],
) -> Any:
    return await preorders.fulfill_preorder(
        db, principal, _request_id(request), preorder_id
    )


class DeliveryZoneCreateRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=160)
    postal_codes: list[str] = Field(default_factory=list, max_length=500)
    fee_override_minor: int | None = Field(default=None, ge=0, le=10_000_000)
    free_threshold_override_minor: int | None = Field(default=None, ge=0, le=10_000_000)
    lead_time_hours: int = Field(default=24, ge=0, le=2_160)
    sort_order: int = Field(default=0, ge=0, le=10_000)


class DeliveryZoneUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    postal_codes: list[str] | None = Field(default=None, max_length=500)
    fee_override_minor: int | None = Field(default=None, ge=0, le=10_000_000)
    free_threshold_override_minor: int | None = Field(default=None, ge=0, le=10_000_000)
    lead_time_hours: int | None = Field(default=None, ge=0, le=2_160)
    status: Literal["active", "inactive"] | None = None
    sort_order: int | None = Field(default=None, ge=0, le=10_000)


class DeliverySlotCreateRequest(_CamelModel):
    day_of_week: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    max_orders: int = Field(default=20, ge=1, le=10_000)


class DeliverySlotUpdateRequest(_CamelModel):
    day_of_week: int | None = Field(default=None, ge=0, le=6)
    start_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    end_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    max_orders: int | None = Field(default=None, ge=1, le=10_000)
    status: Literal["active", "inactive"] | None = None


@router.get("/delivery-zones")
async def list_delivery_zones(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("delivery_zones.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await delivery_zones.list_zones(db, limit=limit, offset=offset)


@router.post("/delivery-zones")
async def create_delivery_zone(
    payload: DeliveryZoneCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    return await delivery_zones.create_zone(
        db, principal, _request_id(request), **payload.model_dump()
    )


@router.patch("/delivery-zones/{zone_id}")
async def update_delivery_zone(
    zone_id: str,
    payload: DeliveryZoneUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    return await delivery_zones.update_zone(
        db, principal, _request_id(request), zone_id, updates=_updates(payload)
    )


@router.delete("/delivery-zones/{zone_id}")
async def delete_delivery_zone(
    zone_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    await delivery_zones.delete_zone(db, principal, _request_id(request), zone_id)
    return {"deleted": True}


@router.get("/delivery-zones/{zone_id}/slots")
async def list_delivery_slots(
    zone_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("delivery_zones.view"))],
) -> Any:
    return {"items": await delivery_zones.list_slots(db, zone_id)}


@router.post("/delivery-zones/{zone_id}/slots")
async def create_delivery_slot(
    zone_id: str,
    payload: DeliverySlotCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    return await delivery_zones.create_slot(
        db, principal, _request_id(request), zone_id=zone_id, **payload.model_dump()
    )


@router.patch("/delivery-slots/{slot_id}")
async def update_delivery_slot(
    slot_id: str,
    payload: DeliverySlotUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    return await delivery_zones.update_slot(
        db, principal, _request_id(request), slot_id, updates=_updates(payload)
    )


@router.delete("/delivery-slots/{slot_id}")
async def delete_delivery_slot(
    slot_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("delivery_zones.manage"))],
) -> Any:
    await delivery_zones.delete_slot(db, principal, _request_id(request), slot_id)
    return {"deleted": True}


class B2BAccountCreateRequest(_CamelModel):
    company_name: str = Field(min_length=1, max_length=200)
    gst_number: str | None = Field(default=None, max_length=40)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=32)
    credit_limit_minor: int = Field(default=0, ge=0, le=1_000_000_000)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    notes: str | None = Field(default=None, max_length=2_000)


class B2BAccountUpdateRequest(_CamelModel):
    company_name: str | None = Field(default=None, min_length=1, max_length=200)
    gst_number: str | None = Field(default=None, max_length=40)
    contact_name: str | None = Field(default=None, max_length=160)
    contact_email: str | None = Field(default=None, max_length=254)
    contact_phone: str | None = Field(default=None, max_length=32)
    credit_limit_minor: int | None = Field(default=None, ge=0, le=1_000_000_000)
    payment_terms_days: int | None = Field(default=None, ge=0, le=365)
    status: Literal["pending", "active", "suspended"] | None = None
    notes: str | None = Field(default=None, max_length=2_000)


class B2BLinkUserRequest(_CamelModel):
    user_id: str = Field(min_length=1, max_length=64)


class PriceBreakCreateRequest(_CamelModel):
    variant_id: str = Field(min_length=1, max_length=64)
    min_quantity: int = Field(ge=1, le=1_000_000)
    price_minor: int = Field(ge=0, le=1_000_000_000)


class InvoicePaidRequest(_CamelModel):
    payment_reference: str | None = Field(default=None, max_length=160)


@router.get("/b2b/accounts")
async def list_b2b_accounts(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("b2b.view"))],
    search: Annotated[str | None, Query(max_length=160)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await b2b.list_b2b_accounts(db, search=search, limit=limit, offset=offset)


@router.post("/b2b/accounts")
async def create_b2b_account(
    payload: B2BAccountCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    return await b2b.create_b2b_account(
        db, principal, _request_id(request), **payload.model_dump()
    )


@router.patch("/b2b/accounts/{account_id}")
async def update_b2b_account(
    account_id: str,
    payload: B2BAccountUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    return await b2b.update_b2b_account(
        db, principal, _request_id(request), account_id, updates=_updates(payload)
    )


@router.post("/b2b/accounts/{account_id}/users")
async def link_b2b_user(
    account_id: str,
    payload: B2BLinkUserRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    await b2b.link_user_to_b2b(
        db,
        principal,
        _request_id(request),
        user_id=payload.user_id,
        b2b_account_id=account_id,
    )
    return {"linked": True}


@router.get("/b2b/price-breaks")
async def list_b2b_price_breaks(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("b2b.view"))],
    variant_id: Annotated[str | None, Query(alias="variantId", max_length=64)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await b2b.list_price_breaks(
        db, variant_id=variant_id, limit=limit, offset=offset
    )


@router.post("/b2b/price-breaks")
async def create_b2b_price_break(
    payload: PriceBreakCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    return await b2b.create_price_break(
        db, principal, _request_id(request), **payload.model_dump()
    )


@router.delete("/b2b/price-breaks/{break_id}")
async def delete_b2b_price_break(
    break_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    await b2b.delete_price_break(db, principal, _request_id(request), break_id)
    return {"deleted": True}


@router.get("/b2b/invoices")
async def list_b2b_invoices(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("b2b.view"))],
    account_id: Annotated[str | None, Query(alias="accountId", max_length=64)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    return await b2b.list_invoices(
        db,
        b2b_account_id=account_id,
        status=status,
        limit=limit,
        offset=offset,
    )


@router.post("/b2b/invoices/{invoice_id}/paid")
async def mark_b2b_invoice_paid(
    invoice_id: str,
    payload: InvoicePaidRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("b2b.manage"))],
) -> Any:
    return await b2b.mark_invoice_paid(
        db,
        principal,
        _request_id(request),
        invoice_id,
        payment_reference=payload.payment_reference,
    )

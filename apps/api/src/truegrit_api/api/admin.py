"""Admin endpoints. Every route enforces a permission — UI hiding is not authorization."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request

from truegrit_api.auth.dependencies import get_current_staff, get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.repositories.admin import AdminRepository
from truegrit_api.repositories.content import AuditRepository, CategoryRepository
from truegrit_api.services.publishing import publish_category

router = APIRouter(tags=["admin"])


@router.get("/me")
async def me(principal: Annotated[Principal, Depends(get_current_staff)]) -> Any:
    return {
        "id": principal.user_id,
        "displayName": principal.display_name,
        "email": principal.email,
        "permissions": sorted(principal.permissions),
    }


@router.get("/products")
async def list_products(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("products.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AdminRepository(db).list_products(limit=limit, offset=offset)
    items = []
    for row in rows:
        min_price = row["min_price_minor"]
        max_price = row["max_price_minor"]
        if min_price is None:
            price_range = "—"
        elif min_price == max_price:
            price_range = f"{min_price / 100:.0f}"
        else:
            price_range = f"{min_price / 100:.0f}-{max_price / 100:.0f}"
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "sku": row["sku"] or "—",
                "status": row["status"],
                "categories": (row["categories"] or "").split(", ") if row["categories"] else [],
                "farmName": row["farm_name"],
                "priceRange": price_range,
                "availableStock": row["available_stock"],
                "updatedAt": row["updated_at"],
                "updatedBy": row["updated_by"] or "—",
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/categories")
async def list_categories(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("categories.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AdminRepository(db).list_categories(limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "parentName": row["parent_name"],
                "productCount": row["product_count"],
                "visibility": row["visibility"],
                "status": row["status"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("/categories/{category_id}/publish")
async def publish_category_endpoint(
    category_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.publish"))],
) -> Any:
    return await publish_category(
        db,
        CategoryRepository(db),
        category_id,
        principal,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


@router.get("/inventory")
async def list_inventory(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("inventory.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AdminRepository(db).list_inventory(limit=limit, offset=offset)
    return {
        "items": [
            {
                "variantId": row["variant_id"],
                "productName": row["product_name"],
                "variantName": row["variant_name"],
                "sku": row["sku"],
                "locationName": row["location_name"],
                "onHand": row["on_hand"],
                "reserved": row["reserved"],
                "reorderThreshold": row["reorder_threshold"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit")
async def audit_log(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Any:
    rows = await AuditRepository(db).recent(limit=limit)
    return {
        "items": [
            {
                "id": row["id"],
                "actorName": row["actor_name"],
                "action": row["action"],
                "entityType": row["entity_type"],
                "entityId": row["entity_id"],
                "requestId": row["request_id"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ]
    }

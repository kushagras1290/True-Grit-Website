"""Demand-forecast admin APIs and public recommendation APIs."""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, PermissionDeniedError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.schemas.public import ProductSummary
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.demand_forecasting import (
    load_inventory_intelligence,
    recompute_demand_forecasts,
)
from truegrit_api.services.feature_settings import recommendations_enabled
from truegrit_api.services.recommendations import (
    ranked_recommendations,
    recompute_recommendations,
    record_event,
)
from truegrit_api.util.timeutil import utc_now_iso

admin_router = APIRouter(tags=["inventory-intelligence"])
public_router = APIRouter(tags=["storefront-recommendations"])
_COUNTRY_PATTERN = re.compile(r"^[A-Za-z]{2}$")


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ForecastSettingsUpdate(_CamelModel):
    lead_time_days: int = Field(ge=1, le=90)
    safety_stock_days: int = Field(ge=0, le=30)


class RecommendationMeta(_CamelModel):
    run_id: str | None = None
    source_product_id: str
    score: float = Field(ge=0)
    confidence: float = Field(ge=0)
    lift: float = Field(ge=0)
    cosine_similarity: float = Field(ge=0)
    reason: Literal["frequently_bought_together", "similar_product", "trending"]


class RecommendedProduct(_CamelModel):
    product: ProductSummary
    recommendation: RecommendationMeta


class RecommendationResponse(_CamelModel):
    items: list[RecommendedProduct]
    total: int
    run_id: str | None = None


class RecommendationEventRequest(_CamelModel):
    visitor_session_id: str = Field(min_length=8, max_length=80)
    source_product_id: str | None = Field(default=None, max_length=64)
    recommended_product_id: str = Field(max_length=64)
    recommendation_run_id: str | None = Field(default=None, max_length=64)
    placement: Literal["product", "cart", "homepage", "category", "shop", "order"]
    event_type: Literal["impression", "click", "add_to_cart"]


def _normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    if not _COUNTRY_PATTERN.fullmatch(country):
        raise ValidationAppError("Country must be a two-letter ISO code.")
    return country.upper()


async def _assert_variant_scope(db: Database, variant_id: str, principal: Principal) -> None:
    row = await db.fetch_one(
        "SELECT p.farm_id FROM product_variants v JOIN products p ON p.id = v.product_id"
        " WHERE v.id = ?",
        (variant_id,),
    )
    if row is None:
        raise NotFoundError("Variant not found.")
    if principal.farm_id is not None and row["farm_id"] != principal.farm_id:
        raise PermissionDeniedError("This variant is outside your farm scope.")


@admin_router.get("/inventory-intelligence")
async def inventory_intelligence(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.view"))],
) -> Any:
    return await load_inventory_intelligence(db, farm_id=principal.farm_id)


@admin_router.get("/inventory-intelligence/{variant_id}/forecast")
async def variant_forecast(
    variant_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.view"))],
) -> Any:
    await _assert_variant_scope(db, variant_id, principal)
    run = await db.fetch_one(
        "SELECT id FROM demand_forecast_runs WHERE status = 'completed'"
        " ORDER BY completed_at DESC LIMIT 1"
    )
    if run is None:
        return {"items": [], "runId": None}
    rows = await db.fetch_all(
        "SELECT forecast_date, predicted_units, lower_units, upper_units,"
        " seasonality_multiplier FROM demand_forecasts"
        " WHERE run_id = ? AND variant_id = ? ORDER BY forecast_date",
        (run["id"], variant_id),
    )
    return {
        "runId": run["id"],
        "items": [
            {
                "forecastDate": row["forecast_date"],
                "predictedUnits": float(row["predicted_units"]),
                "lowerUnits": float(row["lower_units"]),
                "upperUnits": float(row["upper_units"]),
                "seasonalityMultiplier": float(row["seasonality_multiplier"]),
            }
            for row in rows
        ],
    }


@admin_router.patch("/inventory-intelligence/{variant_id}/settings")
async def update_forecast_settings(
    variant_id: str,
    payload: ForecastSettingsUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.adjust"))],
) -> Any:
    await _assert_variant_scope(db, variant_id, principal)
    now = utc_now_iso()
    request_id = getattr(request.state, "request_id", "unknown")
    await db.batch(
        [
            (
                "INSERT INTO inventory_forecast_settings"
                " (variant_id, lead_time_days, safety_stock_days, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?) ON CONFLICT(variant_id) DO UPDATE SET"
                " lead_time_days = excluded.lead_time_days,"
                " safety_stock_days = excluded.safety_stock_days,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (
                    variant_id,
                    payload.lead_time_days,
                    payload.safety_stock_days,
                    now,
                    principal.user_id,
                ),
            ),
            audit_statement(
                action="inventory.forecast_settings_updated",
                entity_type="product_variant",
                entity_id=variant_id,
                actor_id=principal.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "leadTimeDays": payload.lead_time_days,
                    "safetyStockDays": payload.safety_stock_days,
                },
            ),
        ]
    )
    return {
        "variantId": variant_id,
        "leadTimeDays": payload.lead_time_days,
        "safetyStockDays": payload.safety_stock_days,
    }


@admin_router.post("/inventory-intelligence/recompute")
async def recompute_forecasts_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.adjust"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only store-wide operators can recompute all forecasts.")
    return await recompute_demand_forecasts(db)


@admin_router.post("/recommendations/recompute")
async def recompute_recommendations_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("analytics.view"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only store-wide operators can recompute recommendations.")
    return await recompute_recommendations(db)


@public_router.get("/products/{product_ref}/recommendations", response_model=RecommendationResponse)
async def product_recommendations(
    product_ref: str,
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=24)] = 6,
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    if not await recommendations_enabled(db):
        return {"items": [], "total": 0, "runId": None}
    source = await db.fetch_one(
        "SELECT id, slug FROM products WHERE (id = ? OR slug = ?) AND status = 'published' LIMIT 1",
        (product_ref, product_ref),
    )
    if source is None:
        raise NotFoundError("Product not found.")
    # Fetch spare candidates because catalogue resolution may drop products
    # that are unpublished, geo-hidden or currently out of stock.
    run_id, ranked = await ranked_recommendations(db, str(source["id"]), limit=min(limit * 3, 72))
    repository = CatalogueRepository(db)
    visitor_country = _normalize_country(country)
    if ranked:
        product_ids = [str(row["recommended_product_id"]) for row in ranked]
        products = await repository.resolve_ranked_product_ids(
            product_ids, country=visitor_country, locale=locale
        )
        product_by_id = {
            str(product["id"]): product
            for product in products
            if product["availability"] != "out_of_stock" and product["accepts_orders"]
        }
        items = []
        for row in ranked:
            product = product_by_id.get(str(row["recommended_product_id"]))
            if product is None:
                continue
            items.append(
                {
                    "product": product,
                    "recommendation": {
                        "runId": run_id,
                        "sourceProductId": source["id"],
                        "score": float(row["blended_score"]),
                        "confidence": float(row["confidence"]),
                        "lift": float(row["lift"]),
                        "cosineSimilarity": float(row["cosine_similarity"]),
                        "reason": row["reason"],
                    },
                }
            )
    else:
        # Before the first nightly refresh (or with too little order history),
        # never leave a new SKU's module blank: popularity is the cold-start
        # tier and the source product is excluded from its own row.
        products = await repository.list_bestsellers(
            limit=limit,
            exclude_slugs=[str(source["slug"])],
            country=visitor_country,
            locale=locale,
        )
        products = [
            product
            for product in products
            if product["availability"] != "out_of_stock" and product["accepts_orders"]
        ]
        items = [
            {
                "product": product,
                "recommendation": {
                    "runId": run_id,
                    "sourceProductId": source["id"],
                    "score": 0.0,
                    "confidence": 0.0,
                    "lift": 0.0,
                    "cosineSimilarity": 0.0,
                    "reason": "trending",
                },
            }
            for product in products
        ]
    items = items[:limit]
    return {"items": items, "total": len(items), "runId": run_id}


@public_router.post("/recommendation-events", status_code=202)
async def recommendation_event(
    payload: RecommendationEventRequest,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    event_id = await record_event(
        db,
        visitor_session_id=payload.visitor_session_id,
        source_product_id=payload.source_product_id,
        recommended_product_id=payload.recommended_product_id,
        recommendation_run_id=payload.recommendation_run_id,
        placement=payload.placement,
        event_type=payload.event_type,
    )
    return {"id": event_id, "accepted": True}

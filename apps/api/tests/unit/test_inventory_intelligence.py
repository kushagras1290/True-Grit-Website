from __future__ import annotations

import asyncio
from datetime import date, timedelta

from truegrit_api.platform.database import build_local_database
from truegrit_api.services.demand_forecasting import (
    _forecast_variant,
    load_inventory_intelligence,
    recompute_demand_forecasts,
)
from truegrit_api.services.recommendations import (
    ranked_recommendations,
    recommendation_metrics,
    recompute_recommendations,
    record_event,
)


def test_forecast_applies_weekday_seasonality_and_flags_lead_time_risk() -> None:
    today = date(2026, 8, 17)  # Monday
    sales: dict[date, int] = {}
    for offset in range(56):
        day = today - timedelta(days=offset)
        sales[day] = 8 if day.weekday() in {5, 6} else 2

    points, summary = _forecast_variant(
        sales,
        today=today,
        available=10,
        reorder_threshold=3,
        lead_time_days=7,
        safety_stock_days=2,
    )

    saturday = next(
        point for point in points if date.fromisoformat(point["forecast_date"]).weekday() == 5
    )
    tuesday = next(
        point for point in points if date.fromisoformat(point["forecast_date"]).weekday() == 1
    )
    assert saturday["seasonality_multiplier"] > tuesday["seasonality_multiplier"]
    assert saturday["upper_units"] >= saturday["predicted_units"] >= saturday["lower_units"]
    assert summary["reorder_recommended"] == 1
    assert summary["recommended_order_units"] > 0
    assert summary["days_until_stockout"] is not None


def test_empty_history_is_safe_and_does_not_invent_demand() -> None:
    points, summary = _forecast_variant(
        {},
        today=date(2026, 8, 17),
        available=20,
        reorder_threshold=2,
        lead_time_days=7,
        safety_stock_days=2,
    )
    assert all(point["predicted_units"] == 0 for point in points)
    assert summary["days_until_stockout"] is None
    assert summary["reorder_recommended"] == 0


def test_completed_rollups_are_queryable_from_real_migrations_and_seed() -> None:
    async def scenario() -> None:
        db = build_local_database()
        forecast_run = await recompute_demand_forecasts(db, today=date(2026, 8, 17))
        intelligence = await load_inventory_intelligence(db)
        assert forecast_run["forecasts"] == forecast_run["variants"] * 30
        assert intelligence["run"]["id"] == forecast_run["runId"]
        assert len(intelligence["items"]) == forecast_run["variants"]

        recommendation_run = await recompute_recommendations(db)
        source = await db.fetch_one(
            "SELECT source_product_id FROM product_cooccurrence WHERE run_id = ? LIMIT 1",
            (recommendation_run["runId"],),
        )
        assert source is not None
        run_id, ranked = await ranked_recommendations(db, source["source_product_id"], limit=3)
        assert run_id == recommendation_run["runId"]
        assert ranked

        target = ranked[0]["recommended_product_id"]
        await record_event(
            db,
            visitor_session_id="visitor-test-123",
            source_product_id=source["source_product_id"],
            recommended_product_id=target,
            recommendation_run_id=run_id,
            placement="product",
            event_type="impression",
        )
        metrics = await recommendation_metrics(db, from_date="2026-01-01", to_date="2026-12-31")
        assert metrics["impressions"] == 1

    asyncio.run(scenario())

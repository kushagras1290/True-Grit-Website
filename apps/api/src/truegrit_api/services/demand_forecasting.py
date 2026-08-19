"""Interpretable SKU demand forecasting for inventory planning.

The model intentionally stays at the requested baseline: a 7/30-day moving
average blend, shrunk weekday seasonality and a residual-based interval. It is
cheap enough for a weekly Worker cron, works with sparse launches, and leaves
every number explainable to an operator. Completed runs are immutable; readers
only select the latest completed run.
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from statistics import pstdev
from typing import Any, Final

from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

MODEL_VERSION: Final = "moving-average-weekday-v1"
HORIZON_DAYS: Final = 30
HISTORY_DAYS: Final = 180
_BATCH_SIZE: Final = 75


def _parse_day(value: str) -> date:
    return datetime.strptime(value[:10], "%Y-%m-%d").replace(tzinfo=UTC).date()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


async def _write_chunks(db: Database, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
    for start in range(0, len(statements), _BATCH_SIZE):
        await db.batch(statements[start : start + _BATCH_SIZE])


def _forecast_variant(
    daily_sales: dict[date, int],
    *,
    today: date,
    available: int,
    reorder_threshold: int,
    lead_time_days: int,
    safety_stock_days: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    first_sale = min(daily_sales, default=today)
    observed_days = 0 if not daily_sales else min(HISTORY_DAYS, (today - first_sale).days + 1)

    def window(days: int) -> list[float]:
        usable = min(days, observed_days) if observed_days else days
        return [
            float(daily_sales.get(today - timedelta(days=offset), 0)) for offset in range(usable)
        ]

    values_7 = window(7)
    values_30 = window(30)
    avg_7 = sum(values_7) / len(values_7) if values_7 else 0.0
    avg_30 = sum(values_30) / len(values_30) if values_30 else 0.0
    if observed_days >= 30:
        baseline = avg_7 * 0.65 + avg_30 * 0.35
    elif observed_days:
        baseline = avg_7
    else:
        baseline = 0.0

    seasonal_values: dict[int, list[float]] = defaultdict(list)
    history: list[float] = []
    season_days = min(observed_days, 84)
    for offset in range(season_days):
        day = today - timedelta(days=offset)
        units = float(daily_sales.get(day, 0))
        history.append(units)
        seasonal_values[day.weekday()].append(units)
    overall = sum(history) / len(history) if history else 0.0
    multipliers: dict[int, float] = {}
    for weekday in range(7):
        samples = seasonal_values.get(weekday, [])
        if overall <= 0 or not samples:
            multipliers[weekday] = 1.0
            continue
        # Three pseudo-observations at the global mean keep a single launch
        # weekend from turning into an extreme permanent multiplier.
        shrunk_mean = (sum(samples) + overall * 3) / (len(samples) + 3)
        multipliers[weekday] = _clamp(shrunk_mean / overall, 0.5, 2.0)

    residuals: list[float] = []
    for offset, actual in enumerate(values_30):
        historical_day = today - timedelta(days=offset)
        residuals.append(actual - baseline * multipliers[historical_day.weekday()])
    sigma = pstdev(residuals) if len(residuals) > 1 else math.sqrt(max(baseline, 0.0))

    forecasts: list[dict[str, Any]] = []
    cumulative = 0.0
    stockout_date: date | None = None
    days_until_stockout: float | None = None
    for day_offset in range(1, HORIZON_DAYS + 1):
        forecast_day = today + timedelta(days=day_offset)
        multiplier = multipliers[forecast_day.weekday()]
        predicted = max(baseline * multiplier, 0.0)
        lower = max(predicted - 1.96 * sigma, 0.0)
        upper = max(predicted + 1.96 * sigma, lower)
        forecasts.append(
            {
                "forecast_date": forecast_day.isoformat(),
                "predicted_units": round(predicted, 4),
                "lower_units": round(lower, 4),
                "upper_units": round(upper, 4),
                "seasonality_multiplier": round(multiplier, 4),
            }
        )
        previous = cumulative
        cumulative += predicted
        if stockout_date is None and predicted > 0 and cumulative >= available:
            fraction = _clamp((available - previous) / predicted, 0.0, 1.0)
            days_until_stockout = round((day_offset - 1) + fraction, 2)
            stockout_date = forecast_day

    target_days = lead_time_days + safety_stock_days
    average_multiplier = sum(multipliers.values()) / 7
    target_demand = baseline * average_multiplier * target_days
    threshold_breach = reorder_threshold > 0 and available <= reorder_threshold
    reorder_recommended = threshold_breach or (
        days_until_stockout is not None and days_until_stockout <= lead_time_days
    )
    recommended_order_units = (
        max(math.ceil(target_demand - available), reorder_threshold - available, 0)
        if reorder_recommended
        else 0
    )
    return forecasts, {
        "avg_daily_7": round(avg_7, 4),
        "avg_daily_30": round(avg_30, 4),
        "available_units": available,
        "lead_time_days": lead_time_days,
        "safety_stock_days": safety_stock_days,
        "days_until_stockout": days_until_stockout,
        "projected_stockout_date": stockout_date.isoformat() if stockout_date else None,
        "reorder_recommended": int(reorder_recommended),
        "recommended_order_units": recommended_order_units,
        "data_days": observed_days,
    }


async def recompute_demand_forecasts(db: Database, *, today: date | None = None) -> dict[str, Any]:
    """Compute and publish one immutable forecast run.

    A failed run remains queryable for operations, but readers continue using
    the previous completed run. This is important because D1 batches are
    atomic per batch, not across an arbitrarily large catalogue refresh.
    """
    effective_today = today or datetime.now(UTC).date()
    now = utc_now_iso()
    run_id = new_id("dfr")
    await db.execute(
        "INSERT INTO demand_forecast_runs"
        " (id, status, model_version, horizon_days, started_at)"
        " VALUES (?, 'running', ?, ?, ?)",
        (run_id, MODEL_VERSION, HORIZON_DAYS, now),
    )
    try:
        variants = await db.fetch_all(
            """
            SELECT v.id AS variant_id, v.product_id,
                   COALESCE(SUM(il.on_hand - il.reserved), 0) AS available_units,
                   COALESCE(SUM(il.reorder_threshold), 0) AS reorder_threshold,
                   COALESCE(fs.lead_time_days, 7) AS lead_time_days,
                   COALESCE(fs.safety_stock_days, 2) AS safety_stock_days
            FROM product_variants v
            JOIN products p ON p.id = v.product_id
            LEFT JOIN inventory_levels il ON il.variant_id = v.id
            LEFT JOIN inventory_forecast_settings fs ON fs.variant_id = v.id
            WHERE v.status = 'active' AND p.status = 'published'
            GROUP BY v.id, v.product_id, fs.lead_time_days, fs.safety_stock_days
            """
        )
        boundary = (effective_today - timedelta(days=HISTORY_DAYS - 1)).isoformat()
        sales_rows = await db.fetch_all(
            """
            SELECT oi.variant_id, DATE(COALESCE(o.placed_at, o.created_at)) AS sale_day,
                   SUM(oi.quantity) AS units
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE oi.variant_id IS NOT NULL
              AND o.order_status != 'cancelled'
              AND DATE(COALESCE(o.placed_at, o.created_at)) BETWEEN ? AND ?
            GROUP BY oi.variant_id, sale_day
            """,
            (boundary, effective_today.isoformat()),
        )
        sales: dict[str, dict[date, int]] = defaultdict(dict)
        for row in sales_rows:
            sales[str(row["variant_id"])][_parse_day(str(row["sale_day"]))] = int(row["units"])

        statements: list[tuple[str, tuple[Any, ...]]] = []
        forecast_count = 0
        for variant in variants:
            variant_id = str(variant["variant_id"])
            forecasts, summary = _forecast_variant(
                sales.get(variant_id, {}),
                today=effective_today,
                available=max(int(variant["available_units"]), 0),
                reorder_threshold=max(int(variant["reorder_threshold"]), 0),
                lead_time_days=int(variant["lead_time_days"]),
                safety_stock_days=int(variant["safety_stock_days"]),
            )
            for forecast in forecasts:
                statements.append(
                    (
                        "INSERT INTO demand_forecasts"
                        " (run_id, product_id, variant_id, forecast_date, predicted_units,"
                        " lower_units, upper_units, seasonality_multiplier, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            run_id,
                            variant["product_id"],
                            variant_id,
                            forecast["forecast_date"],
                            forecast["predicted_units"],
                            forecast["lower_units"],
                            forecast["upper_units"],
                            forecast["seasonality_multiplier"],
                            now,
                        ),
                    )
                )
            forecast_count += len(forecasts)
            statements.append(
                (
                    "INSERT INTO demand_forecast_summaries"
                    " (run_id, product_id, variant_id, avg_daily_7, avg_daily_30,"
                    " available_units, lead_time_days, safety_stock_days, days_until_stockout,"
                    " projected_stockout_date, reorder_recommended, recommended_order_units,"
                    " data_days, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        variant["product_id"],
                        variant_id,
                        summary["avg_daily_7"],
                        summary["avg_daily_30"],
                        summary["available_units"],
                        summary["lead_time_days"],
                        summary["safety_stock_days"],
                        summary["days_until_stockout"],
                        summary["projected_stockout_date"],
                        summary["reorder_recommended"],
                        summary["recommended_order_units"],
                        summary["data_days"],
                        now,
                    ),
                )
            )
        await _write_chunks(db, statements)
        completed_at = utc_now_iso()
        await db.execute(
            "UPDATE demand_forecast_runs SET status = 'completed', variants_processed = ?,"
            " forecasts_written = ?, completed_at = ? WHERE id = ?",
            (len(variants), forecast_count, completed_at, run_id),
        )
        # Retain eight known-good runs for comparison/rollback plus any failed
        # run records for diagnosis. Cascades remove their forecast rows.
        await db.execute(
            "DELETE FROM demand_forecast_runs WHERE status = 'completed' AND id NOT IN"
            " (SELECT id FROM demand_forecast_runs WHERE status = 'completed'"
            " ORDER BY completed_at DESC LIMIT 8)"
        )
        await db.execute(
            "DELETE FROM demand_forecast_runs WHERE status = 'failed'"
            " AND DATE(completed_at) < DATE('now', '-90 days')"
        )
        log_event(
            "info",
            "demand_forecast.completed",
            run_id=run_id,
            variants=len(variants),
            forecasts=forecast_count,
        )
        return {"runId": run_id, "variants": len(variants), "forecasts": forecast_count}
    except Exception as exc:
        await db.execute(
            "UPDATE demand_forecast_runs SET status = 'failed', completed_at = ?,"
            " error_message = ? WHERE id = ?",
            (utc_now_iso(), str(exc)[:500], run_id),
        )
        log_event("error", "demand_forecast.failed", run_id=run_id, error_type=type(exc).__name__)
        raise


async def load_inventory_intelligence(
    db: Database, *, farm_id: str | None = None
) -> dict[str, Any]:
    run = await db.fetch_one(
        "SELECT * FROM demand_forecast_runs WHERE status = 'completed'"
        " ORDER BY completed_at DESC LIMIT 1"
    )
    if run is None:
        return {"run": None, "items": [], "summary": {"reorderSoon": 0, "forecastedSkus": 0}}
    rows = await db.fetch_all(
        """
        SELECT s.*, p.name AS product_name, p.status AS product_status,
               v.name AS variant_name, v.sku, p.farm_id
        FROM demand_forecast_summaries s
        JOIN products p ON p.id = s.product_id
        JOIN product_variants v ON v.id = s.variant_id
        WHERE s.run_id = ? AND (? IS NULL OR p.farm_id = ?)
        ORDER BY s.reorder_recommended DESC,
                 CASE WHEN s.days_until_stockout IS NULL THEN 1 ELSE 0 END,
                 s.days_until_stockout, p.name, v.sort_order
        """,
        (run["id"], farm_id, farm_id),
    )
    items = [
        {
            "productId": row["product_id"],
            "productName": row["product_name"],
            "productStatus": row["product_status"],
            "variantId": row["variant_id"],
            "variantName": row["variant_name"],
            "sku": row["sku"],
            "availableUnits": int(row["available_units"]),
            "avgDaily7": float(row["avg_daily_7"]),
            "avgDaily30": float(row["avg_daily_30"]),
            "leadTimeDays": int(row["lead_time_days"]),
            "safetyStockDays": int(row["safety_stock_days"]),
            "daysUntilStockout": (
                float(row["days_until_stockout"])
                if row["days_until_stockout"] is not None
                else None
            ),
            "projectedStockoutDate": row["projected_stockout_date"],
            "reorderRecommended": bool(row["reorder_recommended"]),
            "recommendedOrderUnits": int(row["recommended_order_units"]),
            "dataDays": int(row["data_days"]),
        }
        for row in rows
    ]
    return {
        "run": {
            "id": run["id"],
            "modelVersion": run["model_version"],
            "horizonDays": int(run["horizon_days"]),
            "completedAt": run["completed_at"],
        },
        "summary": {
            "reorderSoon": sum(1 for item in items if item["reorderRecommended"]),
            "forecastedSkus": len(items),
        },
        "items": items,
    }

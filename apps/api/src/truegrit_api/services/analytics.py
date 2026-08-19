"""Owner analytics dashboard (migration 0065): revenue, orders, top products
and order-status mix over a date range. Read-only -- see
`repositories.analytics` for the queries this composes.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final

from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.analytics import AnalyticsRepository
from truegrit_api.services.recommendations import recommendation_metrics

# A dashboard, not an export tool -- a year is generous for "how is the store
# doing" while still bounding the work a single request can trigger.
_MAX_RANGE_DAYS: Final = 366


def _parse_date(value: str, field: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)
    except ValueError as exc:
        raise ValidationAppError(f"{field} must be a date in YYYY-MM-DD form.") from exc


def _default_range() -> tuple[str, str]:
    today = datetime.now(UTC).date()
    return (today - timedelta(days=29)).isoformat(), today.isoformat()


def _validate_range(from_date: str | None, to_date: str | None) -> tuple[str, str]:
    if from_date is None and to_date is None:
        return _default_range()
    if from_date is None or to_date is None:
        raise ValidationAppError("Provide both a start and an end date, or neither.")
    parsed_from = _parse_date(from_date, "Start date")
    parsed_to = _parse_date(to_date, "End date")
    if parsed_to < parsed_from:
        raise ValidationAppError("End date must be on or after the start date.")
    if (parsed_to - parsed_from).days > _MAX_RANGE_DAYS:
        raise ValidationAppError(f"Date range cannot exceed {_MAX_RANGE_DAYS} days.")
    return from_date, to_date


async def load_overview(
    db: Database, *, from_date: str | None = None, to_date: str | None = None
) -> dict[str, Any]:
    clean_from, clean_to = _validate_range(from_date, to_date)
    repository = AnalyticsRepository(db)

    overview = await repository.overview(from_date=clean_from, to_date=clean_to)
    revenue_minor = int(overview["revenue_minor"])
    order_count = int(overview["order_count"])
    average_order_value_minor = revenue_minor // order_count if order_count else 0

    new_customers = await repository.new_customers(from_date=clean_from, to_date=clean_to)
    revenue_by_day = await repository.revenue_by_day(from_date=clean_from, to_date=clean_to)
    top_products = await repository.top_products(from_date=clean_from, to_date=clean_to)
    status_breakdown = await repository.status_breakdown(from_date=clean_from, to_date=clean_to)
    recommendations = await recommendation_metrics(db, from_date=clean_from, to_date=clean_to)

    return {
        "fromDate": clean_from,
        "toDate": clean_to,
        "revenueMinor": revenue_minor,
        "orderCount": order_count,
        "averageOrderValueMinor": average_order_value_minor,
        "newCustomers": new_customers,
        "revenueByDay": [
            {
                "date": row["day"],
                "revenueMinor": int(row["revenue_minor"]),
                "orderCount": int(row["order_count"]),
            }
            for row in revenue_by_day
        ],
        "topProducts": [
            {
                "productId": row["product_id"],
                "productName": row["product_name"],
                "unitsSold": int(row["units_sold"]),
                "revenueMinor": int(row["revenue_minor"]),
            }
            for row in top_products
        ],
        "statusBreakdown": [
            {"status": row["order_status"], "orderCount": int(row["order_count"])}
            for row in status_breakdown
        ],
        "recommendations": recommendations,
    }

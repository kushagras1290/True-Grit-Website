"""Owner reporting console: a curated library of named, parameterized,
read-only queries — never free-text SQL.

No endpoint or admin input ever reaches the database as SQL text. Each
`ReportDefinition` owns its own fixed statement; the only thing a caller
supplies is a small set of allow-listed, type-checked filter values that get
bound as ordinary query parameters, in the exact order `param_keys` declares.
This keeps the console's entire attack surface identical to any other
parameterized query in the app — there is no new class of risk here, just a
fixed menu instead of an open text box.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class ReportParam:
    key: str
    label: str
    kind: str  # 'date' | 'country'
    required: bool = False


@dataclass(frozen=True)
class ReportDefinition:
    id: str
    label: str
    description: str
    sql: str
    param_keys: tuple[str, ...] = field(default_factory=tuple)
    params: tuple[ReportParam, ...] = field(default_factory=tuple)


def _validate_param(param: ReportParam, raw: str | None) -> Any:
    if raw is None or raw == "":
        if param.required:
            raise ValidationAppError(f"'{param.label}' is required.")
        return None
    if param.kind == "date":
        if not _DATE_RE.match(raw):
            raise ValidationAppError(f"'{param.label}' must be an ISO date (YYYY-MM-DD).")
        return raw
    if param.kind == "country":
        if not re.match(r"^[A-Za-z]{2}$", raw):
            raise ValidationAppError(f"'{param.label}' must be a two-letter country code.")
        return raw.upper()
    raise ValidationAppError(f"Unsupported filter type for '{param.label}'.")


_REPORTS: dict[str, ReportDefinition] = {
    "revenue_by_month": ReportDefinition(
        id="revenue_by_month",
        label="Revenue by month",
        description="Total order value by month, excluding cancelled orders.",
        params=(
            ReportParam("date_from", "From date", "date"),
            ReportParam("date_to", "To date", "date"),
        ),
        param_keys=("date_from", "date_from", "date_to", "date_to"),
        sql="""
            SELECT strftime('%Y-%m', placed_at) AS month,
                   COUNT(*) AS orders,
                   SUM(total_minor) AS revenue_minor
            FROM orders
            WHERE order_status != 'cancelled'
              AND (? IS NULL OR date(placed_at) >= date(?))
              AND (? IS NULL OR date(placed_at) <= date(?))
            GROUP BY month
            ORDER BY month DESC
            LIMIT 500
        """,
    ),
    "top_products_by_revenue": ReportDefinition(
        id="top_products_by_revenue",
        label="Top products by revenue",
        description="Best-selling products by line-item revenue across all orders.",
        params=(
            ReportParam("date_from", "From date", "date"),
            ReportParam("date_to", "To date", "date"),
        ),
        param_keys=("date_from", "date_from", "date_to", "date_to"),
        sql="""
            SELECT oi.product_name AS product,
                   SUM(oi.quantity) AS units_sold,
                   SUM(oi.line_total_minor) AS revenue_minor
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            WHERE o.order_status != 'cancelled'
              AND (? IS NULL OR date(o.placed_at) >= date(?))
              AND (? IS NULL OR date(o.placed_at) <= date(?))
            GROUP BY oi.product_name
            ORDER BY revenue_minor DESC
            LIMIT 50
        """,
    ),
    "orders_by_status": ReportDefinition(
        id="orders_by_status",
        label="Orders by status",
        description="Order count and value grouped by order status.",
        sql="""
            SELECT order_status AS status, COUNT(*) AS orders, SUM(total_minor) AS total_minor
            FROM orders
            GROUP BY order_status
            ORDER BY orders DESC
        """,
    ),
    "top_customers_by_spend": ReportDefinition(
        id="top_customers_by_spend",
        label="Top customers by lifetime spend",
        description="Customers ranked by total order value, excluding cancelled orders.",
        sql="""
            SELECT COALESCE(u.display_name, o.customer_email) AS customer,
                   COUNT(*) AS orders,
                   SUM(o.total_minor) AS lifetime_minor
            FROM orders o
            LEFT JOIN users u ON u.id = o.customer_user_id
            WHERE o.order_status != 'cancelled'
            GROUP BY customer
            ORDER BY lifetime_minor DESC
            LIMIT 50
        """,
    ),
    "low_stock_variants": ReportDefinition(
        id="low_stock_variants",
        label="Low stock variants",
        description="Variants at or below their reorder threshold, most urgent first.",
        sql="""
            SELECT p.name AS product, v.name AS variant, v.sku,
                   il.on_hand - il.reserved AS available, il.reorder_threshold
            FROM inventory_levels il
            JOIN product_variants v ON v.id = il.variant_id
            JOIN products p ON p.id = v.product_id
            WHERE (il.on_hand - il.reserved) <= il.reorder_threshold
            ORDER BY available ASC
            LIMIT 200
        """,
    ),
    "return_requests_by_reason": ReportDefinition(
        id="return_requests_by_reason",
        label="Return requests by reason",
        description="Open and resolved return request counts grouped by reason code.",
        sql="""
            SELECT reason_code AS reason, status, COUNT(*) AS requests
            FROM return_requests
            GROUP BY reason_code, status
            ORDER BY reason, status
        """,
    ),
    "content_pipeline": ReportDefinition(
        id="content_pipeline",
        label="Content pipeline",
        description="How many blog articles and recipes sit in each workflow status.",
        sql="""
            SELECT 'article' AS content_type, status, COUNT(*) AS items
              FROM articles GROUP BY status
            UNION ALL
            SELECT 'recipe' AS content_type, status, COUNT(*) AS items FROM recipes GROUP BY status
            ORDER BY content_type, status
        """,
    ),
}


def list_reports() -> list[dict[str, Any]]:
    return [
        {
            "id": report.id,
            "label": report.label,
            "description": report.description,
            "params": [
                {"key": p.key, "label": p.label, "kind": p.kind, "required": p.required}
                for p in report.params
            ],
        }
        for report in _REPORTS.values()
    ]


async def run_report(
    db: Database, report_id: str, filters: dict[str, str] | None
) -> dict[str, Any]:
    report = _REPORTS.get(report_id)
    if report is None:
        raise NotFoundError("Report not found.")
    filters = filters or {}
    resolved: dict[str, Any] = {
        param.key: _validate_param(param, filters.get(param.key)) for param in report.params
    }
    bound_params = tuple(resolved[key] for key in report.param_keys)
    rows = await db.fetch_all(report.sql, bound_params)
    columns = list(rows[0].keys()) if rows else []
    return {
        "id": report.id,
        "label": report.label,
        "columns": columns,
        "rows": [[row[col] for col in columns] for row in rows],
    }

"""Explainable market-basket and item-similarity recommendation engine."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from itertools import combinations
from typing import Any, Final

from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

MODEL_VERSION: Final = "basket-cosine-blend-v1"
LOOKBACK_DAYS: Final = 365
MAX_RECOMMENDATIONS_PER_PRODUCT: Final = 50
_BATCH_SIZE: Final = 75


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(value, high))


async def _write_chunks(db: Database, statements: list[tuple[str, tuple[Any, ...]]]) -> None:
    for start in range(0, len(statements), _BATCH_SIZE):
        await db.batch(statements[start : start + _BATCH_SIZE])


async def recompute_recommendations(db: Database) -> dict[str, Any]:
    now_dt = datetime.now(UTC)
    now = now_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    boundary = (now_dt - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = new_id("rrn")
    await db.execute(
        "INSERT INTO recommendation_runs"
        " (id, status, model_version, lookback_days, started_at)"
        " VALUES (?, 'running', ?, ?, ?)",
        (run_id, MODEL_VERSION, LOOKBACK_DAYS, now),
    )
    try:
        rows = await db.fetch_all(
            """
            SELECT o.id AS order_id, COALESCE(o.placed_at, o.created_at) AS ordered_at,
                   oi.product_id, SUM(oi.quantity) AS units
            FROM orders o
            JOIN order_items oi ON oi.order_id = o.id
            JOIN products p ON p.id = oi.product_id
            WHERE o.order_status != 'cancelled' AND oi.product_id IS NOT NULL
              AND COALESCE(o.placed_at, o.created_at) >= ?
            GROUP BY o.id, ordered_at, oi.product_id
            ORDER BY o.id
            """,
            (boundary,),
        )
        categories_rows = await db.fetch_all(
            "SELECT product_id, category_id FROM product_categories"
        )
        categories: dict[str, set[str]] = defaultdict(set)
        for row in categories_rows:
            categories[str(row["product_id"])].add(str(row["category_id"]))

        order_products: dict[str, set[str]] = defaultdict(set)
        product_orders: dict[str, set[str]] = defaultdict(set)
        units_7d: dict[str, int] = defaultdict(int)
        units_30d: dict[str, int] = defaultdict(int)
        last_order: dict[str, datetime] = {}
        seven_boundary = now_dt - timedelta(days=7)
        thirty_boundary = now_dt - timedelta(days=30)
        for row in rows:
            order_id = str(row["order_id"])
            product_id = str(row["product_id"])
            ordered_at = datetime.fromisoformat(str(row["ordered_at"]).replace("Z", "+00:00"))
            units = int(row["units"])
            order_products[order_id].add(product_id)
            product_orders[product_id].add(order_id)
            if ordered_at >= seven_boundary:
                units_7d[product_id] += units
            if ordered_at >= thirty_boundary:
                units_30d[product_id] += units
            if product_id not in last_order or ordered_at > last_order[product_id]:
                last_order[product_id] = ordered_at

        pair_counts: dict[tuple[str, str], int] = defaultdict(int)
        for products in order_products.values():
            for left, right in combinations(sorted(products), 2):
                pair_counts[(left, right)] += 1
                pair_counts[(right, left)] += 1

        total_orders = len(order_products)
        product_ids = sorted(product_orders)
        max_units_30 = max(units_30d.values(), default=0)
        popularity: dict[str, float] = {
            product_id: (units_30d[product_id] / max_units_30 if max_units_30 else 0.0)
            for product_id in product_ids
        }
        recency: dict[str, float] = {}
        for product_id in product_ids:
            age_days = max((now_dt - last_order[product_id]).total_seconds() / 86400, 0.0)
            recency[product_id] = _clamp(math.exp(-age_days / 30))

        popularity_ranked = sorted(
            product_ids,
            key=lambda product_id: (
                -(0.7 * popularity[product_id] + 0.3 * recency[product_id]),
                product_id,
            ),
        )
        statements: list[tuple[str, tuple[Any, ...]]] = []
        for rank, product_id in enumerate(popularity_ranked, 1):
            statements.append(
                (
                    "INSERT INTO recommendation_product_scores"
                    " (run_id, product_id, units_7d, units_30d, order_count, popularity_score,"
                    " recency_score, last_order_at, rank, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        run_id,
                        product_id,
                        units_7d[product_id],
                        units_30d[product_id],
                        len(product_orders[product_id]),
                        round(popularity[product_id], 6),
                        round(recency[product_id], 6),
                        last_order[product_id].strftime("%Y-%m-%dT%H:%M:%SZ"),
                        rank,
                        now,
                    ),
                )
            )

        association_count = 0
        for source in product_ids:
            source_orders = len(product_orders[source])
            candidates: list[dict[str, Any]] = []
            for target in product_ids:
                if target == source:
                    continue
                co_count = pair_counts.get((source, target), 0)
                target_orders = len(product_orders[target])
                confidence = co_count / source_orders if source_orders else 0.0
                target_probability = target_orders / total_orders if total_orders else 0.0
                lift = confidence / target_probability if target_probability else 0.0
                cosine = (
                    co_count / math.sqrt(source_orders * target_orders)
                    if source_orders and target_orders
                    else 0.0
                )
                shared = categories[source] & categories[target]
                category_match = 1.0 if shared else 0.0
                # Sparse products still receive indirect/category and cold-start
                # signals; direct baskets dominate once they exist.
                score = (
                    0.30 * cosine
                    + 0.25 * _clamp(lift / 5)
                    + 0.15 * confidence
                    + 0.12 * category_match
                    + 0.10 * popularity[target]
                    + 0.08 * recency[target]
                )
                candidates.append(
                    {
                        "target": target,
                        "co_count": co_count,
                        "target_orders": target_orders,
                        "confidence": confidence,
                        "lift": lift,
                        "cosine": cosine,
                        "category_match": category_match,
                        "score": score,
                        "reason": (
                            "frequently_bought_together" if co_count > 0 else "similar_product"
                        ),
                    }
                )
            candidates.sort(key=lambda item: (-item["score"], -item["co_count"], item["target"]))
            for rank, item in enumerate(candidates[:MAX_RECOMMENDATIONS_PER_PRODUCT], 1):
                statements.append(
                    (
                        "INSERT INTO product_cooccurrence"
                        " (run_id, source_product_id, recommended_product_id, co_purchase_count,"
                        " source_order_count, recommended_order_count, confidence, lift,"
                        " cosine_similarity, category_match, popularity_score, recency_score,"
                        " blended_score, rank, reason, created_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            run_id,
                            source,
                            item["target"],
                            item["co_count"],
                            source_orders,
                            item["target_orders"],
                            round(item["confidence"], 6),
                            round(item["lift"], 6),
                            round(item["cosine"], 6),
                            item["category_match"],
                            round(popularity[item["target"]], 6),
                            round(recency[item["target"]], 6),
                            round(item["score"], 6),
                            rank,
                            item["reason"],
                            now,
                        ),
                    )
                )
                association_count += 1

        await _write_chunks(db, statements)
        await db.execute(
            "UPDATE recommendation_runs SET status = 'completed', orders_processed = ?,"
            " products_processed = ?, associations_written = ?, completed_at = ? WHERE id = ?",
            (total_orders, len(product_ids), association_count, utc_now_iso(), run_id),
        )
        await db.execute(
            "DELETE FROM recommendation_runs WHERE status = 'completed' AND id NOT IN"
            " (SELECT id FROM recommendation_runs WHERE status = 'completed'"
            " ORDER BY completed_at DESC LIMIT 8)"
        )
        await db.execute(
            "DELETE FROM recommendation_runs WHERE status = 'failed'"
            " AND DATE(completed_at) < DATE('now', '-90 days')"
        )
        await db.execute(
            "DELETE FROM recommendation_events WHERE DATE(created_at) < DATE('now', '-400 days')"
        )
        log_event(
            "info",
            "recommendations.completed",
            run_id=run_id,
            orders=total_orders,
            products=len(product_ids),
            associations=association_count,
        )
        return {
            "runId": run_id,
            "orders": total_orders,
            "products": len(product_ids),
            "associations": association_count,
        }
    except Exception as exc:
        await db.execute(
            "UPDATE recommendation_runs SET status = 'failed', completed_at = ?,"
            " error_message = ? WHERE id = ?",
            (utc_now_iso(), str(exc)[:500], run_id),
        )
        log_event("error", "recommendations.failed", run_id=run_id, error_type=type(exc).__name__)
        raise


async def ranked_recommendations(
    db: Database, source_product_id: str, *, limit: int = 6
) -> tuple[str | None, list[dict[str, Any]]]:
    run = await db.fetch_one(
        "SELECT id FROM recommendation_runs WHERE status = 'completed'"
        " ORDER BY completed_at DESC LIMIT 1"
    )
    if run is None:
        return None, []
    rows = await db.fetch_all(
        """
        SELECT recommended_product_id, blended_score, confidence, lift,
               cosine_similarity, reason, rank
        FROM product_cooccurrence
        WHERE run_id = ? AND source_product_id = ?
        ORDER BY rank
        LIMIT ?
        """,
        (run["id"], source_product_id, max(limit, 1)),
    )
    if not rows:
        rows = await db.fetch_all(
            """
            SELECT product_id AS recommended_product_id,
                   (popularity_score * 0.6 + recency_score * 0.2 +
                    CASE WHEN EXISTS (
                      SELECT 1 FROM product_categories source_pc
                      JOIN product_categories target_pc
                        ON target_pc.category_id = source_pc.category_id
                      WHERE source_pc.product_id = ?
                        AND target_pc.product_id = recommendation_product_scores.product_id
                    ) THEN 0.2 ELSE 0 END) AS blended_score,
                   0.0 AS confidence, 0.0 AS lift, 0.0 AS cosine_similarity,
                   CASE WHEN EXISTS (
                     SELECT 1 FROM product_categories source_pc
                     JOIN product_categories target_pc
                       ON target_pc.category_id = source_pc.category_id
                     WHERE source_pc.product_id = ?
                       AND target_pc.product_id = recommendation_product_scores.product_id
                   ) THEN 'similar_product' ELSE 'trending' END AS reason, rank
            FROM recommendation_product_scores
            WHERE run_id = ? AND product_id != ?
            ORDER BY blended_score DESC, rank LIMIT ?
            """,
            (source_product_id, source_product_id, run["id"], source_product_id, max(limit, 1)),
        )
    return str(run["id"]), rows


async def record_event(
    db: Database,
    *,
    visitor_session_id: str,
    source_product_id: str | None,
    recommended_product_id: str,
    recommendation_run_id: str | None,
    placement: str,
    event_type: str,
) -> str:
    source = None
    if source_product_id:
        source_row = await db.fetch_one(
            "SELECT id FROM products WHERE id = ?", (source_product_id,)
        )
        source = str(source_row["id"]) if source_row else None
    valid_run = None
    if recommendation_run_id:
        run_row = await db.fetch_one(
            "SELECT id FROM recommendation_runs WHERE id = ? AND status = 'completed'",
            (recommendation_run_id,),
        )
        valid_run = str(run_row["id"]) if run_row else None
    event_id = new_id("rev")
    await db.execute(
        "INSERT INTO recommendation_events"
        " (id, visitor_session_id, source_product_id, recommended_product_id,"
        " recommendation_run_id, placement, event_type, created_at)"
        " SELECT ?, ?, ?, p.id, ?, ?, ?, ? FROM products p WHERE p.id = ?",
        (
            event_id,
            visitor_session_id,
            source,
            valid_run,
            placement,
            event_type,
            utc_now_iso(),
            recommended_product_id,
        ),
    )
    return event_id


async def recommendation_metrics(db: Database, *, from_date: str, to_date: str) -> dict[str, Any]:
    events = await db.fetch_one(
        """
        SELECT SUM(CASE WHEN event_type = 'impression' THEN 1 ELSE 0 END) AS impressions,
               SUM(CASE WHEN event_type = 'click' THEN 1 ELSE 0 END) AS clicks,
               SUM(CASE WHEN event_type = 'add_to_cart' THEN 1 ELSE 0 END) AS adds
        FROM recommendation_events
        WHERE DATE(created_at) BETWEEN ? AND ?
        """,
        (from_date, to_date),
    )
    attributed = await db.fetch_one(
        """
        SELECT COUNT(DISTINCT order_id) AS orders, COALESCE(SUM(quantity), 0) AS units,
               COALESCE(SUM(attributed_revenue_minor), 0) AS revenue_minor
        FROM recommendation_attributions
        WHERE DATE(created_at) BETWEEN ? AND ?
        """,
        (from_date, to_date),
    )
    impressions = int((events or {}).get("impressions") or 0)
    clicks = int((events or {}).get("clicks") or 0)
    return {
        "impressions": impressions,
        "clicks": clicks,
        "addToCarts": int((events or {}).get("adds") or 0),
        "clickThroughRate": round(clicks / impressions, 4) if impressions else 0.0,
        "attributedOrders": int((attributed or {}).get("orders") or 0),
        "attributedUnits": int((attributed or {}).get("units") or 0),
        "attributedRevenueMinor": int((attributed or {}).get("revenue_minor") or 0),
    }

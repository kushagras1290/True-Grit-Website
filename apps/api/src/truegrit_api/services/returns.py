"""Return requests (RMA): customer-initiated, staff-reviewed.

A customer may request a return against their own order (`create_return_request`).
Staff with `returns.manage` triage it (`decide_return_request`: under_review,
approved, or a terminal rejected) and then resolve an approved request
(`resolve_return_request`). A refund resolution also writes an
`order_adjustments` ledger row and updates the order's `payment_status`,
keeping the return in step with the existing money model — integer minor
units throughout, never a float, never client-trusted (ADR-006) — and
requires `orders.refund` in addition to `returns.manage` as a second gate on
the money-moving path.
"""

from __future__ import annotations

import json
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_REASON_CODES = frozenset(
    {"damaged", "wrong_item", "quality_issue", "not_as_described", "missing_item", "other"}
)
_RETURNABLE_ORDER_STATUSES = frozenset({"confirmed", "processing", "completed"})
_OPEN_STATUSES = frozenset({"requested", "under_review"})
_RESOLUTION_TYPES = frozenset({"refund", "replacement", "store_credit", "none"})
_RESOLUTION_TARGET_STATUS = {
    "refund": "refunded",
    "replacement": "replaced",
    "store_credit": "completed",
    "none": "completed",
}
_MAX_EVIDENCE = 6


async def create_return_request(
    db: Database,
    customer: Principal,
    request_id: str,
    *,
    order_id: str,
    order_item_id: str | None,
    reason_code: str,
    description: str,
    requested_refund_amount_minor: int | None = None,
    evidence_media_ids: list[str] | None = None,
) -> dict[str, Any]:
    if reason_code not in _REASON_CODES:
        raise ValidationAppError("Unsupported return reason.")
    description = description.strip()
    if len(description) < 10:
        raise ValidationAppError("Describe the issue in at least 10 characters.")
    evidence = (evidence_media_ids or [])[:_MAX_EVIDENCE]

    order = await db.fetch_one(
        "SELECT id, customer_user_id, order_status, total_minor FROM orders WHERE id = ?",
        (order_id,),
    )
    if order is None or order["customer_user_id"] != customer.user_id:
        raise NotFoundError("Order not found.")
    if order["order_status"] not in _RETURNABLE_ORDER_STATUSES:
        raise ConflictError("This order is not eligible for a return request yet.")
    if order_item_id is not None:
        item = await db.fetch_one(
            """
            SELECT oi.id, COALESCE(p.return_eligible, 1) AS return_eligible
            FROM order_items oi
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.id = ? AND oi.order_id = ?
            """,
            (order_item_id, order_id),
        )
        if item is None:
            raise NotFoundError("Order item not found.")
        if not item["return_eligible"]:
            raise ValidationAppError("This product is not eligible for return.")
    else:
        eligible = await db.fetch_one(
            """
            SELECT 1
            FROM order_items oi
            LEFT JOIN products p ON p.id = oi.product_id
            WHERE oi.order_id = ? AND COALESCE(p.return_eligible, 1) = 1
            LIMIT 1
            """,
            (order_id,),
        )
        if eligible is None:
            raise ValidationAppError("No items in this order are eligible for return.")
    scope_sql = "AND order_item_id = ?" if order_item_id else "AND order_item_id IS NULL"
    scope_params = (order_id, order_item_id) if order_item_id else (order_id,)
    existing = await db.fetch_one(
        f"SELECT id FROM return_requests WHERE order_id = ? {scope_sql} AND status != 'rejected'",
        scope_params,
    )
    if existing is not None:
        raise ConflictError("A return request is already open for this order.")
    if (
        requested_refund_amount_minor is not None
        and requested_refund_amount_minor > order["total_minor"]
    ):
        raise ValidationAppError("Requested amount cannot exceed the order total.")

    now = utc_now_iso()
    return_id = new_id("ret")
    await db.batch(
        [
            (
                "INSERT INTO return_requests"
                " (id, order_id, order_item_id, customer_user_id, reason_code, description,"
                "  evidence_media_ids_json, status, requested_refund_amount_minor,"
                "  requested_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'requested', ?, ?, ?, ?)",
                (
                    return_id,
                    order_id,
                    order_item_id,
                    customer.user_id,
                    reason_code,
                    description,
                    json.dumps(evidence),
                    requested_refund_amount_minor,
                    now,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="return_request.created",
                entity_type="return_request",
                entity_id=return_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"orderId": order_id, "reasonCode": reason_code},
            ),
        ]
    )
    return {"id": return_id, "status": "requested"}


async def decide_return_request(
    db: Database, actor: Principal, request_id: str, return_id: str, *, decision: str
) -> dict[str, Any]:
    if decision not in {"under_review", "approved", "rejected"}:
        raise ValidationAppError("Unsupported decision.")
    current = await db.fetch_one("SELECT * FROM return_requests WHERE id = ?", (return_id,))
    if current is None:
        raise NotFoundError("Return request not found.")
    if current["status"] not in _OPEN_STATUSES:
        raise ConflictError(f"Cannot move a '{current['status']}' return request to '{decision}'.")

    now = utc_now_iso()
    if decision == "rejected":
        statement = (
            "UPDATE return_requests SET status = ?, resolved_at = ?, resolved_by = ?,"
            " updated_at = ? WHERE id = ?",
            (decision, now, actor.user_id, now, return_id),
        )
    else:
        statement = (
            "UPDATE return_requests SET status = ?, updated_at = ? WHERE id = ?",
            (decision, now, return_id),
        )
    await db.batch(
        [
            statement,
            audit_statement(
                action=f"return_request.{decision}",
                entity_type="return_request",
                entity_id=return_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": decision},
            ),
        ]
    )
    return {"id": return_id, "status": decision}


async def resolve_return_request(
    db: Database,
    actor: Principal,
    request_id: str,
    return_id: str,
    *,
    resolution_type: str,
    resolution_amount_minor: int | None,
    resolution_notes: str | None,
) -> dict[str, Any]:
    if resolution_type not in _RESOLUTION_TYPES:
        raise ValidationAppError("Unsupported resolution type.")
    current = await db.fetch_one("SELECT * FROM return_requests WHERE id = ?", (return_id,))
    if current is None:
        raise NotFoundError("Return request not found.")
    if current["status"] != "approved":
        raise ConflictError("Only an approved return request can be resolved.")

    order = await db.fetch_one(
        "SELECT id, total_minor FROM orders WHERE id = ?", (current["order_id"],)
    )
    if order is None:
        raise NotFoundError("Order not found.")

    refund_amount = int(resolution_amount_minor or 0)
    if resolution_type == "refund":
        if not actor.has("orders.refund"):
            raise PermissionDeniedError()
        if refund_amount <= 0:
            raise ValidationAppError("Enter a refund amount greater than zero.")
        if refund_amount > order["total_minor"]:
            raise ValidationAppError("Refund cannot exceed the order total.")

    now = utc_now_iso()
    target_status = _RESOLUTION_TARGET_STATUS[resolution_type]
    statements: list[tuple[str, Any]] = [
        (
            "UPDATE return_requests SET status = ?, resolution_type = ?,"
            " resolution_amount_minor = ?, resolution_notes = ?, resolved_at = ?,"
            " resolved_by = ?, updated_at = ? WHERE id = ?",
            (
                target_status,
                resolution_type,
                resolution_amount_minor,
                (resolution_notes or "").strip() or None,
                now,
                actor.user_id,
                now,
                return_id,
            ),
        ),
        audit_statement(
            action="return_request.resolved",
            entity_type="return_request",
            entity_id=return_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"status": current["status"]},
            after={
                "status": target_status,
                "resolutionType": resolution_type,
                "amountMinor": resolution_amount_minor,
            },
        ),
    ]
    if resolution_type == "refund" and refund_amount > 0:
        new_payment_status = (
            "refunded" if refund_amount >= order["total_minor"] else "partially_refunded"
        )
        statements.append(
            (
                "INSERT INTO order_adjustments"
                " (id, order_id, adjustment_type, label, amount_minor, created_at, created_by)"
                " VALUES (?, ?, 'refund', ?, ?, ?, ?)",
                (
                    new_id("adj"),
                    current["order_id"],
                    "Return refund",
                    -refund_amount,
                    now,
                    actor.user_id,
                ),
            )
        )
        statements.append(
            (
                "UPDATE orders SET payment_status = ?, updated_at = ? WHERE id = ?",
                (new_payment_status, now, current["order_id"]),
            )
        )
    await db.batch(statements)
    return {"id": return_id, "status": target_status}

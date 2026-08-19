"""Stage 1 of the refund orchestrator: gather everything the fraud-signal
scorer and decision stage need about one return request, in a single
read-only pass. Nothing here mutates state or calls a gateway -- it only
reads `return_requests`, the order, the latest payment on that order, and
the customer's history across all their orders.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from truegrit_api.errors import NotFoundError
from truegrit_api.platform.database import Database

_LOOKBACK_DAYS: int = 30
_LIFETIME_PAID_STATUSES = ("paid", "partially_refunded", "refunded")


@dataclass(frozen=True)
class RefundContext:
    return_request_id: str
    order_id: str
    customer_user_id: str | None
    reason_code: str
    evidence_media_count: int
    requested_refund_amount_minor: int | None
    order_total_minor: int
    billing_address_json: str | None
    delivery_address_json: str | None

    payment_provider: str | None
    payment_status: str | None
    payment_amount_minor: int | None
    already_refunded_minor: int

    account_created_at: str | None
    recent_return_count: int  # this customer's return requests in the trailing window
    lifetime_order_count: int  # orders with a paid/refunded payment
    lifetime_paid_minor: int
    lifetime_refunded_minor: int


def _lookback_cutoff_iso() -> str:
    return (datetime.now(UTC) - timedelta(days=_LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def gather_context(db: Database, return_request_id: str) -> RefundContext:
    return_row = await db.fetch_one(
        "SELECT id, order_id, customer_user_id, reason_code, evidence_media_ids_json,"
        " requested_refund_amount_minor FROM return_requests WHERE id = ?",
        (return_request_id,),
    )
    if return_row is None:
        raise NotFoundError("Return request not found.")

    order = await db.fetch_one(
        "SELECT id, customer_user_id, total_minor, billing_address_json, delivery_address_json"
        " FROM orders WHERE id = ?",
        (return_row["order_id"],),
    )
    if order is None:
        raise NotFoundError("Order not found.")

    payment = await db.fetch_one(
        """
        SELECT id, provider, provider_intent_id, amount_minor, currency_code, status
        FROM payments WHERE order_id = ?
        ORDER BY created_at DESC LIMIT 1
        """,
        (return_row["order_id"],),
    )
    already_refunded_minor = 0
    if payment is not None:
        refunded_row = await db.fetch_one(
            "SELECT COALESCE(SUM(amount_minor), 0) AS refunded FROM payment_events"
            " WHERE payment_id = ? AND event_type = 'refund'",
            (payment["id"],),
        )
        already_refunded_minor = int(refunded_row["refunded"]) if refunded_row else 0

    customer_id = order["customer_user_id"]
    account_created_at: str | None = None
    recent_return_count = 0
    lifetime_order_count = 0
    lifetime_paid_minor = 0
    lifetime_refunded_minor = 0

    if customer_id:
        account_row = await db.fetch_one(
            "SELECT created_at FROM users WHERE id = ?", (customer_id,)
        )
        account_created_at = account_row["created_at"] if account_row else None

        recent_row = await db.fetch_one(
            "SELECT COUNT(*) AS n FROM return_requests"
            " WHERE customer_user_id = ? AND requested_at >= ?",
            (customer_id, _lookback_cutoff_iso()),
        )
        recent_return_count = int(recent_row["n"]) if recent_row else 0

        lifetime_row = await db.fetch_one(
            f"""
            SELECT COALESCE(SUM(p.amount_minor), 0) AS paid,
                   COUNT(DISTINCT o.id) AS order_count
            FROM orders o
            JOIN payments p ON p.order_id = o.id
            WHERE o.customer_user_id = ?
              AND p.status IN ({",".join("?" * len(_LIFETIME_PAID_STATUSES))})
            """,
            (customer_id, *_LIFETIME_PAID_STATUSES),
        )
        lifetime_paid_minor = int(lifetime_row["paid"]) if lifetime_row else 0
        lifetime_order_count = int(lifetime_row["order_count"]) if lifetime_row else 0

        lifetime_refund_row = await db.fetch_one(
            """
            SELECT COALESCE(SUM(pe.amount_minor), 0) AS refunded
            FROM payment_events pe
            JOIN payments p ON p.id = pe.payment_id
            JOIN orders o ON o.id = p.order_id
            WHERE o.customer_user_id = ? AND pe.event_type = 'refund'
            """,
            (customer_id,),
        )
        lifetime_refunded_minor = int(lifetime_refund_row["refunded"]) if lifetime_refund_row else 0

    evidence_ids: list[str] = []
    raw_evidence = return_row["evidence_media_ids_json"]
    if raw_evidence:
        try:
            parsed = json.loads(raw_evidence)
            if isinstance(parsed, list):
                evidence_ids = [str(item) for item in parsed]
        except ValueError:
            evidence_ids = []

    return RefundContext(
        return_request_id=return_row["id"],
        order_id=return_row["order_id"],
        customer_user_id=customer_id,
        reason_code=return_row["reason_code"],
        evidence_media_count=len(evidence_ids),
        requested_refund_amount_minor=return_row["requested_refund_amount_minor"],
        order_total_minor=order["total_minor"],
        billing_address_json=order["billing_address_json"],
        delivery_address_json=order["delivery_address_json"],
        payment_provider=payment["provider"] if payment else None,
        payment_status=payment["status"] if payment else None,
        payment_amount_minor=payment["amount_minor"] if payment else None,
        already_refunded_minor=already_refunded_minor,
        account_created_at=account_created_at,
        recent_return_count=recent_return_count,
        lifetime_order_count=lifetime_order_count,
        lifetime_paid_minor=lifetime_paid_minor,
        lifetime_refunded_minor=lifetime_refunded_minor,
    )

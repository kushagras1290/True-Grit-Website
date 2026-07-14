"""Customer-facing commerce: checkout and order history.

All routes require a signed-in customer session. Checkout is server-authoritative
(see services.checkout); order reads are scoped to the calling customer so one
customer can never see another's orders.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import NotFoundError
from truegrit_api.platform.database import Database
from truegrit_api.services.checkout import CheckoutLine, place_order
from truegrit_api.services.email import send_email
from truegrit_api.services.email_templates import render_farm_order_notification, render_order_confirmation
from truegrit_api.services.payments import (
    PaymentError,
    create_razorpay_order,
    verify_razorpay_signature,
)
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["storefront-commerce"])

_PAYMENT_INSERT_SQL = (
    "INSERT INTO payments"
    " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
    "  status, created_at, updated_at)"
    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"
)


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CheckoutItem(_CamelModel):
    variant_id: str = Field(max_length=64)
    quantity: int = Field(ge=1, le=99)


class CheckoutAddress(_CamelModel):
    recipient_name: str = Field(min_length=1, max_length=160)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country_code: str | None = Field(default="IN", max_length=2)
    phone_e164: str | None = Field(default=None, max_length=20)


class CheckoutRequest(_CamelModel):
    items: list[CheckoutItem] = Field(min_length=1)
    delivery_address: CheckoutAddress
    # "cod" | "razorpay" (| "paypal" later). Unknown/unavailable methods fall
    # back to cash-on-delivery so checkout never fails on a bad client value.
    payment_method: str = Field(default="cod", max_length=32)


class RazorpayVerifyRequest(_CamelModel):
    order_id: str = Field(max_length=64)
    razorpay_order_id: str = Field(max_length=128)
    razorpay_payment_id: str = Field(max_length=128)
    razorpay_signature: str = Field(max_length=256)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


@router.post("/checkout")
async def checkout(
    payload: CheckoutRequest,
    request: Request,
    background: BackgroundTasks,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    method = payload.payment_method if payload.payment_method in settings.enabled_payment_methods else "cod"
    result = await place_order(
        db,
        customer,
        _request_id(request),
        items=[
            CheckoutLine(variant_id=item.variant_id, quantity=item.quantity)
            for item in payload.items
        ],
        delivery_address=payload.delivery_address.model_dump(exclude_none=True),
        payment_method=method,
    )
    now = utc_now_iso()

    if method == "razorpay":
        # Create the gateway order, then hand the browser the params its checkout
        # widget needs. Emails wait until the payment is verified.
        razorpay_order_id = await create_razorpay_order(
            settings,
            amount_minor=result["totalMinor"],
            currency=result["currencyCode"],
            receipt=result["reference"],
        )
        await db.execute(
            _PAYMENT_INSERT_SQL,
            (
                new_id("pay"),
                result["id"],
                "razorpay",
                razorpay_order_id,
                result["totalMinor"],
                result["currencyCode"],
                "created",
                now,
                now,
            ),
        )
        result["payment"] = {
            "method": "razorpay",
            "razorpayKeyId": settings.razorpay_key_id,
            "razorpayOrderId": razorpay_order_id,
            "amountMinor": result["totalMinor"],
            "currency": result["currencyCode"],
        }
        return result

    # Cash on delivery: record the pending payment; the order is already confirmed.
    await db.execute(
        _PAYMENT_INSERT_SQL,
        (
            new_id("pay"),
            result["id"],
            "cod",
            None,
            result["totalMinor"],
            result["currencyCode"],
            "pending",
            now,
            now,
        ),
    )
    result["payment"] = {"method": "cod"}
    await _queue_order_emails(db, background, customer, result)
    return result


@router.post("/payments/razorpay/verify")
async def verify_razorpay_payment(
    payload: RazorpayVerifyRequest,
    background: BackgroundTasks,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    # Scope to the caller's own pending-payment order, then verify the signature
    # Razorpay's checkout returned before marking the order paid and confirmed.
    order = await db.fetch_one(
        """
        SELECT id, public_reference, currency_code, total_minor
        FROM orders
        WHERE id = ? AND customer_user_id = ? AND order_status = 'pending_payment'
        """,
        (payload.order_id, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found or already processed.")

    settings = get_settings()
    if not verify_razorpay_signature(
        settings,
        razorpay_order_id=payload.razorpay_order_id,
        razorpay_payment_id=payload.razorpay_payment_id,
        signature=payload.razorpay_signature,
    ):
        raise PaymentError("We could not verify this payment. You were not charged twice.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE payments SET status = 'paid', provider_intent_id = ?, updated_at = ?"
                " WHERE order_id = ? AND provider = 'razorpay'",
                (payload.razorpay_order_id, now, payload.order_id),
            ),
            (
                "UPDATE orders SET payment_status = 'paid', order_status = 'confirmed',"
                " updated_at = ? WHERE id = ? AND customer_user_id = ?",
                (now, payload.order_id, customer.user_id),
            ),
        ]
    )
    result = {
        "id": order["id"],
        "reference": order["public_reference"],
        "currencyCode": order["currency_code"],
        "totalMinor": order["total_minor"],
        "orderStatus": "confirmed",
        "paymentStatus": "paid",
    }
    await _queue_order_emails(db, background, customer, result)
    return {"ok": True, **result}


async def _queue_order_emails(
    db: Database,
    background: BackgroundTasks,
    customer: Principal,
    order: dict[str, Any],
) -> None:
    """Notify the customer and the owner(s) of every farm in the order. Sent in
    the background so email latency never delays the checkout response."""
    settings = get_settings()
    reference = order["reference"]
    total = f"{order['totalMinor'] / 100:.2f} {order['currencyCode']}"
    background.add_task(
        send_email,
        customer.email,
        f"Order {reference} confirmed",
        f"Hi {customer.display_name},\n\nYour order {reference} is confirmed. "
        f"Total {total} (cash on delivery). We'll let you know when it ships.\n\nThank you!",
        settings,
        render_order_confirmation(customer.display_name, reference, total)
    )
    owners = await db.fetch_all(
        """
        SELECT DISTINCT u.email, u.display_name, f.name AS farm_name
        FROM order_items oi
        JOIN products p ON p.id = oi.product_id
        JOIN farms f ON f.id = p.farm_id
        JOIN farm_members fm ON fm.farm_id = p.farm_id
        JOIN users u ON u.id = fm.user_id
        WHERE oi.order_id = ? AND u.status = 'active'
        """,
        (order["id"],),
    )
    for owner in owners:
        background.add_task(
            send_email,
            owner["email"],
            f"Order Received: {reference}",
            f"Hi {owner['display_name']},\n\nAn order ({reference}) has been received for "
            f"{owner['farm_name']}. Please prepare it for fulfilment.",
            settings,
            render_farm_order_notification(
                owner['display_name'], 
                owner['farm_name'], 
                reference, 
                settings.public_admin_url
            )
        )


@router.get("/orders")
async def my_orders(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    rows = await db.fetch_all(
        """
        SELECT id, public_reference, currency_code, total_minor, order_status,
               payment_status, fulfilment_status, placed_at, created_at,
               (SELECT COUNT(*) FROM order_items WHERE order_id = orders.id) AS item_count
        FROM orders
        WHERE customer_user_id = ?
        ORDER BY COALESCE(placed_at, created_at) DESC
        LIMIT 50
        """,
        (customer.user_id,),
    )
    return {
        "items": [
            {
                "reference": row["public_reference"],
                "currencyCode": row["currency_code"],
                "totalMinor": row["total_minor"],
                "orderStatus": row["order_status"],
                "paymentStatus": row["payment_status"],
                "fulfilmentStatus": row["fulfilment_status"],
                "placedAt": row["placed_at"] or row["created_at"],
                "itemCount": row["item_count"],
            }
            for row in rows
        ]
    }


@router.get("/orders/{reference}")
async def my_order_detail(
    reference: str,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    order = await db.fetch_one(
        """
        SELECT id, public_reference, currency_code, subtotal_minor, discount_minor,
               delivery_minor, tax_minor, total_minor, order_status, payment_status,
               fulfilment_status, delivery_status, delivery_address_json, placed_at, created_at
        FROM orders
        WHERE public_reference = ? AND customer_user_id = ?
        """,
        (reference, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    items = await db.fetch_all(
        """
        SELECT id, product_name, variant_name, sku, quantity,
               unit_effective_amount_minor, line_total_minor
        FROM order_items WHERE order_id = ? ORDER BY product_name
        """,
        (order["id"],),
    )
    return {
        "reference": order["public_reference"],
        "currencyCode": order["currency_code"],
        "subtotalMinor": order["subtotal_minor"],
        "deliveryMinor": order["delivery_minor"],
        "discountMinor": order["discount_minor"],
        "taxMinor": order["tax_minor"],
        "totalMinor": order["total_minor"],
        "orderStatus": order["order_status"],
        "paymentStatus": order["payment_status"],
        "fulfilmentStatus": order["fulfilment_status"],
        "placedAt": order["placed_at"] or order["created_at"],
        "items": [
            {
                "id": item["id"],
                "productName": item["product_name"],
                "variantName": item["variant_name"],
                "sku": item["sku"],
                "quantity": item["quantity"],
                "unitMinor": item["unit_effective_amount_minor"],
                "lineTotalMinor": item["line_total_minor"],
            }
            for item in items
        ],
    }

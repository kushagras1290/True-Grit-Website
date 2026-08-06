"""Customer-facing commerce: checkout and order history.

All routes require a signed-in customer session. Checkout is server-authoritative
(see services.checkout); order reads are scoped to the calling customer so one
customer can never see another's orders.
"""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.domain.money import MAX_AMOUNT_MINOR
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import ReturnRequestRepository
from truegrit_api.services import addresses as address_service
from truegrit_api.services import subscriptions as subscription_service
from truegrit_api.services import wishlist as wishlist_service
from truegrit_api.services.checkout import CheckoutLine, place_order
from truegrit_api.services.contact import contactable_email
from truegrit_api.services.email_templates import (
    render_farm_order_notification,
    render_order_confirmation,
)
from truegrit_api.services.feature_settings import (
    gift_cards_enabled,
    load_delivery_settings,
    promotions_enabled,
)
from truegrit_api.services.gift_cards import resolve_checkout_redemption
from truegrit_api.services.jobs import enqueue_email
from truegrit_api.services.payments import (
    PaymentError,
    capture_paypal_order,
    create_paypal_order,
    create_razorpay_order,
    verify_razorpay_signature,
)
from truegrit_api.services.promotions import resolve_checkout_discount
from truegrit_api.services.returns import create_return_request
from truegrit_api.services.reviews import create_review
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
    # Client-generated once per checkout attempt-group (the storefront mints
    # one when the checkout page first loads and reuses it across retries of
    # the same submission). Optional so an older client without one still
    # checks out normally, just without retry protection.
    idempotency_key: str | None = Field(default=None, max_length=80)
    coupon_code: str | None = Field(default=None, max_length=32)
    gift_card_code: str | None = Field(default=None, max_length=24)


class DiscountPreviewRequest(_CamelModel):
    coupon_code: str = Field(min_length=1, max_length=32)
    subtotal_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)


class GiftCardPreviewRequest(_CamelModel):
    gift_card_code: str = Field(min_length=1, max_length=24)
    # What the gift card would be applied against -- the checkout page's
    # current subtotal + delivery - other discounts, exactly what
    # `place_order` itself resolves the redemption against.
    amount_needed_minor: int = Field(ge=0, le=MAX_AMOUNT_MINOR)


class PaypalCaptureRequest(_CamelModel):
    order_id: str = Field(max_length=64)
    paypal_order_id: str = Field(max_length=64)


class RazorpayVerifyRequest(_CamelModel):
    order_id: str = Field(max_length=64)
    razorpay_order_id: str = Field(max_length=128)
    razorpay_payment_id: str = Field(max_length=128)
    razorpay_signature: str = Field(max_length=256)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


_ADDRESS_FIELD_MAP = {
    "recipient_name": "recipientName",
    "phone_e164": "phoneE164",
    "line1": "line1",
    "line2": "line2",
    "city": "city",
    "state": "state",
    "postal_code": "postalCode",
    "country_code": "countryCode",
}


def _camel_address(address_json: str | None) -> dict[str, Any] | None:
    """`orders.delivery_address_json` is written by
    `services.checkout._validate_address` with the snake_case keys
    `CheckoutAddress` posts -- translated here to camelCase to match every
    other response shape in this API."""
    if not address_json:
        return None
    stored = json.loads(address_json)
    return {camel: stored[snake] for snake, camel in _ADDRESS_FIELD_MAP.items() if snake in stored}


@router.post("/checkout/preview-discount")
async def preview_discount(
    payload: DiscountPreviewRequest,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """What a coupon code would do to this basket, without placing an order or
    recording a redemption -- so the checkout box can show a real amount
    before the customer commits, rather than "type it and see". Uses the same
    `resolve_checkout_discount` that `place_order` calls, so the preview can
    never promise a discount checkout would then refuse to honour.
    """
    if not await promotions_enabled(db):
        raise ValidationAppError("Coupons are not available right now.")
    delivery_settings = await load_delivery_settings(db)
    delivery_minor = (
        0
        if payload.subtotal_minor >= delivery_settings.free_threshold_minor
        else delivery_settings.fee_minor
    )
    applied = await resolve_checkout_discount(
        db,
        subtotal_minor=payload.subtotal_minor,
        delivery_minor=delivery_minor,
        coupon_code=payload.coupon_code,
        customer_user_id=customer.user_id,
    )
    if applied is None:
        raise ValidationAppError("This code is not valid.")
    return {
        "code": applied["code"],
        "headline": applied["headline"],
        "discountMinor": 0 if applied["free_delivery"] else applied["discount_minor"],
        "freeDelivery": applied["free_delivery"],
        "deliveryMinor": 0 if applied["free_delivery"] else delivery_minor,
    }


@router.post("/checkout/preview-gift-card")
async def preview_gift_card(
    payload: GiftCardPreviewRequest,
    _customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """What a gift card code would cover toward `amountNeededMinor`, without
    placing an order or recording a redemption -- the gift-card equivalent of
    `preview_discount`, same reasoning: uses the exact `resolve_checkout_
    redemption` function `place_order` calls, so the preview can never
    promise an amount checkout would then refuse to honour."""
    if not await gift_cards_enabled(db):
        raise ValidationAppError("Gift cards are not available right now.")
    applied = await resolve_checkout_redemption(
        db, code=payload.gift_card_code, amount_needed_minor=payload.amount_needed_minor
    )
    if applied is None:
        raise ValidationAppError("This code is not valid.")
    return {
        "code": applied["code"],
        "appliedMinor": applied["applied_minor"],
        "balanceMinor": applied["balance_minor"],
        "remainingAfterMinor": applied["remaining_after_minor"],
    }


@router.post("/checkout")
async def checkout(
    payload: CheckoutRequest,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    # The owner's kill-switch is enforced inside `place_order` -> `_resolve_line`
    # now, not here: a blanket pre-check here could never widen for a product
    # an owner has explicitly force-enabled (migration 0069), so the switch is
    # evaluated per line, against each product's own override, at the one spot
    # that already re-validates price and stock rather than trusting the
    # browser cart.
    method = (
        payload.payment_method
        if payload.payment_method in settings.enabled_payment_methods
        else "cod"
    )
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
        idempotency_key=payload.idempotency_key,
        coupon_code=payload.coupon_code,
        gift_card_code=payload.gift_card_code,
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

    if method == "paypal":
        # International lane: the order stays priced in INR, but the buyer is
        # charged in `paypal_currency` because PayPal cannot settle INR to an
        # Indian merchant. Store the converted amount on the payment row so the
        # capture can be checked against exactly what we asked PayPal for.
        paypal = await create_paypal_order(
            settings,
            amount_minor=result["totalMinor"],
            currency=result["currencyCode"],
            reference=result["reference"],
        )
        await db.execute(
            _PAYMENT_INSERT_SQL,
            (
                new_id("pay"),
                result["id"],
                "paypal",
                paypal["paypalOrderId"],
                paypal["chargeMinor"],
                paypal["chargeCurrency"],
                "created",
                now,
                now,
            ),
        )
        result["payment"] = {
            "method": "paypal",
            "paypalClientId": settings.paypal_client_id,
            "paypalOrderId": paypal["paypalOrderId"],
            "amountMinor": paypal["chargeMinor"],
            "currency": paypal["chargeCurrency"],
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
    await _queue_order_emails(db, customer, result)
    return result


@router.post("/payments/paypal/capture")
async def capture_paypal_payment(
    payload: PaypalCaptureRequest,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Capture an approved PayPal order and mark ours paid.

    Unlike Razorpay — where the browser returns a signature we can check offline
    — PayPal only becomes money when *we* call capture. So the browser's report
    is never trusted: we look up our own payment row, capture against the id we
    stored, and check the captured amount matches what we asked for.
    """
    order = await db.fetch_one(
        """
        SELECT o.id, o.public_reference, o.currency_code, o.total_minor,
               p.provider_reference, p.amount_minor AS charge_minor, p.status AS payment_status
        FROM orders o
        JOIN payments p ON p.order_id = o.id AND p.provider = 'paypal'
        WHERE o.id = ? AND o.customer_user_id = ? AND o.order_status = 'pending_payment'
        """,
        (payload.order_id, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found or already processed.")
    # Capture the id we created, not the one the client handed us. Trusting the
    # client's id would let it swap in some other (cheaper) PayPal order.
    if str(order["provider_reference"]) != payload.paypal_order_id:
        raise PaymentError("This payment does not belong to that order.")
    if str(order["payment_status"]) == "paid":
        raise ConflictError("This order has already been paid.")

    capture_id = await capture_paypal_order(
        get_settings(),
        paypal_order_id=str(order["provider_reference"]),
        expected_minor=int(order["charge_minor"]),
    )

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE payments SET status = 'paid', provider_intent_id = ?, updated_at = ?"
                " WHERE order_id = ? AND provider = 'paypal'",
                (capture_id, now, payload.order_id),
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
    await _queue_order_emails(db, customer, result)
    return {"ok": True, **result}


@router.post("/payments/razorpay/verify")
async def verify_razorpay_payment(
    payload: RazorpayVerifyRequest,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    # Scope to the caller's own pending-payment order, then verify the signature
    # Razorpay's checkout returned before marking the order paid and confirmed.
    order = await db.fetch_one(
        """
        SELECT o.id, o.public_reference, o.currency_code, o.total_minor,
               p.provider_intent_id, p.status AS payment_status
        FROM orders o
        JOIN payments p ON p.order_id = o.id AND p.provider = 'razorpay'
        WHERE o.id = ? AND o.customer_user_id = ? AND o.order_status = 'pending_payment'
        """,
        (payload.order_id, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found or already processed.")
    # Verify against the Razorpay order *we* created for this order, not the one
    # the client handed us. A signature is only proof that a
    # (razorpay_order_id, payment_id, signature) triple is internally
    # consistent -- it says nothing about which of the merchant's Razorpay
    # orders that triple belongs to. Trusting the client's razorpay_order_id
    # would let a real payment for one (cheap) order verify a different
    # (expensive) one. Mirrors the equivalent check in capture_paypal_payment.
    if str(order["provider_intent_id"]) != payload.razorpay_order_id:
        raise PaymentError("This payment does not belong to that order.")
    if str(order["payment_status"]) == "paid":
        raise ConflictError("This order has already been paid.")

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
                " WHERE order_id = ? AND provider = 'razorpay' AND provider_intent_id = ?",
                (payload.razorpay_order_id, now, payload.order_id, payload.razorpay_order_id),
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
    await _queue_order_emails(db, customer, result)
    return {"ok": True, **result}


async def _queue_order_emails(
    db: Database,
    customer: Principal,
    order: dict[str, Any],
) -> None:
    """Persist durable customer and farm-owner notification jobs."""
    settings = get_settings()
    reference = order["reference"]
    total = f"{order['totalMinor'] / 100:.2f} {order['currencyCode']}"
    # A customer who signed up with a mobile has no address — only the
    # `@phone.invalid` placeholder that satisfies users.email NOT NULL. Skip the
    # email rather than hand the mail server something undeliverable; they get
    # the same status from the order page, and SMS order updates would be a
    # separate (chargeable) piece of work.
    customer_email = contactable_email(customer.email)
    if customer_email is not None:
        await enqueue_email(
            db,
            dedupe_key=f"order:{order['id']}:customer-confirmed",
            to=customer_email,
            subject=f"Order {reference} confirmed",
            body=f"Hi {customer.display_name},\n\nYour order {reference} is confirmed. "
            f"Total {total} (cash on delivery). We'll let you know when it ships.\n\nThank you!",
            html_body=render_order_confirmation(customer.display_name, reference, total),
            aggregate_type="order",
            aggregate_id=order["id"],
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
        await enqueue_email(
            db,
            dedupe_key=f"order:{order['id']}:farm-owner:{owner['email']}:{owner['farm_name']}",
            to=owner["email"],
            subject=f"Order Received: {reference}",
            body=f"Hi {owner['display_name']},\n\nAn order ({reference}) has been received for "
            f"{owner['farm_name']}. Please prepare it for fulfilment.",
            html_body=render_farm_order_notification(
                owner["display_name"], owner["farm_name"], reference, settings.public_admin_url
            ),
            aggregate_type="order",
            aggregate_id=order["id"],
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
        SELECT oi.id, oi.product_id, p.slug AS product_slug, oi.product_name,
               oi.variant_name, oi.sku, oi.quantity,
               oi.unit_effective_amount_minor, oi.line_total_minor
        FROM order_items oi
        LEFT JOIN products p ON p.id = oi.product_id
        WHERE oi.order_id = ? ORDER BY oi.product_name
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
        "deliveryAddress": _camel_address(order["delivery_address_json"]),
        "items": [
            {
                "id": item["id"],
                # Null only when the product was later deleted (`order_items.product_id`
                # is `ON DELETE SET NULL`) -- the storefront hides the "write a
                # review" action for that line rather than posting a review
                # against nothing.
                "productId": item["product_id"],
                "productSlug": item["product_slug"],
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


class ReturnRequestCreate(_CamelModel):
    order_item_id: str | None = Field(default=None, max_length=64)
    reason_code: str = Field(min_length=1, max_length=32)
    description: str = Field(min_length=10, max_length=2000)
    requested_refund_amount_minor: int | None = Field(default=None, ge=0)
    evidence_media_ids: list[str] = Field(default_factory=list, max_length=6)


def _return_request_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderReference": row["public_reference"],
        "reasonCode": row["reason_code"],
        "status": row["status"],
        "resolutionType": row["resolution_type"],
        "requestedAt": row["requested_at"],
        "resolvedAt": row["resolved_at"],
    }


@router.get("/orders/{reference}/return-requests")
async def my_return_requests(
    reference: str,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    order = await db.fetch_one(
        "SELECT id FROM orders WHERE public_reference = ? AND customer_user_id = ?",
        (reference, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    rows = await ReturnRequestRepository(db).list_for_customer(customer.user_id)
    return {
        "items": [_return_request_payload(row) for row in rows if row["order_id"] == order["id"]]
    }


@router.post("/orders/{reference}/return-requests")
async def create_my_return_request(
    reference: str,
    payload: ReturnRequestCreate,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    order = await db.fetch_one(
        "SELECT id FROM orders WHERE public_reference = ? AND customer_user_id = ?",
        (reference, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    return await create_return_request(
        db,
        customer,
        getattr(request.state, "request_id", "unknown"),
        order_id=order["id"],
        order_item_id=payload.order_item_id,
        reason_code=payload.reason_code,
        description=payload.description,
        requested_refund_amount_minor=payload.requested_refund_amount_minor,
        evidence_media_ids=payload.evidence_media_ids,
    )


class ReviewCreate(_CamelModel):
    product_id: str = Field(min_length=1, max_length=64)
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=120)
    body: str = Field(min_length=10, max_length=4000)


def _review_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productId": row["product_id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "rating": row["rating"],
        "title": row["title"],
        "body": row["body"],
        "status": row["status"],
        "createdAt": row["created_at"],
    }


@router.get("/orders/{reference}/reviews")
async def my_order_reviews(
    reference: str,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Every review the calling customer has written against this order,
    whatever its moderation status -- lets the order page show "pending",
    "published" or "not reviewed yet" per line item without a second query."""
    order = await db.fetch_one(
        "SELECT id FROM orders WHERE public_reference = ? AND customer_user_id = ?",
        (reference, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    rows = await db.fetch_all(
        """
        SELECT r.id, r.product_id, r.rating, r.title, r.body, r.status, r.created_at,
               p.name AS product_name, p.slug AS product_slug
        FROM reviews r
        JOIN products p ON p.id = r.product_id
        WHERE r.order_id = ? AND r.customer_user_id = ?
        ORDER BY r.created_at DESC
        """,
        (order["id"], customer.user_id),
    )
    return {"items": [_review_payload(row) for row in rows]}


@router.post("/orders/{reference}/reviews")
async def create_my_review(
    reference: str,
    payload: ReviewCreate,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    order = await db.fetch_one(
        "SELECT id FROM orders WHERE public_reference = ? AND customer_user_id = ?",
        (reference, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    return await create_review(
        db,
        customer,
        getattr(request.state, "request_id", "unknown"),
        product_id=payload.product_id,
        order_id=order["id"],
        rating=payload.rating,
        title=payload.title,
        body=payload.body,
    )


# ---------------------------------------------------------------------------
# Delivery addresses (migration 0005, dormant until now -- see the module
# docstring in services.addresses for why). Reusable, unlike the ad-hoc
# address `place_order`'s own CheckoutAddress takes on every ordinary
# checkout: a subscription's renewal has no request to take one from, so it
# needs somewhere to keep pointing.
# ---------------------------------------------------------------------------


class AddressCreate(_CamelModel):
    label: str | None = Field(default=None, max_length=60)
    recipient_name: str = Field(min_length=1, max_length=150)
    phone_e164: str | None = Field(default=None, max_length=20)
    line1: str = Field(min_length=1, max_length=200)
    line2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country_code: str | None = Field(default="IN", max_length=2)


@router.get("/addresses")
async def list_my_addresses_endpoint(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return {"items": await address_service.list_my_addresses(db, customer)}


@router.post("/addresses")
async def create_my_address_endpoint(
    payload: AddressCreate,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await address_service.create_address(
        db,
        customer,
        label=payload.label,
        recipient_name=payload.recipient_name,
        phone_e164=payload.phone_e164,
        line1=payload.line1,
        line2=payload.line2,
        city=payload.city,
        state=payload.state,
        postal_code=payload.postal_code,
        country_code=payload.country_code,
    )


@router.delete("/addresses/{address_id}")
async def archive_my_address_endpoint(
    address_id: str,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await address_service.archive_address(db, customer, address_id)
    return {"id": address_id, "archived": True}


# ---------------------------------------------------------------------------
# Subscriptions (migration 0064): "Subscribe & Save" on a single product
# variant, gated on the sitewide switch (services.feature_settings
# `subscriptions_enabled`) -- off until an owner turns it on. See the module
# docstring in services.subscriptions for the cash-on-delivery-only decision.
# ---------------------------------------------------------------------------


class SubscriptionCreate(_CamelModel):
    variant_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=12)
    frequency: str = Field(min_length=1, max_length=20)
    address_id: str = Field(min_length=1, max_length=64)


class SubscriptionUpdate(_CamelModel):
    quantity: int | None = Field(default=None, ge=1, le=12)
    frequency: str | None = Field(default=None, max_length=20)
    address_id: str | None = Field(default=None, max_length=64)


@router.get("/subscriptions")
async def list_my_subscriptions_endpoint(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
    status: str | None = None,
) -> Any:
    return {"items": await subscription_service.list_my_subscriptions(db, customer, status=status)}


@router.post("/subscriptions")
async def create_my_subscription_endpoint(
    payload: SubscriptionCreate,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await subscription_service.create_subscription(
        db,
        customer,
        _request_id(request),
        variant_id=payload.variant_id,
        quantity=payload.quantity,
        frequency=payload.frequency,
        address_id=payload.address_id,
    )


@router.patch("/subscriptions/{subscription_id}")
async def update_my_subscription_endpoint(
    subscription_id: str,
    payload: SubscriptionUpdate,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await subscription_service.update_subscription(
        db,
        customer,
        _request_id(request),
        subscription_id,
        quantity=payload.quantity,
        frequency=payload.frequency,
        address_id=payload.address_id,
    )


@router.post("/subscriptions/{subscription_id}/pause")
async def pause_my_subscription_endpoint(
    subscription_id: str,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await subscription_service.pause_subscription(
        db, customer, _request_id(request), subscription_id
    )


@router.post("/subscriptions/{subscription_id}/resume")
async def resume_my_subscription_endpoint(
    subscription_id: str,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await subscription_service.resume_subscription(
        db, customer, _request_id(request), subscription_id
    )


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_my_subscription_endpoint(
    subscription_id: str,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await subscription_service.cancel_subscription(
        db, customer, _request_id(request), subscription_id
    )


class WishlistCreate(_CamelModel):
    product_id: str = Field(min_length=1, max_length=64)


@router.get("/wishlist")
async def list_my_wishlist_endpoint(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return {"items": await wishlist_service.list_my_wishlist(db, customer)}


@router.get("/wishlist/product-ids")
async def list_my_wishlist_product_ids_endpoint(
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return {"productIds": await wishlist_service.list_wishlist_product_ids(db, customer)}


@router.post("/wishlist")
async def add_to_my_wishlist_endpoint(
    payload: WishlistCreate,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await wishlist_service.add_to_wishlist(
        db, customer, _request_id(request), product_id=payload.product_id
    )


@router.delete("/wishlist/{product_id}")
async def remove_from_my_wishlist_endpoint(
    product_id: str,
    request: Request,
    customer: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await wishlist_service.remove_from_wishlist(
        db, customer, _request_id(request), product_id=product_id
    )
    return {"productId": product_id, "removed": True}

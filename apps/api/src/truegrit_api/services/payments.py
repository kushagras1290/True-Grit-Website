"""Payment gateway integration.

Cash-on-delivery needs no gateway. Razorpay follows the standard order flow:
create a server-side order, hand the client the order id + public key, then
verify the signed result the browser returns. All credentials come from
``Settings`` (env vars / Worker secrets); outbound calls use the async Workers
`fetch`. Amounts are always in the currency's minor unit (paise for INR).

PayPal is the international lane and works differently from Razorpay in two ways
that matter:

* **Cross-border only.** PayPal closed its domestic India business on 1 April
  2021, so an Indian merchant cannot take INR from an Indian customer. The
  supported direction is an overseas buyer paying an Indian merchant, so PayPal
  charges in `paypal_currency` (never INR) and the INR order total is converted
  at the operator-set `paypal_inr_per_unit` rate.
* **Capture, not signature.** Razorpay hands the browser a signed result we can
  verify offline. PayPal instead requires a server-side capture call against its
  API, so authority over "was this actually paid" comes from our own outbound
  request, not from anything the client passes us.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from truegrit_api.config import Settings
from truegrit_api.errors import ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.http import HttpError, post_form_async, post_json_async

_RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"
_RAZORPAY_PAYMENTS_URL = "https://api.razorpay.com/v1/payments"
_STRIPE_REFUNDS_URL = "https://api.stripe.com/v1/refunds"
# Both INR and every currency PayPal is likely to be configured with here (USD,
# GBP, EUR, AUD, CAD, SGD) are two-decimal. A zero-decimal presentment currency
# (JPY) would need its own exponent table; `paypal_currency` is validated against
# this list rather than silently mispricing by 100x.
_MINOR_UNIT_EXPONENT = 2
_SUPPORTED_PAYPAL_CURRENCIES = frozenset({"USD", "GBP", "EUR", "AUD", "CAD", "SGD"})


class PaymentError(ValidationAppError):
    """A payment could not be created or verified."""


async def create_razorpay_order(
    settings: Settings, *, amount_minor: int, currency: str, receipt: str
) -> str:
    """Create a Razorpay order and return its id (``order_...``)."""
    if not settings.razorpay_enabled:
        raise PaymentError("Online card/UPI payment is not available right now.")
    credentials = f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode()
    authorization = "Basic " + base64.b64encode(credentials).decode("ascii")
    try:
        result = await post_json_async(
            _RAZORPAY_ORDERS_URL,
            body={
                "amount": amount_minor,
                "currency": currency,
                "receipt": receipt,
                "payment_capture": 1,
            },
            headers={"authorization": authorization},
        )
    except HttpError as exc:
        raise PaymentError("Could not start the payment. Please try again.") from exc
    order_id = (result or {}).get("id")
    if not order_id:
        raise PaymentError("The payment provider did not return an order id.")
    return str(order_id)


def verify_razorpay_signature(
    settings: Settings, *, razorpay_order_id: str, razorpay_payment_id: str, signature: str
) -> bool:
    """Verify the checkout signature Razorpay returns to the browser.

    Razorpay signs ``"{order_id}|{payment_id}"`` with HMAC-SHA256 keyed by the
    account secret. Compared in constant time to resist timing attacks.
    """
    if not (settings.razorpay_key_secret and razorpay_order_id and razorpay_payment_id):
        return False
    expected = hmac.new(
        settings.razorpay_key_secret.encode("utf-8"),
        f"{razorpay_order_id}|{razorpay_payment_id}".encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


async def refund_razorpay_payment(
    settings: Settings, *, payment_id: str, amount_minor: int, idempotency_key: str
) -> str:
    """Refund (fully or partially) a captured Razorpay payment and return the
    refund id. `idempotency_key` — Razorpay's own retry-safety header — should
    be derived from the caller's own refund record id, so a retried request
    after a dropped response can never create a second refund at Razorpay."""
    if not settings.razorpay_enabled:
        raise PaymentError("Online refunds are not available right now.")
    credentials = f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode()
    authorization = "Basic " + base64.b64encode(credentials).decode("ascii")
    try:
        result = await post_json_async(
            f"{_RAZORPAY_PAYMENTS_URL}/{payment_id}/refund",
            body={"amount": amount_minor},
            headers={
                "authorization": authorization,
                "X-Razorpay-Idempotency-Key": idempotency_key,
            },
        )
    except HttpError as exc:
        raise PaymentError("The refund could not be processed. Please try again.") from exc
    refund_id = (result or {}).get("id")
    if not refund_id:
        raise PaymentError("The payment provider did not confirm the refund.")
    return str(refund_id)


# --- PayPal (international) --------------------------------------------------


def convert_inr_minor_to_paypal_minor(settings: Settings, inr_minor: int) -> int:
    """Convert an INR order total into `paypal_currency` minor units.

    Uses Decimal, not float: a binary float cannot hold 0.01 exactly, and money
    that is off by a paise per order is money that reconciles wrong forever.
    Rounds half-up (the way a person expects) and never down to zero — a nonzero
    order must never become a free one because the rate made it tiny.
    """
    currency = settings.paypal_currency.upper()
    if currency not in _SUPPORTED_PAYPAL_CURRENCIES:
        raise PaymentError("International payment is not available right now.")
    rate = Decimal(str(settings.paypal_inr_per_unit))
    if rate <= 0:
        raise PaymentError("International payment is not available right now.")
    minor_scale = Decimal(10) ** _MINOR_UNIT_EXPONENT
    major = (Decimal(inr_minor) / minor_scale) / rate
    minor = int((major * minor_scale).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return max(minor, 1) if inr_minor > 0 else 0


def format_paypal_amount(minor: int) -> str:
    """PayPal wants the amount as a fixed-precision decimal string ("11.35"),
    not a number — floats in a money field are how you end up sending 11.350000000000001."""
    return str((Decimal(minor) / (Decimal(10) ** _MINOR_UNIT_EXPONENT)).quantize(Decimal("0.01")))


async def _paypal_access_token(settings: Settings) -> str:
    """Fetch an OAuth2 client-credentials token.

    Not cached: Workers isolates are short-lived and shared-nothing, so a cache
    here would buy little and risk serving a token across a config change. One
    extra round trip per checkout is the cheaper mistake.
    """
    credentials = f"{settings.paypal_client_id}:{settings.paypal_secret}".encode()
    try:
        result = await post_form_async(
            f"{settings.paypal_api_base}/v1/oauth2/token",
            form={"grant_type": "client_credentials"},
            headers={"authorization": "Basic " + base64.b64encode(credentials).decode("ascii")},
        )
    except HttpError as exc:
        log_event("error", "paypal_token_failed", error_type=type(exc).__name__)
        raise PaymentError("Could not start the payment. Please try again.") from exc
    token = (result or {}).get("access_token")
    if not token:
        raise PaymentError("Could not start the payment. Please try again.")
    return str(token)


async def create_paypal_order(
    settings: Settings, *, amount_minor: int, currency: str, reference: str
) -> dict[str, Any]:
    """Create a PayPal order for an INR total and return the params the browser
    needs. `amount_minor`/`currency` describe the *order* (INR); the charge is
    converted to `paypal_currency` because PayPal cannot settle INR to an Indian
    merchant."""
    if not settings.paypal_enabled:
        raise PaymentError("International payment is not available right now.")
    if currency.upper() != "INR":
        # The conversion below assumes the order is priced in INR. Fail loudly
        # rather than quietly charge the wrong number.
        raise PaymentError("International payment is not available for this order.")

    charge_minor = convert_inr_minor_to_paypal_minor(settings, amount_minor)
    charge_currency = settings.paypal_currency.upper()
    token = await _paypal_access_token(settings)
    try:
        result = await post_json_async(
            f"{settings.paypal_api_base}/v2/checkout/orders",
            body={
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "reference_id": reference,
                        "custom_id": reference,
                        "description": f"True Grit order {reference}",
                        "amount": {
                            "currency_code": charge_currency,
                            "value": format_paypal_amount(charge_minor),
                        },
                    }
                ],
            },
            headers={"authorization": f"Bearer {token}"},
        )
    except HttpError as exc:
        log_event(
            "error", "paypal_create_failed", reference=reference, error_type=type(exc).__name__
        )
        raise PaymentError("Could not start the payment. Please try again.") from exc

    paypal_order_id = (result or {}).get("id")
    if not paypal_order_id:
        raise PaymentError("The payment provider did not return an order id.")
    return {
        "paypalOrderId": str(paypal_order_id),
        "chargeMinor": charge_minor,
        "chargeCurrency": charge_currency,
    }


async def capture_paypal_order(
    settings: Settings, *, paypal_order_id: str, expected_minor: int
) -> str:
    """Capture an approved PayPal order and return the capture id.

    This call — not anything the browser reports — is what makes a PayPal order
    paid. The captured amount is checked against what we priced, so a client that
    approves a different order cannot mark this one settled.
    """
    if not settings.paypal_enabled:
        raise PaymentError("International payment is not available right now.")
    token = await _paypal_access_token(settings)
    try:
        result = await post_json_async(
            f"{settings.paypal_api_base}/v2/checkout/orders/{paypal_order_id}/capture",
            body={},
            headers={"authorization": f"Bearer {token}"},
        )
    except HttpError as exc:
        log_event(
            "error",
            "paypal_capture_failed",
            paypal_order_id=paypal_order_id,
            error_type=type(exc).__name__,
        )
        raise PaymentError(
            "We could not confirm this payment. You were not charged twice."
        ) from exc

    if not isinstance(result, dict) or result.get("status") != "COMPLETED":
        raise PaymentError("This payment was not completed.")

    capture = _first_capture(result)
    if capture is None:
        raise PaymentError("This payment was not completed.")
    if str(capture.get("status")) != "COMPLETED":
        raise PaymentError("This payment was not completed.")

    amount = capture.get("amount") or {}
    captured_currency = str(amount.get("currency_code", "")).upper()
    captured_value = str(amount.get("value", "0"))
    if captured_currency != settings.paypal_currency.upper():
        raise PaymentError("This payment was taken in an unexpected currency.")
    if _to_minor(captured_value) != expected_minor:
        # Amount mismatch means the approved order is not the one we priced.
        log_event(
            "error",
            "paypal_amount_mismatch",
            paypal_order_id=paypal_order_id,
            expected_minor=expected_minor,
            captured=captured_value,
        )
        raise PaymentError("This payment did not match the order total.")

    capture_id = capture.get("id")
    if not capture_id:
        raise PaymentError("This payment was not completed.")
    return str(capture_id)


async def refund_paypal_capture(
    settings: Settings,
    *,
    capture_id: str,
    amount_minor: int,
    currency: str,
    idempotency_key: str,
) -> str:
    """Refund (fully or partially) a captured PayPal payment and return the
    refund id. `idempotency_key` maps to PayPal's own `PayPal-Request-Id`
    retry-safety header, for the same reason `refund_razorpay_payment` takes
    one: a retried request after a dropped response must not double-refund."""
    if not settings.paypal_enabled:
        raise PaymentError("International refunds are not available right now.")
    token = await _paypal_access_token(settings)
    try:
        result = await post_json_async(
            f"{settings.paypal_api_base}/v2/payments/captures/{capture_id}/refund",
            body={
                "amount": {
                    "currency_code": currency,
                    "value": format_paypal_amount(amount_minor),
                }
            },
            headers={
                "authorization": f"Bearer {token}",
                "PayPal-Request-Id": idempotency_key,
            },
        )
    except HttpError as exc:
        log_event(
            "error", "paypal_refund_failed", capture_id=capture_id, error_type=type(exc).__name__
        )
        raise PaymentError("The refund could not be processed. Please try again.") from exc
    if not isinstance(result, dict) or result.get("status") not in {"COMPLETED", "PENDING"}:
        raise PaymentError("The payment provider did not confirm the refund.")
    refund_id = result.get("id")
    if not refund_id:
        raise PaymentError("The payment provider did not confirm the refund.")
    return str(refund_id)


# --- Stripe (cards, global) ---------------------------------------------------
#
# No order-creation or capture flow exists yet here -- `config.py`'s
# `payment_stripe_visible` is deliberately off until that is built and tested,
# so `provider = 'stripe'` never appears on a real `payments` row today. This
# refund function exists ahead of that so the moment Stripe checkout ships and
# starts writing `provider_intent_id` as the PaymentIntent id (`pi_...`),
# refunds -- both a staff-issued one and the refund orchestrator's automatic
# one -- already work with no further change on the refund side.


async def refund_stripe_payment(
    settings: Settings, *, payment_intent_id: str, amount_minor: int, idempotency_key: str
) -> str:
    """Refund (fully or partially) a captured Stripe PaymentIntent and return
    the refund id. `idempotency_key` maps to Stripe's own `Idempotency-Key`
    header, the same retry-safety contract `refund_razorpay_payment` and
    `refund_paypal_capture` each give their own gateway. Stripe amounts are
    already expressed in the currency's smallest unit, the same convention
    `amount_minor` uses everywhere else in this codebase, so no conversion is
    needed the way PayPal's INR-to-`paypal_currency` conversion is."""
    if not settings.stripe_enabled:
        raise PaymentError("Online refunds are not available right now.")
    authorization = "Basic " + base64.b64encode(f"{settings.stripe_secret_key}:".encode()).decode(
        "ascii"
    )
    try:
        result = await post_form_async(
            _STRIPE_REFUNDS_URL,
            form={"payment_intent": payment_intent_id, "amount": str(amount_minor)},
            headers={
                "authorization": authorization,
                "Idempotency-Key": idempotency_key,
            },
        )
    except HttpError as exc:
        log_event(
            "error",
            "stripe_refund_failed",
            payment_intent_id=payment_intent_id,
            error_type=type(exc).__name__,
        )
        raise PaymentError("The refund could not be processed. Please try again.") from exc
    if not isinstance(result, dict) or result.get("status") not in {"succeeded", "pending"}:
        raise PaymentError("The payment provider did not confirm the refund.")
    refund_id = result.get("id")
    if not refund_id:
        raise PaymentError("The payment provider did not confirm the refund.")
    return str(refund_id)


def _first_capture(result: dict[str, Any]) -> dict[str, Any] | None:
    units = result.get("purchase_units")
    if not isinstance(units, list) or not units:
        return None
    payments = units[0].get("payments") if isinstance(units[0], dict) else None
    captures = payments.get("captures") if isinstance(payments, dict) else None
    if not isinstance(captures, list) or not captures:
        return None
    return captures[0] if isinstance(captures[0], dict) else None


def _to_minor(value: str) -> int:
    try:
        return int(
            (Decimal(value) * (Decimal(10) ** _MINOR_UNIT_EXPONENT)).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        )
    except (ArithmeticError, ValueError):
        return -1

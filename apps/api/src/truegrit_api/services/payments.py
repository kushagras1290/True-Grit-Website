"""Payment gateway integration.

Cash-on-delivery needs no gateway. Razorpay follows the standard order flow:
create a server-side order, hand the client the order id + public key, then
verify the signed result the browser returns. All credentials come from
``Settings`` (env vars / Worker secrets); outbound calls use the async Workers
`fetch`. Amounts are always in the currency's minor unit (paise for INR).
"""

from __future__ import annotations

import base64
import hashlib
import hmac

from truegrit_api.config import Settings
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.http import HttpError, post_json_async

_RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


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

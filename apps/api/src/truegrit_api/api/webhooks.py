"""Payment gateway webhooks: server-to-server payment confirmation.

The storefront's own confirm endpoints (`api.storefront.capture_paypal_payment`,
`api.storefront.verify_razorpay_payment`) are client-driven: the browser calls
them once its checkout widget finishes. If the tab closes, the network drops,
or the process crashes between "the gateway took the money" and "the browser
told us so", the order is stuck in `pending_payment` forever even though the
gateway is holding a completed payment. These routes are the fix: the gateway
itself calls us directly, independent of the browser, whenever a payment
settles.

Because there is no browser session on a server-to-server call, these routes
carry no cookie/session auth and no CSRF token — the provider's signature IS
the auth. Do not add `get_current_customer`/`get_current_staff` here; either
would reject every legitimate delivery outright.

An unconfigured gateway (`razorpay_webhook_secret` / `paypal_webhook_id`
empty) answers with the same 404 an unmapped route would return. Anything
more specific — a 401, or a distinct "not configured" body — would let an
unauthenticated caller distinguish "no such gateway" from "gateway configured,
signature wrong", which is exactly the kind of detail worth not leaking on an
endpoint no browser ever calls.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request

from truegrit_api.auth.dependencies import get_database
from truegrit_api.config import Settings, get_settings
from truegrit_api.errors import AuthenticationError, ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.payments import verify_paypal_webhook_signature
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["webhooks"])

# Razorpay event types that mean "money has moved"; everything else is
# recorded (for idempotency and auditing) but requires no reconciliation.
_RAZORPAY_SETTLED_EVENTS = frozenset({"payment.captured", "payment.authorized"})
_PAYPAL_SETTLED_EVENTS = frozenset({"PAYMENT.CAPTURE.COMPLETED"})


def _not_configured() -> HTTPException:
    # A fresh instance per call: Starlette exceptions carry no per-request
    # state, but sharing one raised object across concurrent requests is a
    # false economy for a two-field object — construct plainly instead.
    return HTTPException(status_code=404)


def _razorpay_signature_valid(settings: Settings, raw_body: bytes, signature: str) -> bool:
    """HMAC-SHA256 over the raw webhook body, keyed by the webhook secret.

    This is a different signature from `services.payments.verify_razorpay_signature`:
    that one checks `"{order_id}|{payment_id}"` keyed by the *account key
    secret*, signed for the browser at the end of checkout. This one checks
    the *entire raw request body*, keyed by the *webhook secret*, signed for
    a server-to-server delivery. Conflating the two means every webhook fails
    signature verification.
    """
    expected = hmac.new(
        settings.razorpay_webhook_secret.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


def _parse_json_object(raw_body: bytes) -> dict[str, Any]:
    try:
        parsed = json.loads(raw_body)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise ValidationAppError("Malformed webhook payload.") from exc
    if not isinstance(parsed, dict):
        raise ValidationAppError("Malformed webhook payload.")
    return parsed


async def _record_webhook_event(
    db: Database, *, provider: str, provider_event_id: str, event_type: str, raw_body: bytes
) -> dict[str, Any]:
    """Durably record this delivery attempt before doing anything else, so a
    crash between recording and processing still leaves a retryable trace.

    The upsert makes a replay (the gateway retrying because our previous 200
    never reached it, or simply delivering twice) cheap to detect: a second
    delivery of the same `(provider, provider_event_id)` only bumps
    `attempt_count`, never inserts a second row. The caller decides whether to
    reprocess by reading `processing_status` back off the row this returns.
    """
    payload_hash = hashlib.sha256(raw_body).hexdigest()
    await db.execute(
        """
        INSERT INTO webhook_events
            (id, provider, provider_event_id, event_type, payload_hash,
             processing_status, attempt_count, received_at)
        VALUES (?, ?, ?, ?, ?, 'received', 1, ?)
        ON CONFLICT(provider, provider_event_id) DO UPDATE SET attempt_count = attempt_count + 1
        """,
        (new_id("whe"), provider, provider_event_id, event_type, payload_hash, utc_now_iso()),
    )
    row = await db.fetch_one(
        "SELECT processing_status, attempt_count FROM webhook_events"
        " WHERE provider = ? AND provider_event_id = ?",
        (provider, provider_event_id),
    )
    if row is None:
        # The INSERT/upsert above just completed against this same connection;
        # its absence now means the database layer itself is broken, not a
        # business condition this route can meaningfully recover from.
        raise RuntimeError("webhook_events row missing immediately after recording it.")
    return row


async def _mark_processed(db: Database, *, provider: str, provider_event_id: str) -> None:
    await db.execute(
        "UPDATE webhook_events SET processing_status = 'processed', processed_at = ?"
        " WHERE provider = ? AND provider_event_id = ?",
        (utc_now_iso(), provider, provider_event_id),
    )


def _razorpay_order_id(payload: dict[str, Any]) -> str | None:
    body = payload.get("payload")
    payment = body.get("payment") if isinstance(body, dict) else None
    entity = payment.get("entity") if isinstance(payment, dict) else None
    order_id = entity.get("order_id") if isinstance(entity, dict) else None
    return str(order_id) if order_id else None


async def _reconcile_razorpay_payment(db: Database, payload: dict[str, Any]) -> None:
    """Mark the matching order paid, mirroring `verify_razorpay_payment` in
    `api.storefront` exactly (same columns, same end state) so a customer
    whose confirm call landed and one whose confirm call never arrived
    converge on an identical order row. A payload with no matching local
    payment — an order that does not exist here, or a test-mode ping — is not
    an error: it is simply nothing to reconcile."""
    razorpay_order_id = _razorpay_order_id(payload)
    if razorpay_order_id is None:
        return

    row = await db.fetch_one(
        """
        SELECT o.id AS order_id, o.payment_status AS order_payment_status
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE p.provider_intent_id = ? AND p.provider = 'razorpay'
        """,
        (razorpay_order_id,),
    )
    if row is None or str(row["order_payment_status"]) == "paid":
        return

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE payments SET status = 'paid', provider_intent_id = ?, updated_at = ?"
                " WHERE order_id = ? AND provider = 'razorpay'",
                (razorpay_order_id, now, row["order_id"]),
            ),
            (
                "UPDATE orders SET payment_status = 'paid', order_status = 'confirmed',"
                " updated_at = ? WHERE id = ?",
                (now, row["order_id"]),
            ),
        ]
    )


def _paypal_capture_and_order_id(payload: dict[str, Any]) -> tuple[str, str] | None:
    resource = payload.get("resource")
    if not isinstance(resource, dict):
        return None
    capture_id = resource.get("id")
    if not capture_id:
        return None

    supplementary = resource.get("supplementary_data")
    related_ids = supplementary.get("related_ids") if isinstance(supplementary, dict) else None
    order_id = related_ids.get("order_id") if isinstance(related_ids, dict) else None
    if not order_id:
        # Some deliveries carry the order reference only on `custom_id` (the
        # value True Grit's own `create_paypal_order` sets it to at checkout).
        order_id = resource.get("custom_id")
    if not order_id:
        return None
    return str(capture_id), str(order_id)


async def _reconcile_paypal_payment(db: Database, payload: dict[str, Any]) -> None:
    """Mark the matching order paid, mirroring `capture_paypal_payment` in
    `api.storefront`: same `payments`/`orders` columns, same end state.

    Looks up the payment by `provider_intent_id` — the column
    `services.checkout`'s order-creation step actually populates with the
    PayPal order id — rather than by payment id, since that is the only
    identifier PayPal hands us before this webhook fires.
    """
    ids = _paypal_capture_and_order_id(payload)
    if ids is None:
        return
    capture_id, paypal_order_id = ids

    row = await db.fetch_one(
        """
        SELECT o.id AS order_id, o.payment_status AS order_payment_status
        FROM payments p
        JOIN orders o ON o.id = p.order_id
        WHERE p.provider_intent_id = ? AND p.provider = 'paypal'
        """,
        (paypal_order_id,),
    )
    if row is None or str(row["order_payment_status"]) == "paid":
        return

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE payments SET status = 'paid', provider_intent_id = ?, updated_at = ?"
                " WHERE order_id = ? AND provider = 'paypal'",
                (capture_id, now, row["order_id"]),
            ),
            (
                "UPDATE orders SET payment_status = 'paid', order_status = 'confirmed',"
                " updated_at = ? WHERE id = ?",
                (now, row["order_id"]),
            ),
        ]
    )


@router.post("/razorpay", include_in_schema=False)
async def razorpay_webhook(
    request: Request, db: Annotated[Database, Depends(get_database)]
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.razorpay_webhook_secret:
        raise _not_configured()

    raw_body = await request.body()
    signature = request.headers.get("x-razorpay-signature")
    if not signature or not _razorpay_signature_valid(settings, raw_body, signature):
        log_event("warning", "webhook_signature_rejected", provider="razorpay")
        raise AuthenticationError("Webhook signature verification failed.")

    payload = _parse_json_object(raw_body)
    provider_event_id = str(payload.get("id") or "")
    event_type = str(payload.get("event") or "")
    if not provider_event_id or not event_type:
        raise ValidationAppError("Malformed webhook payload.")

    event_row = await _record_webhook_event(
        db,
        provider="razorpay",
        provider_event_id=provider_event_id,
        event_type=event_type,
        raw_body=raw_body,
    )
    if event_row["processing_status"] == "processed":
        log_event("info", "webhook_replay_ignored", provider="razorpay", event_type=event_type)
        return {"ok": True}

    if event_type in _RAZORPAY_SETTLED_EVENTS:
        await _reconcile_razorpay_payment(db, payload)

    await _mark_processed(db, provider="razorpay", provider_event_id=provider_event_id)
    log_event("info", "webhook_processed", provider="razorpay", event_type=event_type)
    return {"ok": True}


@router.post("/paypal", include_in_schema=False)
async def paypal_webhook(
    request: Request, db: Annotated[Database, Depends(get_database)]
) -> dict[str, bool]:
    settings = get_settings()
    if not settings.paypal_webhook_id:
        raise _not_configured()

    raw_body = await request.body()
    payload = _parse_json_object(raw_body)

    verified = await verify_paypal_webhook_signature(
        settings,
        headers=dict(request.headers),
        raw_body=raw_body,
        webhook_event=payload,
    )
    if not verified:
        log_event("warning", "webhook_signature_rejected", provider="paypal")
        raise AuthenticationError("Webhook signature verification failed.")

    provider_event_id = str(payload.get("id") or "")
    event_type = str(payload.get("event_type") or "")
    if not provider_event_id or not event_type:
        raise ValidationAppError("Malformed webhook payload.")

    event_row = await _record_webhook_event(
        db,
        provider="paypal",
        provider_event_id=provider_event_id,
        event_type=event_type,
        raw_body=raw_body,
    )
    if event_row["processing_status"] == "processed":
        log_event("info", "webhook_replay_ignored", provider="paypal", event_type=event_type)
        return {"ok": True}

    if event_type in _PAYPAL_SETTLED_EVENTS:
        await _reconcile_paypal_payment(db, payload)

    await _mark_processed(db, provider="paypal", provider_event_id=provider_event_id)
    log_event("info", "webhook_processed", provider="paypal", event_type=event_type)
    return {"ok": True}

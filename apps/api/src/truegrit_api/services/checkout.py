"""Checkout: turn a client-side cart into a server-authoritative order.

The browser cart is only an estimate. At checkout the server re-validates every
line — the product must be published, the variant active, a current price must
exist, and enough stock must be free — then computes the totals itself, creates
the order and its line items, and reserves inventory. All writes happen in one
batch so an order can never exist without its reservations and audit record.

Payment is cash-on-delivery for now (no gateway): the order is confirmed with a
pending payment. Integrating a real payment provider (intent + webhook) is a
separate piece of work.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.domain.money import basis_points_discount
from truegrit_api.errors import ConflictError, PhoneRequiredError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.bundles import resolve_bundle_discount
from truegrit_api.services.feature_settings import (
    load_delivery_settings,
    load_storefront_settings,
    promotions_enabled,
)
from truegrit_api.services.promotions import resolve_checkout_discount
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_QUANTITY_PER_LINE = 12
_MAX_LINES = 40
_ADDRESS_REQUIRED = ("recipient_name", "line1", "city", "state", "postal_code")


@dataclass(frozen=True)
class CheckoutLine:
    variant_id: str
    quantity: int


def _reference() -> str:
    return "TG-" + "".join(secrets.choice("0123456789") for _ in range(8))


def _validate_address(address: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key in _ADDRESS_REQUIRED:
        value = str(address.get(key, "")).strip()
        if not value:
            raise ValidationAppError(f"Delivery address is missing {key.replace('_', ' ')}.")
        cleaned[key] = value
    for optional in ("line2", "phone_e164", "country_code"):
        value = str(address.get(optional, "")).strip()
        if value:
            cleaned[optional] = value
    cleaned.setdefault("country_code", "IN")
    return cleaned


async def _resolve_line(
    db: Database, line: CheckoutLine, now: str, *, payments_enabled: bool
) -> dict[str, Any]:
    if line.quantity < 1 or line.quantity > _MAX_QUANTITY_PER_LINE:
        raise ValidationAppError(f"Quantity for each item must be 1-{_MAX_QUANTITY_PER_LINE}.")
    variant = await db.fetch_one(
        """
        SELECT v.id AS variant_id, v.sku, v.name AS variant_name,
               p.id AS product_id, p.name AS product_name, p.status,
               p.accepts_orders, p.payments_override, p.farm_id
        FROM product_variants v
        JOIN products p ON p.id = v.product_id
        WHERE v.id = ? AND v.status = 'active'
        """,
        (line.variant_id,),
    )
    if variant is None or variant["status"] != "published":
        raise ConflictError("An item in your basket is no longer available.")
    # Per-product switch (migration 0048): a stock/quality kill-switch, always
    # narrowing regardless of the site-wide payments switch below. Re-checked
    # here rather than trusted from the browser cart for the same reason price
    # and stock are -- the cart is only ever an estimate.
    if not variant["accepts_orders"]:
        raise ConflictError(f"{variant['product_name']} is not currently available to order.")
    # Site-wide payments switch (migration 0040), overridable per product in
    # EITHER direction (migration 0069): 'inherit' follows `payments_enabled`,
    # 'force_enabled' takes an order even while payments are off site-wide,
    # 'force_disabled' blocks one product even while payments are on. This is
    # the one place that decides it -- `place_order` no longer trusts a
    # blanket pre-check, since that cannot express a per-product override.
    override = variant["payments_override"]
    payments_allowed = payments_enabled if override == "inherit" else override == "force_enabled"
    if not payments_allowed:
        raise ConflictError(
            f"{variant['product_name']} is not available for order right now"
            " — we are not taking payments for it at the moment."
        )

    price = await db.fetch_one(
        """
        SELECT list_amount_minor, sale_amount_minor, currency_code
        FROM variant_prices
        WHERE variant_id = ? AND status = 'active'
          AND (starts_at IS NULL OR starts_at <= ?)
          AND (ends_at IS NULL OR ends_at > ?)
        ORDER BY starts_at DESC
        LIMIT 1
        """,
        (line.variant_id, now, now),
    )
    if price is None:
        raise ConflictError(f"{variant['product_name']} is not currently priced for sale.")

    level = await db.fetch_one(
        """
        SELECT location_id, on_hand, reserved
        FROM inventory_levels
        WHERE variant_id = ? AND (on_hand - reserved) >= ?
        ORDER BY (on_hand - reserved) DESC
        LIMIT 1
        """,
        (line.variant_id, line.quantity),
    )
    if level is None:
        raise ConflictError(f"Not enough stock for {variant['product_name']}.")

    unit = price["sale_amount_minor"] or price["list_amount_minor"]
    return {
        "variant": variant,
        "location_id": level["location_id"],
        "unit_list_minor": price["list_amount_minor"],
        "unit_effective_minor": unit,
        "currency_code": price["currency_code"],
        "quantity": line.quantity,
        "line_total_minor": unit * line.quantity,
    }


def _order_result(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "reference": row["public_reference"],
        "currencyCode": row["currency_code"],
        "subtotalMinor": row["subtotal_minor"],
        "discountMinor": row["discount_minor"],
        "deliveryMinor": row["delivery_minor"],
        "totalMinor": row["total_minor"],
        "orderStatus": row["order_status"],
        "paymentStatus": row["payment_status"],
    }


async def _find_by_idempotency_key(
    db: Database, customer_user_id: str, idempotency_key: str
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id, public_reference, currency_code, subtotal_minor, discount_minor,
               delivery_minor, total_minor, order_status, payment_status
        FROM orders
        WHERE customer_user_id = ? AND idempotency_key = ?
        """,
        (customer_user_id, idempotency_key),
    )


async def _release_reservation(
    db: Database, variant_id: str, location_id: str, quantity: int
) -> None:
    """Best-effort compensation for a phase-1 reservation whose order never
    landed (a later line failed, or the order batch itself failed). Not
    itself conditional -- undoing a reservation we just proved we hold can
    never take `reserved` negative, so there is nothing to guard here."""
    await db.execute(
        "UPDATE inventory_levels SET reserved = reserved - ?, updated_at = ?"
        " WHERE variant_id = ? AND location_id = ?",
        (quantity, utc_now_iso(), variant_id, location_id),
    )


async def place_order(
    db: Database,
    customer: Principal,
    request_id: str,
    *,
    items: list[CheckoutLine],
    delivery_address: dict[str, Any],
    payment_method: str = "cod",
    idempotency_key: str | None = None,
    coupon_code: str | None = None,
    subscription_id: str | None = None,
    subscription_discount_percent: int | None = None,
) -> dict[str, Any]:
    # A retried submission (double-click, network timeout-and-resend, back
    # button) returns the order that request already placed instead of a
    # second one. Scoped to the customer so two different shoppers can never
    # collide on the same client-generated key.
    idempotency_key = (idempotency_key or "").strip() or None
    if idempotency_key is not None:
        existing = await _find_by_idempotency_key(db, customer.user_id, idempotency_key)
        if existing is not None:
            return _order_result(existing)

    if not items:
        raise ValidationAppError("Your basket is empty.")
    if len(items) > _MAX_LINES:
        raise ValidationAppError("Too many items in one order.")
    # Collapse duplicate variant lines defensively.
    merged: dict[str, int] = {}
    for line in items:
        merged[line.variant_id] = merged.get(line.variant_id, 0) + line.quantity
    lines = [CheckoutLine(variant_id=v, quantity=q) for v, q in merged.items()]

    address = _validate_address(delivery_address)
    settings = get_settings()

    # A reachable mobile is the one contact detail this order genuinely depends
    # on: the courier calls it, and cash-on-delivery has nothing else to fall
    # back on. Accounts that predate phone verification are prompted (and may
    # skip) in the storefront, so checkout is where the ask finally lands.
    if settings.phone_required_at_checkout and not customer.has_verified_phone:
        raise PhoneRequiredError(
            "Please verify your mobile number before checking out — "
            "we need it for delivery updates."
        )

    now = utc_now_iso()
    # Resolved once per order, not once per line: every line in the same
    # checkout sees the same site-wide switch state, and `_resolve_line`
    # layers each product's own override (migration 0069) on top of it.
    payments_enabled = (await load_storefront_settings(db)).payments
    resolved = [
        await _resolve_line(db, line, now, payments_enabled=payments_enabled) for line in lines
    ]

    currency = resolved[0]["currency_code"]
    subtotal = sum(item["line_total_minor"] for item in resolved)
    delivery_settings = await load_delivery_settings(db)
    delivery = (
        0 if subtotal >= delivery_settings.free_threshold_minor else delivery_settings.fee_minor
    )

    # A coupon code is only ever honoured while the sitewide switch is on; an
    # automatic (no-code) promotion is resolved the same gated way, so this
    # is the one place that decides whether checkout is even allowed to look
    # -- `resolve_checkout_discount` alone decides what, if anything, applies.
    clean_coupon_code = (coupon_code or "").strip() or None
    enabled = await promotions_enabled(db)
    if clean_coupon_code and not enabled:
        raise ValidationAppError("Coupons are not available right now.")
    applied_promotion = (
        await resolve_checkout_discount(
            db,
            subtotal_minor=subtotal,
            delivery_minor=delivery,
            coupon_code=clean_coupon_code,
            customer_user_id=customer.user_id,
        )
        if enabled
        else None
    )
    # `discount` is strictly the reduction to `subtotal` -- it must stay 0 for
    # a free-delivery promotion, whose benefit is already fully expressed by
    # zeroing `delivery` below. Folding the waived fee into `discount` too
    # would double-count it (`total = subtotal + 0 - fee` instead of
    # `subtotal`) and break `total == subtotal - discount + delivery`, an
    # invariant order history and revenue reporting both rely on holding.
    # `granted_value` is the separate, honest record of what the promotion
    # was actually worth, whichever mechanism delivered it -- that is what
    # gets written to `order_adjustments` and the order's promotion snapshot.
    discount = 0
    granted_value = 0
    if applied_promotion is not None:
        granted_value = applied_promotion["discount_minor"]
        if applied_promotion["free_delivery"]:
            delivery = 0
        else:
            discount = granted_value

    # A bundle discount is independent of, and stacks additively with, any
    # coupon/promotion discount above -- see the module docstring in
    # `services.bundles`. Priced against `unit_effective_minor` (already
    # resolved per line, sale price included), so bundle savings are always
    # measured against what the customer is actually being charged.
    applied_bundle = await resolve_bundle_discount(db, resolved)
    bundle_discount = applied_bundle["discount_minor"] if applied_bundle is not None else 0

    # A subscription renewal's own incentive -- independent of, and stacking
    # with, both discounts above, the same reasoning bundle_discount's own
    # comment documents. `subscription_discount_percent` only ever arrives
    # non-None from `services.subscriptions`, never from the ordinary
    # cart-checkout route, so an ordinary order is never affected by it.
    subscription_discount = (
        basis_points_discount(subtotal, subscription_discount_percent * 100)
        if subscription_discount_percent
        else 0
    )

    total_discount = discount + bundle_discount + subscription_discount
    total = max(subtotal + delivery - total_discount, 0)

    if payment_method == "cod":
        if total > settings.payment_cod_max_minor:
            raise ValidationAppError(
                "Cash on delivery is only available for orders up to "
                f"{settings.payment_cod_max_minor // 100} {currency}. "
                "Please pay online for this order."
            )
        # One outstanding COD order per customer: an unpaid COD order must be
        # settled (paid on delivery) before another can be placed.
        outstanding = await db.fetch_one(
            """
            SELECT COUNT(*) AS open_cod
            FROM payments p
            JOIN orders o ON o.id = p.order_id
            WHERE o.customer_user_id = ? AND p.provider = 'cod' AND p.status = 'pending'
            """,
            (customer.user_id,),
        )
        if outstanding and int(outstanding["open_cod"]) > 0:
            raise ConflictError(
                "You already have a cash-on-delivery order in progress. "
                "Please pay for this order online, or wait until the previous one is delivered."
            )

    # Phase 1: reserve every line's stock with a conditional write, checked
    # and changed in the same statement (`WHERE (on_hand - reserved) >= ?`)
    # rather than trusting the read a few lines above -- that read is only
    # ever a friendly early error message now; this is the actual guard. Two
    # requests racing for the same last unit can no longer both succeed: only
    # one UPDATE matches a row, the other affects zero and is rejected before
    # any order exists. A line that fails here unwinds every reservation this
    # order already made, so a partial checkout never holds stock nobody's
    # order references.
    reserved_so_far: list[dict[str, Any]] = []
    try:
        for item in resolved:
            variant = item["variant"]
            changed = await db.execute(
                "UPDATE inventory_levels SET reserved = reserved + ?, updated_at = ?"
                " WHERE variant_id = ? AND location_id = ? AND (on_hand - reserved) >= ?",
                (
                    item["quantity"],
                    now,
                    variant["variant_id"],
                    item["location_id"],
                    item["quantity"],
                ),
            )
            if changed == 0:
                raise ConflictError(f"Not enough stock for {variant['product_name']}.")
            reserved_so_far.append(item)
    except Exception:
        for item in reserved_so_far:
            variant = item["variant"]
            await _release_reservation(
                db, variant["variant_id"], item["location_id"], item["quantity"]
            )
        raise

    order_id = new_id("ord")
    reference = _reference()
    # Cash-on-delivery orders are confirmed immediately (paid on delivery). Online
    # payments open as pending_payment and are confirmed once the gateway result
    # is verified, so unpaid orders never enter fulfilment.
    order_status = "confirmed" if payment_method == "cod" else "pending_payment"
    # Frozen at order time, the same reasoning `order_items.product_snapshot_json`
    # already uses for catalogue data: a promotion edited or archived after this
    # order shipped must never retroactively change what this order's history says.
    promotion_snapshot = (
        json.dumps(
            {
                "promotionId": applied_promotion["promotion_id"],
                "couponId": applied_promotion["coupon_id"],
                "code": applied_promotion["code"],
                "headline": applied_promotion["headline"],
                "discountMinor": granted_value,
                "freeDelivery": applied_promotion["free_delivery"],
            }
        )
        if applied_promotion is not None
        else None
    )
    statements: list[tuple[str, Any]] = [
        (
            """
            INSERT INTO orders (
              id, public_reference, customer_user_id, customer_email, customer_phone_e164,
              currency_code,
              subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,
              order_status, payment_status, fulfilment_status, delivery_status,
              delivery_address_json, promotion_snapshot_json,
              idempotency_key, subscription_id, placed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?,
                      ?, 'pending', 'unfulfilled', 'not_ready', ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id,
                reference,
                customer.user_id,
                # customer_email is NOT NULL, so a phone-only account stores its
                # `@phone.invalid` placeholder here exactly as `users` does. Every
                # reader goes through `services.contact`, and the phone below is
                # what fulfilment actually contacts them on.
                customer.email,
                customer.phone_e164 or address.get("phone_e164"),
                currency,
                subtotal,
                total_discount,
                delivery,
                total,
                order_status,
                json.dumps(address),
                promotion_snapshot,
                idempotency_key,
                subscription_id,
                now,
                now,
                now,
            ),
        )
    ]

    for item in resolved:
        variant = item["variant"]
        statements.append(
            (
                """
                INSERT INTO order_items (
                  id, order_id, product_id, variant_id, product_name, variant_name, sku,
                  quantity, unit_list_amount_minor, unit_effective_amount_minor,
                  discount_minor, tax_minor, line_total_minor, farm_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)
                """,
                (
                    new_id("oit"),
                    order_id,
                    variant["product_id"],
                    variant["variant_id"],
                    variant["product_name"],
                    variant["variant_name"],
                    variant["sku"],
                    item["quantity"],
                    item["unit_list_minor"],
                    item["unit_effective_minor"],
                    item["line_total_minor"],
                    variant["farm_id"],
                ),
            )
        )
        statements.append(
            (
                "INSERT INTO inventory_reservations"
                " (id, variant_id, location_id, quantity, reference_type, reference_id,"
                "  status, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, 'order', ?, 'held', ?, ?)",
                (
                    new_id("rsv"),
                    variant["variant_id"],
                    item["location_id"],
                    item["quantity"],
                    order_id,
                    now,
                    now,
                ),
            )
        )

    if applied_promotion is not None:
        # One ledger row for the discount actually granted -- 'coupon' when a
        # code drove it, 'promotion' for the automatic case -- and, only when
        # a coupon was used, the redemption row its own usage-limit checks
        # depend on. Both land in this same batch as the order: a discount
        # can never be computed without being recorded, or recorded without
        # an order behind it.
        statements.append(
            (
                "INSERT INTO order_adjustments"
                " (id, order_id, adjustment_type, label, amount_minor, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("adj"),
                    order_id,
                    "coupon" if applied_promotion["coupon_id"] else "promotion",
                    applied_promotion["headline"],
                    -granted_value,
                    now,
                ),
            )
        )
        if applied_promotion["coupon_id"] is not None:
            statements.append(
                (
                    "INSERT INTO coupon_redemptions"
                    " (id, coupon_id, order_id, customer_user_id, redeemed_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (
                        new_id("crdm"),
                        applied_promotion["coupon_id"],
                        order_id,
                        customer.user_id,
                        now,
                    ),
                )
            )

    if applied_bundle is not None:
        # Reuses the 'promotion' adjustment type -- see the WHY note in
        # migration 0062 for why this doesn't get its own enum value.
        statements.append(
            (
                "INSERT INTO order_adjustments"
                " (id, order_id, adjustment_type, label, amount_minor, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("adj"),
                    order_id,
                    "promotion",
                    f"Bundle savings — {applied_bundle['name']}",
                    -bundle_discount,
                    now,
                ),
            )
        )

    if subscription_discount > 0:
        # Same 'promotion' reuse, same reasoning -- see the WHY note in
        # migration 0064.
        statements.append(
            (
                "INSERT INTO order_adjustments"
                " (id, order_id, adjustment_type, label, amount_minor, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("adj"),
                    order_id,
                    "promotion",
                    f"Subscribe & Save — {subscription_discount_percent}% off",
                    -subscription_discount,
                    now,
                ),
            )
        )

    statements.append(
        audit_statement(
            action="order.placed",
            entity_type="order",
            entity_id=order_id,
            actor_id=customer.user_id,
            request_id=request_id,
            created_at=now,
            after={
                "reference": reference,
                "total_minor": total,
                "lines": len(resolved),
                "discount_minor": total_discount,
                "granted_value_minor": granted_value,
                "bundle_discount_minor": bundle_discount,
                "bundle_id": applied_bundle["bundle_id"] if applied_bundle else None,
                "coupon_code": applied_promotion["code"] if applied_promotion else None,
                "subscription_id": subscription_id,
                "subscription_discount_minor": subscription_discount,
            },
        )
    )

    try:
        await db.batch(statements)
    except Exception:
        # The order never landed, so the stock this attempt reserved for it
        # must go back -- otherwise it is held forever against nothing.
        for item in resolved:
            variant = item["variant"]
            await _release_reservation(
                db, variant["variant_id"], item["location_id"], item["quantity"]
            )
        # A concurrent request with the same idempotency key may have won the
        # race and already created the real order between our check above and
        # this write -- that shows up here as an INSERT failing on the unique
        # (customer, key) index. Treat that as the success it actually is
        # rather than surfacing a raw database error to the customer.
        if idempotency_key is not None:
            existing = await _find_by_idempotency_key(db, customer.user_id, idempotency_key)
            if existing is not None:
                return _order_result(existing)
        raise

    return {
        "id": order_id,
        "reference": reference,
        "currencyCode": currency,
        "subtotalMinor": subtotal,
        "discountMinor": total_discount,
        "deliveryMinor": delivery,
        "totalMinor": total,
        "orderStatus": order_status,
        "paymentStatus": "pending",
        "couponCode": applied_promotion["code"] if applied_promotion else None,
    }

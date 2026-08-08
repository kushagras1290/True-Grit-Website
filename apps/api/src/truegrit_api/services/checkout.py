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
from truegrit_api.services.b2b import (
    check_credit_limit,
    is_b2b_customer,
    resolve_b2b_price,
)
from truegrit_api.services.bundles import resolve_bundle_discount
from truegrit_api.services.delivery_zones import (
    find_zone_for_postal_code,
    list_slots,
    validate_slot_selection,
)
from truegrit_api.services.feature_settings import (
    load_delivery_settings,
    load_loyalty_settings,
    load_storefront_settings,
    promotions_enabled,
)
from truegrit_api.services.gift_cards import resolve_checkout_redemption
from truegrit_api.services.loyalty import resolve_checkout_redemption as resolve_loyalty_redemption
from truegrit_api.services.preorders import get_active_harvest_window_for_product
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
    preorder: bool = False


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
    db: Database,
    line: CheckoutLine,
    now: str,
    *,
    payments_enabled: bool,
    preorders_enabled: bool,
    b2b_pricing_enabled: bool,
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

    harvest_window = None
    if line.preorder:
        if not preorders_enabled:
            raise ValidationAppError("Seasonal pre-orders are not available right now.")
        harvest_window = await get_active_harvest_window_for_product(
            db, variant["product_id"], quantity=line.quantity
        )
        if harvest_window is None:
            raise ConflictError(f"{variant['product_name']} is not open for pre-order.")

    level = (
        None
        if line.preorder
        else await db.fetch_one(
            """
        SELECT location_id, on_hand, reserved
        FROM inventory_levels
        WHERE variant_id = ? AND (on_hand - reserved) >= ?
        ORDER BY (on_hand - reserved) DESC
        LIMIT 1
        """,
            (line.variant_id, line.quantity),
        )
    )
    if level is None and not line.preorder:
        raise ConflictError(f"Not enough stock for {variant['product_name']}.")

    unit = (
        price["sale_amount_minor"]
        if price["sale_amount_minor"] is not None
        else price["list_amount_minor"]
    )
    if b2b_pricing_enabled:
        tier_price = await resolve_b2b_price(db, line.variant_id, line.quantity)
        if tier_price is not None:
            unit = min(unit, tier_price)
    return {
        "variant": variant,
        "location_id": level["location_id"] if level is not None else None,
        "harvest_window_id": harvest_window["id"] if harvest_window is not None else None,
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
        "giftCardCode": row["gift_card_code"],
        "giftCardAppliedMinor": row["gift_card_applied_minor"],
        "loyaltyPointsRedeemed": row.get("loyalty_points_redeemed", 0),
        "loyaltyAppliedMinor": row.get("loyalty_applied_minor", 0),
        "deliveryMethod": row.get("delivery_method", "delivery"),
        "pickupPointId": row.get("pickup_point_id"),
        "deliveryZoneId": row.get("delivery_zone_id"),
        "deliverySlotId": row.get("delivery_slot_id"),
        "deliveryDate": row.get("delivery_date"),
        "orderType": row.get("order_type", "standard"),
    }


async def _find_by_idempotency_key(
    db: Database, customer_user_id: str, idempotency_key: str
) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id, public_reference, currency_code, subtotal_minor, discount_minor,
               delivery_minor, total_minor, order_status, payment_status,
               gift_card_code, gift_card_applied_minor,
               loyalty_points_redeemed, loyalty_applied_minor,
               delivery_method, pickup_point_id, delivery_zone_id,
               delivery_slot_id, delivery_date, order_type
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
    gift_card_code: str | None = None,
    loyalty_points: int = 0,
    delivery_method: str = "delivery",
    pickup_point_id: str | None = None,
    delivery_slot_id: str | None = None,
    delivery_date: str | None = None,
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
    merged: dict[tuple[str, bool], int] = {}
    for line in items:
        key = (line.variant_id, line.preorder)
        merged[key] = merged.get(key, 0) + line.quantity
    lines = [
        CheckoutLine(variant_id=variant_id, quantity=quantity, preorder=is_preorder)
        for (variant_id, is_preorder), quantity in merged.items()
    ]

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
    feature_settings = await load_storefront_settings(db)
    payments_enabled = feature_settings.payments
    b2b_account = await is_b2b_customer(db, customer.user_id) if feature_settings.b2b else None
    resolved = [
        await _resolve_line(
            db,
            line,
            now,
            payments_enabled=payments_enabled,
            preorders_enabled=feature_settings.preorders,
            b2b_pricing_enabled=b2b_account is not None,
        )
        for line in lines
    ]

    currency = resolved[0]["currency_code"]
    subtotal = sum(item["line_total_minor"] for item in resolved)
    delivery_settings = await load_delivery_settings(db)
    clean_delivery_method = delivery_method.strip().lower()
    if clean_delivery_method not in {"delivery", "pickup"}:
        raise ValidationAppError("Delivery method must be delivery or pickup.")
    selected_pickup_point: dict[str, Any] | None = None
    selected_zone: dict[str, Any] | None = None
    selected_slot: dict[str, Any] | None = None
    if clean_delivery_method == "pickup":
        if not feature_settings.pickup:
            raise ValidationAppError("Local pickup is not available right now.")
        selected_pickup_point = await db.fetch_one(
            "SELECT * FROM pickup_points WHERE id = ? AND status = 'active'",
            ((pickup_point_id or "").strip(),),
        )
        if selected_pickup_point is None:
            raise ValidationAppError("Please choose an available pickup point.")
        delivery = 0
    else:
        fee_minor = delivery_settings.fee_minor
        threshold_minor = delivery_settings.free_threshold_minor
        if feature_settings.delivery_zones:
            selected_zone = await find_zone_for_postal_code(db, address["postal_code"])
            if selected_zone is None:
                raise ValidationAppError("Sorry, we don't deliver to this area yet.")
            fee_minor = (
                selected_zone["feeOverrideMinor"]
                if selected_zone["feeOverrideMinor"] is not None
                else fee_minor
            )
            threshold_minor = (
                selected_zone["freeThresholdOverrideMinor"]
                if selected_zone["freeThresholdOverrideMinor"] is not None
                else threshold_minor
            )
            configured_slots = await list_slots(db, selected_zone["id"])
            active_slots = [slot for slot in configured_slots if slot["status"] == "active"]
            if active_slots:
                if not delivery_slot_id or not delivery_date:
                    raise ValidationAppError("Please choose a delivery date and time slot.")
                selected_slot = await validate_slot_selection(
                    db,
                    zone_id=selected_zone["id"],
                    slot_id=delivery_slot_id,
                    delivery_date=delivery_date,
                )
        delivery = 0 if subtotal >= threshold_minor else fee_minor

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
    pre_gift_card_total = max(subtotal + delivery - total_discount, 0)

    # A gift card is applied last, against whatever is left after every
    # other discount -- it consumes real stored value, not a marketing
    # discount, so it always spends against the smallest amount possible
    # rather than being computed off the pre-discount subtotal.
    clean_gift_card_code = (gift_card_code or "").strip() or None
    gift_cards_are_enabled = feature_settings.gift_cards
    if clean_gift_card_code and not gift_cards_are_enabled:
        raise ValidationAppError("Gift cards are not available right now.")
    applied_gift_card = (
        await resolve_checkout_redemption(
            db, code=clean_gift_card_code, amount_needed_minor=pre_gift_card_total
        )
        if gift_cards_are_enabled
        else None
    )
    gift_card_applied = applied_gift_card["applied_minor"] if applied_gift_card is not None else 0
    pre_loyalty_total = pre_gift_card_total - gift_card_applied

    requested_loyalty_points = max(int(loyalty_points), 0)
    if requested_loyalty_points and not feature_settings.loyalty:
        raise ValidationAppError("Loyalty rewards are not available right now.")
    loyalty_settings = await load_loyalty_settings(db)
    applied_loyalty = (
        await resolve_loyalty_redemption(
            db,
            customer_user_id=customer.user_id,
            points_to_redeem=requested_loyalty_points,
            points_value_minor=loyalty_settings.point_value_minor,
            amount_needed_minor=pre_loyalty_total,
        )
        if feature_settings.loyalty
        else None
    )
    loyalty_applied = applied_loyalty["applied_minor"] if applied_loyalty else 0
    loyalty_points_redeemed = applied_loyalty["points_redeemed"] if applied_loyalty else 0
    loyalty_account = None
    if applied_loyalty is not None:
        loyalty_account = await db.fetch_one(
            "SELECT id FROM loyalty_accounts WHERE customer_user_id = ?",
            (customer.user_id,),
        )
        if loyalty_account is None:
            raise ValidationAppError("Your loyalty account is not available.")
    total = pre_loyalty_total - loyalty_applied

    if payment_method == "invoice":
        if not feature_settings.b2b or b2b_account is None:
            raise ValidationAppError(
                "Invoice payment is only available to active business accounts."
            )
        if not await check_credit_limit(db, b2b_account["id"], total):
            raise ValidationAppError("This order would exceed the business account credit limit.")

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
            if item["harvest_window_id"] is not None:
                continue
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
    order_status = "confirmed" if payment_method in {"cod", "invoice"} else "pending_payment"
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
              gift_card_applied_minor, gift_card_code,
              loyalty_points_redeemed, loyalty_applied_minor,
              order_status, payment_status, fulfilment_status, delivery_status,
              delivery_address_json, promotion_snapshot_json,
              idempotency_key, subscription_id,
              delivery_method, pickup_point_id, order_type,
              delivery_zone_id, delivery_slot_id, delivery_date,
              placed_at, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?,
                      ?, 'pending', 'unfulfilled', 'not_ready', ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                gift_card_applied,
                applied_gift_card["code"] if applied_gift_card is not None else None,
                loyalty_points_redeemed,
                loyalty_applied,
                order_status,
                json.dumps(address),
                promotion_snapshot,
                idempotency_key,
                subscription_id,
                clean_delivery_method,
                selected_pickup_point["id"] if selected_pickup_point else None,
                "preorder"
                if any(item["harvest_window_id"] is not None for item in resolved)
                else "standard",
                selected_zone["id"] if selected_zone else None,
                selected_slot["id"] if selected_slot else None,
                delivery_date if selected_slot else None,
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
        if item["harvest_window_id"] is None:
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
        else:
            statements.append(
                (
                    "INSERT INTO preorders"
                    " (id, order_id, harvest_window_id, product_id, variant_id,"
                    "  quantity, status, created_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, 'reserved', ?)",
                    (
                        new_id("po"),
                        order_id,
                        item["harvest_window_id"],
                        variant["product_id"],
                        variant["variant_id"],
                        item["quantity"],
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

    if applied_gift_card is not None:
        # Lands in the same batch as the order -- a gift card balance can
        # never be spent without an order behind it, the same invariant
        # coupon_redemptions holds for coupons.
        statements.append(
            (
                "INSERT INTO gift_card_redemptions"
                " (id, gift_card_id, order_id, customer_user_id, amount_minor, redeemed_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("gcrd"),
                    applied_gift_card["gift_card_id"],
                    order_id,
                    customer.user_id,
                    gift_card_applied,
                    now,
                ),
            )
        )

    if applied_loyalty is not None:
        assert loyalty_account is not None
        statements.append(
            (
                "INSERT INTO loyalty_transactions"
                " (id, loyalty_account_id, points, transaction_type, reference_id,"
                "  description, created_at)"
                " VALUES (?, ?, ?, 'redeem_checkout', ?, ?, ?)",
                (
                    new_id("ltx"),
                    loyalty_account["id"],
                    -loyalty_points_redeemed,
                    order_id,
                    "Points redeemed at checkout",
                    now,
                ),
            )
        )

    if selected_slot is not None and delivery_date is not None:
        statements.append(
            (
                "INSERT INTO delivery_slot_bookings"
                " (id, order_id, slot_id, delivery_date, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (new_id("dsb"), order_id, selected_slot["id"], delivery_date, now),
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
                "gift_card_code": applied_gift_card["code"] if applied_gift_card else None,
                "gift_card_applied_minor": gift_card_applied,
                "loyalty_points_redeemed": loyalty_points_redeemed,
                "loyalty_applied_minor": loyalty_applied,
                "delivery_method": clean_delivery_method,
                "pickup_point_id": selected_pickup_point["id"] if selected_pickup_point else None,
                "delivery_zone_id": selected_zone["id"] if selected_zone else None,
                "delivery_slot_id": selected_slot["id"] if selected_slot else None,
            },
        )
    )

    try:
        await db.batch(statements)
    except Exception:
        # The order never landed, so the stock this attempt reserved for it
        # must go back -- otherwise it is held forever against nothing.
        for item in resolved:
            if item["harvest_window_id"] is not None:
                continue
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
        "giftCardCode": applied_gift_card["code"] if applied_gift_card else None,
        "giftCardAppliedMinor": gift_card_applied,
        "loyaltyPointsRedeemed": loyalty_points_redeemed,
        "loyaltyAppliedMinor": loyalty_applied,
        "deliveryMethod": clean_delivery_method,
        "pickupPointId": selected_pickup_point["id"] if selected_pickup_point else None,
        "deliveryZoneId": selected_zone["id"] if selected_zone else None,
        "deliverySlotId": selected_slot["id"] if selected_slot else None,
        "deliveryDate": delivery_date if selected_slot else None,
        "orderType": "preorder"
        if any(item["harvest_window_id"] is not None for item in resolved)
        else "standard",
        "b2bAccountId": b2b_account["id"] if b2b_account else None,
        "b2bPaymentTermsDays": b2b_account["paymentTermsDays"] if b2b_account else None,
    }

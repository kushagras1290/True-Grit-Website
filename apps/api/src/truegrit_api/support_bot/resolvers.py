"""Stage 2: turn a classified intent into facts from D1.

Every resolver returns structured data -- never prose. The sentence a customer
reads is assembled in `templates.py` from these fields, which is the property
that makes the bot incapable of stating something no row contained.

Three rules hold across all of them:

* **Customer-scoped queries carry `customer_user_id` in the WHERE clause**, not
  in a filter applied afterwards. A signed-in customer asking about
  `TG-99999999` gets `Status.EMPTY` whether that order belongs to someone else
  or does not exist -- the two are indistinguishable from outside, which is the
  only safe answer.
* **A resolver that finds nothing says so.** `Status.EMPTY` selects a different
  template; it never falls through to a generic reply that implies data was
  found.
* **A resolver that was not given enough to work with returns
  `Status.NEEDS_INPUT`**, which asks the customer one specific question. This
  is the honest answer to "is it in stock?" with no product named, and it beats
  searching the catalogue for whatever noise words survived.

Only reads. There is no resolver that writes, cancels, refunds or changes an
address -- those intents are classified `ESCALATE` in `intents.py` precisely so
that no code path exists for the bot to act on an account.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import geo_release_clause

# How many rows a list-shaped answer shows before it stops being readable in a
# chat bubble and starts being a page the customer should visit instead.
_LIST_LIMIT = 5
_ORDER_HISTORY_LIMIT = 5

_CURRENCY_SYMBOLS = {"INR": "₹", "USD": "$", "EUR": "€", "GBP": "£"}

# Storefront wording for the raw column values (see the CHECK constraints in
# migrations 0005 and 0027). An unmapped value degrades to the underscored
# name rather than being hidden, so a status added later is visibly wrong in
# testing instead of silently missing in production.
_ORDER_STATUS = {
    "pending_payment": "awaiting payment",
    "confirmed": "confirmed",
    "processing": "being prepared",
    "completed": "completed",
    "cancelled": "cancelled",
}
_DELIVERY_STATUS = {
    "not_ready": "not dispatched yet",
    "awaiting_carrier": "waiting for the courier to collect it",
    "in_transit": "in transit",
    "out_for_delivery": "out for delivery",
    "delivered": "delivered",
    "delivery_failed": "a delivery attempt failed",
    "returned": "returned to us",
}
_RETURN_STATUS = {
    "requested": "requested, waiting to be reviewed",
    "under_review": "being reviewed",
    "approved": "approved",
    "rejected": "not approved",
    "refunded": "refunded",
    "replaced": "replaced",
    "completed": "completed",
    "cancelled": "cancelled",
}
_PAYMENT_STATUS = {
    "not_required": "no payment needed",
    "pending": "payment pending",
    "authorized": "payment authorised",
    "paid": "paid",
    "partially_refunded": "partially refunded",
    "refunded": "refunded",
    "failed": "payment failed",
}
_SUBSCRIPTION_FREQUENCY = {
    "weekly": "every week",
    "biweekly": "every two weeks",
    "monthly": "every month",
}


def _label(mapping: dict[str, str], value: Any) -> str:
    text = str(value or "")
    return mapping.get(text, text.replace("_", " ")) or "unknown"


def format_money(amount_minor: Any, currency: Any) -> str:
    """Minor units to a display string. Falls back to the ISO code when the
    currency has no symbol here rather than guessing one."""
    try:
        amount = int(amount_minor)
    except (TypeError, ValueError):
        return ""
    code = str(currency or "").upper()
    symbol = _CURRENCY_SYMBOLS.get(code)
    body = f"{amount / 100:,.2f}"
    return f"{symbol}{body}" if symbol else f"{code} {body}".strip()


class Status(StrEnum):
    OK = "ok"
    EMPTY = "empty"
    NEEDS_INPUT = "needs_input"


@dataclass(frozen=True)
class ResolveContext:
    db: Database
    customer: Principal | None
    slots: dict[str, Any]
    country: str | None = None
    locale: str | None = None

    def slot(self, name: str) -> Any:
        return self.slots.get(name)


@dataclass(frozen=True)
class Resolution:
    status: Status
    # Template variables. Keys must match the placeholders in `templates.py`;
    # a mismatch is caught by the template contract test, not at runtime.
    data: dict[str, Any] = field(default_factory=dict)
    # Anything worth attaching to an escalation record if this turn ends up
    # with a human after all -- the resolved order, the return row.
    context: dict[str, Any] = field(default_factory=dict)


Resolver = Callable[[ResolveContext], Awaitable[Resolution]]


# --- Orders -----------------------------------------------------------------


async def _load_order(ctx: ResolveContext) -> dict[str, Any] | None:
    """The order the customer means: the one they named, else their latest.

    `customer_user_id` is part of every branch. There is no code path here that
    reads an order without it.
    """
    assert ctx.customer is not None  # guaranteed by IntentSpec.requires_auth
    reference = ctx.slot("order_reference")
    if reference:
        return await ctx.db.fetch_one(
            """
            SELECT public_reference, order_status, payment_status, fulfilment_status,
                   delivery_status, delivery_method, total_minor, currency_code,
                   delivery_date, COALESCE(placed_at, created_at) AS placed_at
            FROM orders
            WHERE public_reference = ? COLLATE NOCASE AND customer_user_id = ?
            """,
            (reference, ctx.customer.user_id),
        )
    return await ctx.db.fetch_one(
        """
        SELECT public_reference, order_status, payment_status, fulfilment_status,
               delivery_status, delivery_method, total_minor, currency_code,
               delivery_date, COALESCE(placed_at, created_at) AS placed_at
        FROM orders
        WHERE customer_user_id = ?
        ORDER BY COALESCE(placed_at, created_at) DESC
        LIMIT 1
        """,
        (ctx.customer.user_id,),
    )


async def resolve_order_status(ctx: ResolveContext) -> Resolution:
    order = await _load_order(ctx)
    if order is None:
        return Resolution(
            status=Status.EMPTY, data={"reference": ctx.slot("order_reference") or ""}
        )

    reference = order["public_reference"]
    shipment = await ctx.db.fetch_one(
        """
        SELECT s.carrier, s.tracking_reference, s.status
        FROM shipments s
        JOIN orders o ON o.id = s.order_id
        WHERE o.public_reference = ?
        ORDER BY s.created_at DESC
        LIMIT 1
        """,
        (reference,),
    )
    tracking = ""
    if shipment is not None and shipment["tracking_reference"]:
        carrier = shipment["carrier"] or "the courier"
        tracking = f" Tracking with {carrier}: {shipment['tracking_reference']}."

    data = {
        "reference": reference,
        "order_status": _label(_ORDER_STATUS, order["order_status"]),
        "delivery_status": _label(_DELIVERY_STATUS, order["delivery_status"]),
        "payment_status": _label(_PAYMENT_STATUS, order["payment_status"]),
        "total": format_money(order["total_minor"], order["currency_code"]),
        "placed_at": str(order["placed_at"] or "")[:10],
        "delivery_date": str(order["delivery_date"] or "")[:10],
        "tracking": tracking,
        "path": f"/account/orders/{reference}",
    }
    return Resolution(status=Status.OK, data=data, context={"order": data})


async def resolve_order_list(ctx: ResolveContext) -> Resolution:
    assert ctx.customer is not None
    rows = await ctx.db.fetch_all(
        """
        SELECT public_reference, order_status, total_minor, currency_code,
               COALESCE(placed_at, created_at) AS placed_at
        FROM orders
        WHERE customer_user_id = ?
        ORDER BY COALESCE(placed_at, created_at) DESC
        LIMIT ?
        """,
        (ctx.customer.user_id, _ORDER_HISTORY_LIMIT),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    lines = "\n".join(
        f"- {row['public_reference']} ({str(row['placed_at'] or '')[:10]}) -"
        f" {_label(_ORDER_STATUS, row['order_status'])},"
        f" {format_money(row['total_minor'], row['currency_code'])}"
        for row in rows
    )
    return Resolution(status=Status.OK, data={"orders": lines, "count": len(rows)})


async def resolve_order_items(ctx: ResolveContext) -> Resolution:
    order = await _load_order(ctx)
    if order is None:
        return Resolution(status=Status.EMPTY)
    reference = order["public_reference"]
    rows = await ctx.db.fetch_all(
        """
        SELECT oi.product_name, oi.variant_name, oi.quantity,
               oi.line_total_minor, o.currency_code
        FROM order_items oi
        JOIN orders o ON o.id = oi.order_id
        WHERE o.public_reference = ? AND o.customer_user_id = ?
        ORDER BY oi.product_name
        """,
        (reference, ctx.customer.user_id if ctx.customer else ""),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    lines = "\n".join(
        f"- {row['product_name']}"
        f"{' (' + row['variant_name'] + ')' if row['variant_name'] else ''}"
        f" x{row['quantity']} - {format_money(row['line_total_minor'], row['currency_code'])}"
        for row in rows
    )
    return Resolution(
        status=Status.OK,
        data={"reference": reference, "items": lines, "path": f"/account/orders/{reference}"},
    )


async def resolve_order_invoice(ctx: ResolveContext) -> Resolution:
    order = await _load_order(ctx)
    if order is None:
        return Resolution(status=Status.EMPTY)
    reference = order["public_reference"]
    return Resolution(
        status=Status.OK,
        data={"reference": reference, "path": f"/account/orders/{reference}/receipt"},
    )


# --- Returns and refunds ----------------------------------------------------


async def resolve_return_status(ctx: ResolveContext) -> Resolution:
    assert ctx.customer is not None
    rows = await ctx.db.fetch_all(
        """
        SELECT rr.status, rr.reason_code, rr.requested_at, o.public_reference
        FROM return_requests rr
        JOIN orders o ON o.id = rr.order_id
        WHERE rr.customer_user_id = ?
        ORDER BY rr.requested_at DESC
        LIMIT ?
        """,
        (ctx.customer.user_id, _LIST_LIMIT),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    lines = "\n".join(
        f"- {row['public_reference']}: {_label(_RETURN_STATUS, row['status'])}"
        f" (raised {str(row['requested_at'] or '')[:10]})"
        for row in rows
    )
    return Resolution(
        status=Status.OK,
        data={"returns": lines, "count": len(rows)},
        context={"returns": [dict(row) for row in rows]},
    )


async def resolve_refund_status(ctx: ResolveContext) -> Resolution:
    """Refund state as the shop records it: the return row that authorises the
    money, plus the order's own payment status. Deliberately not a promise
    about when a bank will post it -- that is `refund_timing`, a policy fact."""
    assert ctx.customer is not None
    rows = await ctx.db.fetch_all(
        """
        SELECT rr.status, rr.resolution_type, rr.resolution_amount_minor, rr.resolved_at,
               o.public_reference, o.payment_status, o.currency_code
        FROM return_requests rr
        JOIN orders o ON o.id = rr.order_id
        WHERE rr.customer_user_id = ? AND rr.status IN ('approved', 'refunded', 'completed')
        ORDER BY COALESCE(rr.resolved_at, rr.requested_at) DESC
        LIMIT ?
        """,
        (ctx.customer.user_id, _LIST_LIMIT),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    lines = "\n".join(
        f"- {row['public_reference']}: {_label(_RETURN_STATUS, row['status'])}"
        + (
            f", {format_money(row['resolution_amount_minor'], row['currency_code'])}"
            if row["resolution_amount_minor"]
            else ""
        )
        + (f", order shows {_label(_PAYMENT_STATUS, row['payment_status'])}")
        for row in rows
    )
    return Resolution(
        status=Status.OK,
        data={"refunds": lines},
        context={"refunds": [dict(row) for row in rows]},
    )


# --- Catalogue --------------------------------------------------------------


async def _find_products(ctx: ResolveContext, limit: int = _LIST_LIMIT) -> list[dict[str, Any]]:
    """Published products matching the extracted query, best name match first.

    Geo-filtered with the same `geo_release_clause` the storefront's own
    listings use, so the bot can never mention a product the visitor's country
    is not allowed to see.
    """
    query = str(ctx.slot("query") or "").strip()
    if not query:
        return []
    like = f"%{query}%"
    first_word = f"%{query.split()[0]}%"
    geo_sql, geo_params = geo_release_clause(ctx.country)
    return await ctx.db.fetch_all(
        f"""
        SELECT p.id, p.name, p.slug, p.short_description, p.storage_guidance,
               p.growing_method, p.harvest_note, p.accepts_orders,
               f.name AS farm_name, f.slug AS farm_slug, f.region AS farm_region
        FROM products p
        LEFT JOIN farms f ON f.id = p.farm_id
        WHERE p.status = 'published'
          AND (p.name LIKE ? OR p.slug LIKE ? OR p.short_description LIKE ?
               OR p.name LIKE ?){geo_sql}
        ORDER BY CASE WHEN p.name LIKE ? THEN 0 ELSE 1 END, p.name
        LIMIT ?
        """,
        (like, like, like, first_word, *geo_params, like, limit),
    )


async def _variants_for(ctx: ResolveContext, product_id: str) -> list[dict[str, Any]]:
    """Active variants with price and available stock.

    Stock is a correlated subquery rather than a joined aggregate on purpose: a
    variant with two active price rows would otherwise have its on-hand count
    summed twice by the join.
    """
    return await ctx.db.fetch_all(
        """
        SELECT v.id, v.name, v.is_default,
               vp.list_amount_minor, vp.sale_amount_minor, vp.currency_code,
               (SELECT COALESCE(SUM(il.on_hand - il.reserved), 0)
                  FROM inventory_levels il WHERE il.variant_id = v.id) AS available
        FROM product_variants v
        LEFT JOIN variant_prices vp ON vp.variant_id = v.id AND vp.status = 'active'
        WHERE v.product_id = ? AND v.status = 'active'
        ORDER BY v.is_default DESC, v.sort_order, v.name
        """,
        (product_id,),
    )


async def resolve_product_availability(ctx: ResolveContext) -> Resolution:
    if not ctx.slot("query"):
        return Resolution(status=Status.NEEDS_INPUT)
    products = await _find_products(ctx)
    if not products:
        return Resolution(status=Status.EMPTY, data={"query": ctx.slot("query")})

    product = products[0]
    variants = await _variants_for(ctx, product["id"])
    available = sum(int(variant["available"] or 0) for variant in variants)
    in_stock = available > 0 and bool(product["accepts_orders"])
    price = ""
    for variant in variants:
        if variant["list_amount_minor"] is not None:
            effective = variant["sale_amount_minor"] or variant["list_amount_minor"]
            price = format_money(effective, variant["currency_code"])
            break
    return Resolution(
        status=Status.OK,
        data={
            "name": product["name"],
            "stock_state": "in stock" if in_stock else "out of stock",
            "price_sentence": f" It is {price}." if price and in_stock else "",
            "path": f"/product/{product['slug']}",
        },
        context={"product": product["slug"], "available": available},
    )


async def resolve_product_price(ctx: ResolveContext) -> Resolution:
    if not ctx.slot("query"):
        return Resolution(status=Status.NEEDS_INPUT)
    products = await _find_products(ctx)
    if not products:
        return Resolution(status=Status.EMPTY, data={"query": ctx.slot("query")})

    product = products[0]
    variants = await _variants_for(ctx, product["id"])
    priced = [variant for variant in variants if variant["list_amount_minor"] is not None]
    if not priced:
        # Published with no active price row. Saying "free" or guessing would
        # be worse than sending them to the page that shows the real thing.
        return Resolution(
            status=Status.EMPTY,
            data={"query": product["name"], "path": f"/product/{product['slug']}"},
        )

    def _price_line(variant: dict[str, Any]) -> str:
        effective = variant["sale_amount_minor"] or variant["list_amount_minor"]
        currency = variant["currency_code"]
        line = f"- {variant['name'] or 'Standard'}: {format_money(effective, currency)}"
        if variant["sale_amount_minor"]:
            line += f" (was {format_money(variant['list_amount_minor'], currency)})"
        return line

    lines = "\n".join(_price_line(variant) for variant in priced)
    return Resolution(
        status=Status.OK,
        data={"name": product["name"], "prices": lines, "path": f"/product/{product['slug']}"},
    )


async def resolve_product_storage(ctx: ResolveContext) -> Resolution:
    if not ctx.slot("query"):
        return Resolution(status=Status.NEEDS_INPUT)
    products = await _find_products(ctx)
    if not products:
        return Resolution(status=Status.EMPTY, data={"query": ctx.slot("query")})
    product = products[0]
    guidance = str(product["storage_guidance"] or "").strip()
    if not guidance:
        return Resolution(
            status=Status.EMPTY,
            data={"query": product["name"], "path": f"/product/{product['slug']}"},
        )
    return Resolution(
        status=Status.OK,
        data={
            "name": product["name"],
            "guidance": guidance,
            "path": f"/product/{product['slug']}",
        },
    )


async def resolve_product_sourcing(ctx: ResolveContext) -> Resolution:
    if not ctx.slot("query"):
        return Resolution(status=Status.NEEDS_INPUT)
    products = await _find_products(ctx)
    if not products:
        return Resolution(status=Status.EMPTY, data={"query": ctx.slot("query")})
    product = products[0]
    if not product["farm_name"]:
        return Resolution(
            status=Status.EMPTY,
            data={"query": product["name"], "path": f"/product/{product['slug']}"},
        )
    region = f" in {product['farm_region']}" if product["farm_region"] else ""
    method = (
        f" They grow it using {product['growing_method']}." if product["growing_method"] else ""
    )
    return Resolution(
        status=Status.OK,
        data={
            "name": product["name"],
            "farm": product["farm_name"],
            "region": region,
            "method": method,
            "path": f"/farms/{product['farm_slug']}" if product["farm_slug"] else "/farms",
        },
    )


async def resolve_product_certification(ctx: ResolveContext) -> Resolution:
    if not ctx.slot("query"):
        return Resolution(status=Status.NEEDS_INPUT)
    products = await _find_products(ctx)
    if not products:
        return Resolution(status=Status.EMPTY, data={"query": ctx.slot("query")})
    product = products[0]
    # Only approved claims. A certification still under review is not something
    # a customer may be told the product carries.
    rows = await ctx.db.fetch_all(
        """
        SELECT c.name, c.issuing_body
        FROM product_certifications pc
        JOIN certifications c ON c.id = pc.certification_id
        WHERE pc.product_id = ? AND pc.claim_review_state = 'approved'
        ORDER BY c.name
        """,
        (product["id"],),
    )
    if not rows:
        return Resolution(
            status=Status.EMPTY,
            data={"query": product["name"], "path": f"/product/{product['slug']}"},
        )
    listed = "\n".join(
        f"- {row['name']}" + (f" (issued by {row['issuing_body']})" if row["issuing_body"] else "")
        for row in rows
    )
    return Resolution(
        status=Status.OK,
        data={
            "name": product["name"],
            "certifications": listed,
            "path": f"/product/{product['slug']}",
        },
    )


async def resolve_categories(ctx: ResolveContext) -> Resolution:
    geo_sql, geo_params = geo_release_clause(
        ctx.country,
        alias="c",
        table="category_release_countries",
        id_column="category_id",
    )
    rows = await ctx.db.fetch_all(
        f"""
        SELECT c.name, c.slug
        FROM categories c
        WHERE c.status = 'published' AND c.visibility = 'public' AND c.level = 0{geo_sql}
        ORDER BY c.sort_order, c.name
        LIMIT ?
        """,
        (*geo_params, 8),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(f"- {row['name']}: /category/{row['slug']}" for row in rows)
    return Resolution(status=Status.OK, data={"categories": listed})


async def resolve_bundles(ctx: ResolveContext) -> Resolution:
    rows = await ctx.db.fetch_all(
        "SELECT name, slug, bundle_price_minor FROM bundles"
        " WHERE status = 'published' ORDER BY name LIMIT ?",
        (_LIST_LIMIT,),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(f"- {row['name']}: /bundles/{row['slug']}" for row in rows)
    return Resolution(status=Status.OK, data={"bundles": listed})


# --- Delivery ---------------------------------------------------------------


async def resolve_delivery_areas(ctx: ResolveContext) -> Resolution:
    """Answers only for a PIN code the customer actually supplied.

    Listing every serviceable area would be both enormous and misleading, so
    with no PIN code this asks for one instead of guessing.
    """
    postal_code = ctx.slot("postal_code")
    if not postal_code:
        return Resolution(status=Status.NEEDS_INPUT)
    rows = await ctx.db.fetch_all(
        "SELECT name, postal_codes_json, lead_time_hours FROM delivery_zones"
        " WHERE status = 'active'"
    )
    for row in rows:
        # `postal_codes_json` is a JSON array of strings; a substring test on
        # the raw text is enough to decide membership and avoids parsing every
        # zone on every question.
        if f'"{postal_code}"' in str(row["postal_codes_json"] or ""):
            lead = row["lead_time_hours"]
            lead_sentence = (
                f" Orders there usually take about {lead} hours to reach you." if lead else ""
            )
            return Resolution(
                status=Status.OK,
                data={
                    "postal_code": postal_code,
                    "zone": row["name"],
                    "lead_sentence": lead_sentence,
                },
            )
    return Resolution(status=Status.EMPTY, data={"postal_code": postal_code})


async def resolve_pickup_points(ctx: ResolveContext) -> Resolution:
    rows = await ctx.db.fetch_all(
        "SELECT name, hours FROM pickup_points WHERE status = 'active'"
        " ORDER BY sort_order, name LIMIT ?",
        (_LIST_LIMIT,),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(
        f"- {row['name']}" + (f" ({row['hours']})" if row["hours"] else "") for row in rows
    )
    return Resolution(status=Status.OK, data={"points": listed})


# --- Programmes -------------------------------------------------------------


async def resolve_loyalty(ctx: ResolveContext) -> Resolution:
    assert ctx.customer is not None
    row = await ctx.db.fetch_one(
        """
        SELECT la.id,
               (SELECT COALESCE(SUM(lt.points), 0) FROM loyalty_transactions lt
                 WHERE lt.loyalty_account_id = la.id) AS balance
        FROM loyalty_accounts la
        WHERE la.customer_user_id = ? AND la.status = 'active'
        """,
        (ctx.customer.user_id,),
    )
    if row is None:
        return Resolution(status=Status.EMPTY)
    return Resolution(status=Status.OK, data={"points": int(row["balance"] or 0)})


async def resolve_referral(ctx: ResolveContext) -> Resolution:
    assert ctx.customer is not None
    row = await ctx.db.fetch_one(
        "SELECT referral_code FROM loyalty_accounts"
        " WHERE customer_user_id = ? AND status = 'active'",
        (ctx.customer.user_id,),
    )
    if row is None or not row["referral_code"]:
        return Resolution(status=Status.EMPTY)
    return Resolution(status=Status.OK, data={"code": row["referral_code"]})


async def resolve_giftcard_balance(ctx: ResolveContext) -> Resolution:
    """Balance for a code the customer typed.

    Requires a signed-in account (see `IntentSpec.requires_auth` for
    `giftcard_balance`): the code is the bearer instrument, so an anonymous
    endpoint that reports a balance for an arbitrary code is a brute-force
    oracle. Redemptions are subtracted rather than a stored balance being read,
    matching how `services.gift_cards` computes it.
    """
    code = ctx.slot("gift_card_code")
    if not code:
        return Resolution(status=Status.NEEDS_INPUT)
    card = await ctx.db.fetch_one(
        "SELECT id, code, initial_balance_minor, currency_code, status, expires_at"
        " FROM gift_cards WHERE code = ? COLLATE NOCASE",
        (code,),
    )
    if card is None or card["status"] != "active":
        return Resolution(status=Status.EMPTY, data={"code": code})
    used = await ctx.db.fetch_one(
        "SELECT COALESCE(SUM(amount_minor), 0) AS spent FROM gift_card_redemptions"
        " WHERE gift_card_id = ?",
        (card["id"],),
    )
    remaining = int(card["initial_balance_minor"]) - int(used["spent"] if used else 0)
    return Resolution(
        status=Status.OK,
        data={
            "code": card["code"],
            "balance": format_money(max(remaining, 0), card["currency_code"]),
            "expiry_sentence": (
                f" It expires on {str(card['expires_at'])[:10]}." if card["expires_at"] else ""
            ),
        },
    )


async def resolve_subscriptions(ctx: ResolveContext) -> Resolution:
    assert ctx.customer is not None
    rows = await ctx.db.fetch_all(
        """
        SELECT s.frequency, s.status, s.quantity, s.next_order_date, p.name AS product_name
        FROM subscriptions s
        JOIN product_variants v ON v.id = s.variant_id
        JOIN products p ON p.id = v.product_id
        WHERE s.customer_user_id = ? AND s.status IN ('active', 'paused')
        ORDER BY s.next_order_date
        LIMIT ?
        """,
        (ctx.customer.user_id, _LIST_LIMIT),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(
        f"- {row['product_name']} x{row['quantity']},"
        f" {_SUBSCRIPTION_FREQUENCY.get(str(row['frequency']), row['frequency'])}"
        f" ({row['status']})"
        + (f", next on {str(row['next_order_date'])[:10]}" if row["next_order_date"] else "")
        for row in rows
    )
    return Resolution(status=Status.OK, data={"subscriptions": listed})


async def resolve_harvest(ctx: ResolveContext) -> Resolution:
    rows = await ctx.db.fetch_all(
        """
        SELECT hw.title, hw.expected_start, hw.expected_end, hw.status, p.name AS product_name,
               p.slug
        FROM harvest_windows hw
        JOIN products p ON p.id = hw.product_id
        WHERE hw.status IN ('upcoming', 'active', 'harvesting') AND p.status = 'published'
        ORDER BY hw.expected_start
        LIMIT ?
        """,
        (_LIST_LIMIT,),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(
        f"- {row['product_name']}: {row['title']}"
        + (f", expected from {str(row['expected_start'])[:10]}" if row["expected_start"] else "")
        for row in rows
    )
    return Resolution(status=Status.OK, data={"harvests": listed})


async def resolve_promotions(ctx: ResolveContext) -> Resolution:
    """Only promotions that are running right now, and only their headline --
    never a coupon code. Codes live in `coupons` and are distributed
    deliberately; a bot that hands them to anyone who asks gives away margin."""
    rows = await ctx.db.fetch_all(
        """
        SELECT headline, description
        FROM promotions
        WHERE status = 'active'
          AND (starts_at IS NULL OR starts_at <= datetime('now'))
          AND (ends_at IS NULL OR ends_at >= datetime('now'))
          AND headline IS NOT NULL AND headline <> ''
        ORDER BY priority DESC
        LIMIT ?
        """,
        (_LIST_LIMIT,),
    )
    if not rows:
        return Resolution(status=Status.EMPTY)
    listed = "\n".join(f"- {row['headline']}" for row in rows)
    return Resolution(status=Status.OK, data={"promotions": listed})


# --- Content ----------------------------------------------------------------


async def resolve_recipes(ctx: ResolveContext) -> Resolution:
    query = str(ctx.slot("query") or "").strip()
    if query:
        like = f"%{query}%"
        rows = await ctx.db.fetch_all(
            "SELECT title, slug FROM recipes WHERE status = 'published' AND archived_at IS NULL"
            " AND (title LIKE ? OR excerpt LIKE ?) ORDER BY published_at DESC LIMIT ?",
            (like, like, _LIST_LIMIT),
        )
    else:
        rows = await ctx.db.fetch_all(
            "SELECT title, slug FROM recipes WHERE status = 'published' AND archived_at IS NULL"
            " ORDER BY published_at DESC LIMIT ?",
            (_LIST_LIMIT,),
        )
    if not rows:
        return Resolution(status=Status.EMPTY, data={"query": query})
    listed = "\n".join(f"- {row['title']}: /recipes/{row['slug']}" for row in rows)
    return Resolution(status=Status.OK, data={"recipes": listed})


async def resolve_articles(ctx: ResolveContext) -> Resolution:
    query = str(ctx.slot("query") or "").strip()
    if query:
        like = f"%{query}%"
        rows = await ctx.db.fetch_all(
            "SELECT title, slug FROM articles WHERE status = 'published' AND archived_at IS NULL"
            " AND (title LIKE ? OR excerpt LIKE ?) ORDER BY published_at DESC LIMIT ?",
            (like, like, _LIST_LIMIT),
        )
    else:
        rows = await ctx.db.fetch_all(
            "SELECT title, slug FROM articles WHERE status = 'published' AND archived_at IS NULL"
            " ORDER BY published_at DESC LIMIT ?",
            (_LIST_LIMIT,),
        )
    if not rows:
        return Resolution(status=Status.EMPTY, data={"query": query})
    listed = "\n".join(f"- {row['title']}: /blog/{row['slug']}" for row in rows)
    return Resolution(status=Status.OK, data={"articles": listed})


async def resolve_discussions(ctx: ResolveContext) -> Resolution:
    """Community threads. `status = 'visible'` only -- hidden, archived and
    removed threads are moderation decisions a customer must never see."""
    query = str(ctx.slot("query") or "").strip()
    like = f"%{query}%" if query else "%"
    rows = await ctx.db.fetch_all(
        "SELECT id, title, comment_count FROM discussions"
        " WHERE status = 'visible' AND (title LIKE ? OR body LIKE ?)"
        " ORDER BY last_activity_at DESC LIMIT ?",
        (like, like, _LIST_LIMIT),
    )
    if not rows:
        return Resolution(status=Status.EMPTY, data={"query": query})
    listed = "\n".join(
        f"- {row['title']} ({row['comment_count']} replies): /community/{row['id']}" for row in rows
    )
    return Resolution(status=Status.OK, data={"discussions": listed})


RESOLVERS: dict[str, Resolver] = {
    "order_status": resolve_order_status,
    "order_list": resolve_order_list,
    "order_items": resolve_order_items,
    "order_invoice": resolve_order_invoice,
    "return_status": resolve_return_status,
    "refund_status": resolve_refund_status,
    "product_availability": resolve_product_availability,
    "product_price": resolve_product_price,
    "product_storage": resolve_product_storage,
    "product_sourcing": resolve_product_sourcing,
    "product_certification": resolve_product_certification,
    "categories": resolve_categories,
    "bundles": resolve_bundles,
    "delivery_areas": resolve_delivery_areas,
    "pickup_points": resolve_pickup_points,
    "loyalty": resolve_loyalty,
    "referral": resolve_referral,
    "giftcard_balance": resolve_giftcard_balance,
    "subscriptions": resolve_subscriptions,
    "harvest": resolve_harvest,
    "promotions": resolve_promotions,
    "recipes": resolve_recipes,
    "articles": resolve_articles,
    "discussions": resolve_discussions,
}

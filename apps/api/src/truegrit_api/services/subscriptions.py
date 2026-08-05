"""Subscribe & Save: recurring COD deliveries of a single product variant
(migration 0064).

Writes here cover the customer-owned CRUD surface (create/pause/resume/
cancel/update) and the renewal engine. Discount computation and the actual
order write live in `services.checkout.place_order` -- the same "compute and
record in one atomic batch" discipline `services.bundles.resolve_bundle_discount`
documents, so a renewal order and its subscription-savings line can never
drift apart. See migration 0064 for why renewals are cash-on-delivery only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.subscriptions import SubscriptionRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.checkout import CheckoutLine, place_order
from truegrit_api.services.feature_settings import (
    load_subscription_discount_percent,
    subscriptions_enabled,
)
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_FREQUENCIES: Final = frozenset({"weekly", "biweekly", "monthly"})
_MAX_QUANTITY: Final = 12
# Renewal cadence in days. Monthly is a fixed 30 rather than true calendar-month
# arithmetic (which would need to decide what "the 31st, next February" means) --
# a small, documented simplification for a delivery schedule, not a billing
# system where that distinction has financial consequences.
_FREQUENCY_DAYS: Final[dict[str, int]] = {"weekly": 7, "biweekly": 14, "monthly": 30}
_MAX_RENEWALS_PER_RUN: Final = 200


def _today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


def _advance(from_date: str, frequency: str) -> str:
    try:
        current = date.fromisoformat(from_date)
    except ValueError:
        current = datetime.now(UTC).date()
    return (current + timedelta(days=_FREQUENCY_DAYS[frequency])).isoformat()


def serialize_subscription(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "customerUserId": row["customer_user_id"],
        "variantId": row["variant_id"],
        "productId": row["product_id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "variantName": row["variant_name"],
        "sku": row["sku"],
        "imageUrl": row["image_url"],
        "unitPriceMinor": row["unit_price_minor"],
        "quantity": row["quantity"],
        "frequency": row["frequency"],
        "status": row["status"],
        "addressId": row["address_id"],
        "nextOrderDate": row["next_order_date"],
        "lastOrderId": row["last_order_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "cancelledAt": row["cancelled_at"],
        "customerName": row.get("customer_name"),
        "customerEmail": row.get("customer_email"),
    }


async def _load_variant(db: Database, variant_id: str) -> dict[str, Any]:
    row = await db.fetch_one(
        """
        SELECT v.id, v.product_id, p.status AS product_status, p.accepts_orders
        FROM product_variants v
        JOIN products p ON p.id = v.product_id
        WHERE v.id = ? AND v.status = 'active'
        """,
        (variant_id,),
    )
    if row is None:
        raise ValidationAppError("This product is not available to subscribe to.")
    if row["product_status"] != "published" or not row["accepts_orders"]:
        raise ValidationAppError("This product is not currently accepting orders.")
    return row


async def create_subscription(
    db: Database,
    customer: Principal,
    request_id: str,
    *,
    variant_id: str,
    quantity: int,
    frequency: str,
    address_id: str,
) -> dict[str, Any]:
    if not await subscriptions_enabled(db):
        raise ValidationAppError("Subscribe & Save is not available right now.")
    if frequency not in _FREQUENCIES:
        raise ValidationAppError("Unsupported delivery frequency.")
    if not isinstance(quantity, int) or not 1 <= quantity <= _MAX_QUANTITY:
        raise ValidationAppError(f"Quantity must be between 1 and {_MAX_QUANTITY}.")
    await _load_variant(db, variant_id)

    repository = SubscriptionRepository(db)
    address = await repository.get_address(address_id)
    if address is None:
        raise ValidationAppError("Choose a valid delivery address.")
    owned = await db.fetch_one(
        "SELECT id FROM addresses WHERE id = ? AND user_id = ?", (address_id, customer.user_id)
    )
    if owned is None:
        raise ValidationAppError("That address does not belong to your account.")

    now = utc_now_iso()
    subscription_id = new_id("sub")
    # Due immediately (see module docstring): the very next renewal run --
    # cron or an admin's manual trigger -- creates the first order and
    # advances this date forward, the same code path every later renewal
    # uses. No special-cased "place an order at subscribe time" branch to
    # keep in sync with it.
    next_order_date = _today_iso()
    await db.batch(
        [
            (
                """
                INSERT INTO subscriptions
                  (id, customer_user_id, variant_id, quantity, frequency, status,
                   address_id, next_order_date, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
                """,
                (
                    subscription_id,
                    customer.user_id,
                    variant_id,
                    quantity,
                    frequency,
                    address_id,
                    next_order_date,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="subscription.created",
                entity_type="subscription",
                entity_id=subscription_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                after={"variant_id": variant_id, "quantity": quantity, "frequency": frequency},
            ),
        ]
    )
    created = await repository.get_by_id(subscription_id)
    assert created is not None
    return serialize_subscription(created)


async def list_my_subscriptions(
    db: Database, customer: Principal, *, status: str | None = None
) -> list[dict[str, Any]]:
    repository = SubscriptionRepository(db)
    rows = await repository.list_for_customer(customer.user_id, status=status)
    return [serialize_subscription(row) for row in rows]


async def list_admin_subscriptions(
    db: Database,
    *,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    farm_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    repository = SubscriptionRepository(db)
    rows = await repository.list_admin(limit=limit, offset=offset, status=status, farm_id=farm_id)
    total = await repository.count_admin(status=status, farm_id=farm_id)
    return [serialize_subscription(row) for row in rows], total


async def _get_owned_or_staff(
    db: Database, subscription_id: str, actor: Principal
) -> dict[str, Any]:
    """Customers may only reach their own subscription; staff with
    `subscriptions.manage` may reach any (support: pause/cancel on a
    customer's behalf) -- except a farm-scoped staff member, who may only
    reach a subscription for their own farm's product. Dormant today: no
    seeded role holds `subscriptions.manage` and a `farm_id` at once."""
    repository = SubscriptionRepository(db)
    if actor.has("subscriptions.manage"):
        row = await repository.get_by_id(subscription_id)
        if row is not None and actor.farm_id is not None and row["farm_id"] != actor.farm_id:
            row = None
    else:
        row = await repository.get_owned(subscription_id, actor.user_id)
    if row is None:
        raise NotFoundError("Subscription not found.")
    return row


async def update_subscription(
    db: Database,
    actor: Principal,
    request_id: str,
    subscription_id: str,
    *,
    quantity: int | None = None,
    frequency: str | None = None,
    address_id: str | None = None,
) -> dict[str, Any]:
    current = await _get_owned_or_staff(db, subscription_id, actor)
    if current["status"] == "cancelled":
        raise ValidationAppError("A cancelled subscription cannot be edited.")

    updates: dict[str, Any] = {}
    if quantity is not None:
        if not isinstance(quantity, int) or not 1 <= quantity <= _MAX_QUANTITY:
            raise ValidationAppError(f"Quantity must be between 1 and {_MAX_QUANTITY}.")
        updates["quantity"] = quantity
    if frequency is not None:
        if frequency not in _FREQUENCIES:
            raise ValidationAppError("Unsupported delivery frequency.")
        updates["frequency"] = frequency
    if address_id is not None:
        repository = SubscriptionRepository(db)
        address = await repository.get_address(address_id)
        owned = await db.fetch_one(
            "SELECT id FROM addresses WHERE id = ? AND user_id = ?",
            (address_id, current["customer_user_id"]),
        )
        if address is None or owned is None:
            raise ValidationAppError("Choose a valid delivery address.")
        updates["address_id"] = address_id

    if not updates:
        return serialize_subscription(current)

    now = utc_now_iso()
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    await db.batch(
        [
            (
                f"UPDATE subscriptions SET {set_clause}, updated_at = ? WHERE id = ?",
                (*updates.values(), now, subscription_id),
            ),
            audit_statement(
                action="subscription.updated",
                entity_type="subscription",
                entity_id=subscription_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={key: current[key] for key in updates},
                after=updates,
            ),
        ]
    )
    repository = SubscriptionRepository(db)
    updated = await repository.get_by_id(subscription_id)
    assert updated is not None
    return serialize_subscription(updated)


async def _set_status(
    db: Database,
    actor: Principal,
    request_id: str,
    subscription_id: str,
    *,
    new_status: str,
    allowed_from: frozenset[str],
    action: str,
) -> dict[str, Any]:
    current = await _get_owned_or_staff(db, subscription_id, actor)
    if current["status"] not in allowed_from:
        raise ConflictError(f"Subscription is {current['status']}, cannot {action.split('.')[-1]}.")

    now = utc_now_iso()
    cancelled_at = now if new_status == "cancelled" else None
    await db.batch(
        [
            (
                "UPDATE subscriptions SET status = ?, cancelled_at = COALESCE(?, cancelled_at),"
                " updated_at = ? WHERE id = ?",
                (new_status, cancelled_at, now, subscription_id),
            ),
            audit_statement(
                action=action,
                entity_type="subscription",
                entity_id=subscription_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": new_status},
            ),
        ]
    )
    repository = SubscriptionRepository(db)
    updated = await repository.get_by_id(subscription_id)
    assert updated is not None
    return serialize_subscription(updated)


async def pause_subscription(
    db: Database, actor: Principal, request_id: str, subscription_id: str
) -> dict[str, Any]:
    return await _set_status(
        db,
        actor,
        request_id,
        subscription_id,
        new_status="paused",
        allowed_from=frozenset({"active"}),
        action="subscription.paused",
    )


async def resume_subscription(
    db: Database, actor: Principal, request_id: str, subscription_id: str
) -> dict[str, Any]:
    current = await _get_owned_or_staff(db, subscription_id, actor)
    if current["status"] != "paused":
        raise ConflictError(f"Subscription is {current['status']}, cannot resume.")
    now = utc_now_iso()
    today = _today_iso()
    # Resuming after a pause must never fast-forward through every renewal
    # missed while paused: whichever is later -- today, or the date it was
    # already due before pausing -- becomes due next, so a customer who
    # pauses for a month is not immediately billed for the weeks they paused.
    resumed_next_date = max(current["next_order_date"], today)
    await db.batch(
        [
            (
                "UPDATE subscriptions SET status = 'active', next_order_date = ?,"
                " updated_at = ? WHERE id = ?",
                (resumed_next_date, now, subscription_id),
            ),
            audit_statement(
                action="subscription.resumed",
                entity_type="subscription",
                entity_id=subscription_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": "paused"},
                after={"status": "active", "next_order_date": resumed_next_date},
            ),
        ]
    )
    repository = SubscriptionRepository(db)
    updated = await repository.get_by_id(subscription_id)
    assert updated is not None
    return serialize_subscription(updated)


async def cancel_subscription(
    db: Database, actor: Principal, request_id: str, subscription_id: str
) -> dict[str, Any]:
    return await _set_status(
        db,
        actor,
        request_id,
        subscription_id,
        new_status="cancelled",
        allowed_from=frozenset({"active", "paused"}),
        action="subscription.cancelled",
    )


@dataclass(frozen=True)
class RenewalOutcome:
    subscription_id: str
    order_id: str | None
    skipped_reason: str | None = None


async def _renewal_principal(db: Database, customer_user_id: str) -> Principal | None:
    """A minimal Principal for the customer a renewal order is placed for --
    same shape `auth.sessions.resolve_session` builds from a live session,
    fetched fresh here since a renewal has no session of its own. Returns
    None for a disabled account: an owner who disabled a customer's account
    must not have that customer keep getting billed."""
    row = await db.fetch_one(
        """
        SELECT id, display_name, email, user_type, phone_e164, phone_verified_at
        FROM users WHERE id = ? AND status = 'active'
        """,
        (customer_user_id,),
    )
    if row is None:
        return None
    return Principal(
        user_id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        user_type=row["user_type"],
        phone_e164=row["phone_e164"] if row["phone_verified_at"] else None,
    )


async def run_due_renewals(
    db: Database,
    request_id: str,
    *,
    limit: int = _MAX_RENEWALS_PER_RUN,
    triggered_by: str | None = None,
) -> dict[str, Any]:
    """Place one renewal order for every active subscription due today or
    earlier. Called on a schedule (the Worker's `scheduled` handler, see
    `worker.py`) and, for visibility while the feature is dormant or being
    tested, from an admin-triggered endpoint that runs the identical code
    path. One subscription's failure (a variant gone out of stock, an
    address archived, a payment conflict) never blocks the rest of the
    batch -- each is isolated and reported individually.
    """
    if not await subscriptions_enabled(db):
        return {"processed": 0, "succeeded": 0, "outcomes": []}

    repository = SubscriptionRepository(db)
    discount_percent = await load_subscription_discount_percent(db)
    today = _today_iso()
    due = await repository.list_due(as_of_date=today, limit=limit)

    outcomes: list[RenewalOutcome] = []
    for row in due:
        subscription_id = row["id"]
        try:
            customer = await _renewal_principal(db, row["customer_user_id"])
            if customer is None:
                outcomes.append(
                    RenewalOutcome(subscription_id, None, "customer account is not active")
                )
                continue
            address_row = await repository.get_address(row["address_id"])
            if address_row is None:
                outcomes.append(
                    RenewalOutcome(subscription_id, None, "delivery address no longer available")
                )
                continue
            delivery_address = {
                "recipient_name": address_row["recipient_name"],
                "phone_e164": address_row["phone_e164"],
                "line1": address_row["line1"],
                "line2": address_row["line2"],
                "city": address_row["city"],
                "state": address_row["state"],
                "postal_code": address_row["postal_code"],
                "country_code": address_row["country_code"],
            }
            result = await place_order(
                db,
                customer,
                request_id,
                items=[CheckoutLine(variant_id=row["variant_id"], quantity=row["quantity"])],
                delivery_address=delivery_address,
                payment_method="cod",
                idempotency_key=f"sub:{subscription_id}:{row['next_order_date']}",
                subscription_id=subscription_id,
                subscription_discount_percent=discount_percent,
            )
        except (ValidationAppError, ConflictError) as exc:
            outcomes.append(RenewalOutcome(subscription_id, None, str(exc)))
            continue

        next_date = _advance(row["next_order_date"], row["frequency"])
        now = utc_now_iso()
        # Conditional on the due-date it was read at: if a concurrent run
        # already advanced this subscription past today, that run's write
        # wins and this one is a no-op -- `place_order`'s own idempotency key
        # (above) already guarantees the order itself was never duplicated
        # either way.
        await db.execute(
            "UPDATE subscriptions SET next_order_date = ?, last_order_id = ?, updated_at = ?"
            " WHERE id = ? AND next_order_date <= ?",
            (next_date, result["id"], now, subscription_id, today),
        )
        outcomes.append(RenewalOutcome(subscription_id, result["id"]))

    succeeded = sum(1 for outcome in outcomes if outcome.order_id is not None)
    await db.execute(
        *audit_statement(
            action="subscriptions.renewals_run",
            entity_type="subscription_batch",
            entity_id=request_id,
            actor_id=triggered_by,
            request_id=request_id,
            created_at=utc_now_iso(),
            source="admin" if triggered_by else "system",
            after={"processed": len(outcomes), "succeeded": succeeded},
        )
    )
    return {
        "processed": len(outcomes),
        "succeeded": succeeded,
        "outcomes": [
            {
                "subscriptionId": outcome.subscription_id,
                "orderId": outcome.order_id,
                "skippedReason": outcome.skipped_reason,
            }
            for outcome in outcomes
        ],
    }

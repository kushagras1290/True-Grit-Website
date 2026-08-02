"""Coupons and promotions (migration 0005, extended by 0060).

A promotion with no coupons is automatic: `resolve_checkout_discount` applies
the highest-priority currently-active one to every eligible cart with no code
needed. A promotion with one or more coupons only applies when a customer
enters a matching, still-usable code. Only one promotion ever applies to an
order in this build -- a coupon code, when given and valid, always wins over
an automatic promotion; `stacking_policy` is recorded but combining multiple
promotions on one order is not implemented.

Writes here cover the admin CRUD surface (create/update/archive/delete a
promotion, issue/revoke a coupon). `resolve_checkout_discount` is read-only by
design: it is called from `services.checkout.place_order`, which owns the
order's batch and is responsible for actually writing the redemption and
`order_adjustments` row alongside the order itself, so a discount can never be
computed without being recorded, or recorded without an order behind it.
"""

from __future__ import annotations

import json
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.money import apply_discount, basis_points_discount
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.promotions import PromotionRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_NAME: Final = 160
_MAX_HEADLINE: Final = 160
_MAX_DESCRIPTION: Final = 400
_MAX_CODE: Final = 32
_STATUSES: Final = frozenset({"draft", "scheduled", "active", "paused", "ended", "archived"})
_STACKING_POLICIES: Final = frozenset({"exclusive", "stackable"})
_ACTION_TYPES: Final = frozenset({"percentage_discount", "fixed_discount", "free_delivery"})


def _clean_code(code: str) -> str:
    cleaned = code.strip().upper()
    if not cleaned or len(cleaned) > _MAX_CODE:
        raise ValidationAppError(f"A coupon code must be 1-{_MAX_CODE} characters.")
    return cleaned


async def create_promotion(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    name: str,
    headline: str | None,
    description: str | None,
    status: str,
    priority: int,
    starts_at: str | None,
    ends_at: str | None,
    stacking_policy: str,
    usage_limit_total: int | None,
    usage_limit_per_customer: int | None,
    min_subtotal_minor: int | None,
    action_type: str,
    value_basis_points: int | None,
    amount_minor: int | None,
    maximum_discount_minor: int | None,
) -> dict[str, Any]:
    clean_name = name.strip()
    if not clean_name or len(clean_name) > _MAX_NAME:
        raise ValidationAppError(f"Name must be 1-{_MAX_NAME} characters.")
    if status not in _STATUSES:
        raise ValidationAppError("Unsupported status.")
    if stacking_policy not in _STACKING_POLICIES:
        raise ValidationAppError("Unsupported stacking policy.")
    if action_type not in _ACTION_TYPES:
        raise ValidationAppError("Unsupported action type.")
    if action_type == "percentage_discount":
        if value_basis_points is None or not 0 <= value_basis_points <= 10_000:
            raise ValidationAppError("Percentage discount needs a value between 0 and 100%.")
    elif action_type == "fixed_discount" and (amount_minor is None or amount_minor < 0):
        raise ValidationAppError("Fixed discount needs a non-negative amount.")
    if ends_at and starts_at and ends_at <= starts_at:
        raise ValidationAppError("The end date must be after the start date.")

    now = utc_now_iso()
    promotion_id = new_id("promo")
    statements: list[tuple[str, Any]] = [
        (
            "INSERT INTO promotions"
            " (id, name, status, priority, starts_at, ends_at, stacking_policy,"
            "  usage_limit_total, usage_limit_per_customer, headline, description,"
            "  created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                promotion_id,
                clean_name,
                status,
                priority,
                starts_at,
                ends_at,
                stacking_policy,
                usage_limit_total,
                usage_limit_per_customer,
                (headline or "").strip()[:_MAX_HEADLINE] or None,
                (description or "").strip()[:_MAX_DESCRIPTION] or None,
                now,
                actor.user_id,
                now,
                actor.user_id,
            ),
        ),
        (
            "INSERT INTO promotion_actions"
            " (id, promotion_id, action_type, value_basis_points, amount_minor,"
            "  maximum_discount_minor)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                new_id("pact"),
                promotion_id,
                action_type,
                value_basis_points,
                amount_minor,
                maximum_discount_minor,
            ),
        ),
    ]
    if min_subtotal_minor is not None:
        statements.append(
            (
                "INSERT INTO promotion_rules (id, promotion_id, rule_json) VALUES (?, ?, ?)",
                (
                    new_id("prule"),
                    promotion_id,
                    json.dumps({"minSubtotalMinor": min_subtotal_minor}),
                ),
            )
        )
    statements.append(
        audit_statement(
            action="promotion.created",
            entity_type="promotion",
            entity_id=promotion_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"name": clean_name, "status": status, "actionType": action_type},
        )
    )
    await db.batch(statements)
    return {"id": promotion_id, "status": status}


async def update_promotion(
    db: Database, actor: Principal, request_id: str, promotion_id: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Partial update of the promotion row itself (name/status/schedule/limits/
    copy). The action and rule are set once at creation in this build --
    editing them means archiving and creating a fresh promotion, the same way
    a payment provider's plan is versioned rather than mutated underneath
    orders that already reference it."""
    current = await db.fetch_one("SELECT * FROM promotions WHERE id = ?", (promotion_id,))
    if current is None:
        raise NotFoundError("Promotion not found.")

    updates: dict[str, Any] = {}
    if "name" in fields:
        clean_name = (fields["name"] or "").strip()
        if not clean_name or len(clean_name) > _MAX_NAME:
            raise ValidationAppError(f"Name must be 1-{_MAX_NAME} characters.")
        updates["name"] = clean_name
    if "status" in fields:
        if fields["status"] not in _STATUSES:
            raise ValidationAppError("Unsupported status.")
        updates["status"] = fields["status"]
    if "priority" in fields:
        updates["priority"] = int(fields["priority"])
    if "starts_at" in fields:
        updates["starts_at"] = fields["starts_at"]
    if "ends_at" in fields:
        updates["ends_at"] = fields["ends_at"]
    if "usage_limit_total" in fields:
        updates["usage_limit_total"] = fields["usage_limit_total"]
    if "usage_limit_per_customer" in fields:
        updates["usage_limit_per_customer"] = fields["usage_limit_per_customer"]
    if "headline" in fields:
        updates["headline"] = (fields["headline"] or "").strip()[:_MAX_HEADLINE] or None
    if "description" in fields:
        updates["description"] = (fields["description"] or "").strip()[:_MAX_DESCRIPTION] or None
    if not updates:
        return {"id": promotion_id, "status": current["status"]}

    starts_at = updates.get("starts_at", current["starts_at"])
    ends_at = updates.get("ends_at", current["ends_at"])
    if ends_at and starts_at and ends_at <= starts_at:
        raise ValidationAppError("The end date must be after the start date.")

    now = utc_now_iso()
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    await db.batch(
        [
            (
                f"UPDATE promotions SET {set_clause}, updated_at = ?, updated_by = ? WHERE id = ?",
                (*updates.values(), now, actor.user_id, promotion_id),
            ),
            audit_statement(
                action="promotion.updated",
                entity_type="promotion",
                entity_id=promotion_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={key: current[key] for key in updates},
                after=updates,
            ),
        ]
    )
    return {"id": promotion_id, "status": updates.get("status", current["status"])}


async def delete_promotion(
    db: Database, actor: Principal, request_id: str, promotion_id: str
) -> dict[str, Any]:
    """Archive a promotion with redemption history (money already moved
    because of it, so the record has to stay); permanently delete one that
    was never used. `coupon_redemptions.coupon_id` is `ON DELETE RESTRICT`
    precisely so this can't be gotten wrong by accident -- a redeemed
    promotion's DELETE fails at the database layer, not just in this check."""
    current = await db.fetch_one("SELECT status FROM promotions WHERE id = ?", (promotion_id,))
    if current is None:
        raise NotFoundError("Promotion not found.")
    redeemed = await db.fetch_one(
        """
        SELECT COUNT(*) AS total FROM coupon_redemptions cr
        JOIN coupons c ON c.id = cr.coupon_id
        WHERE c.promotion_id = ?
        """,
        (promotion_id,),
    )
    now = utc_now_iso()
    if redeemed and int(redeemed["total"]) > 0:
        await db.batch(
            [
                (
                    "UPDATE promotions SET status = 'archived', updated_at = ?,"
                    " updated_by = ? WHERE id = ?",
                    (now, actor.user_id, promotion_id),
                ),
                audit_statement(
                    action="promotion.archived",
                    entity_type="promotion",
                    entity_id=promotion_id,
                    actor_id=actor.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "archived"},
                ),
            ]
        )
        return {"id": promotion_id, "status": "archived", "deleted": False}

    await db.batch(
        [
            ("DELETE FROM promotions WHERE id = ?", (promotion_id,)),
            audit_statement(
                action="promotion.deleted",
                entity_type="promotion",
                entity_id=promotion_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": promotion_id, "status": "deleted", "deleted": True}


async def create_coupon(
    db: Database, actor: Principal, request_id: str, promotion_id: str, *, code: str
) -> dict[str, Any]:
    promotion = await db.fetch_one("SELECT id FROM promotions WHERE id = ?", (promotion_id,))
    if promotion is None:
        raise NotFoundError("Promotion not found.")
    clean_code = _clean_code(code)
    existing = await db.fetch_one("SELECT id FROM coupons WHERE code = ?", (clean_code,))
    if existing is not None:
        raise ConflictError(f'The code "{clean_code}" is already in use.')

    now = utc_now_iso()
    coupon_id = new_id("cpn")
    await db.batch(
        [
            (
                "INSERT INTO coupons (id, promotion_id, code, active, created_at)"
                " VALUES (?, ?, ?, 1, ?)",
                (coupon_id, promotion_id, clean_code, now),
            ),
            audit_statement(
                action="coupon.created",
                entity_type="coupon",
                entity_id=coupon_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"promotionId": promotion_id, "code": clean_code},
            ),
        ]
    )
    return {"id": coupon_id, "code": clean_code}


async def set_coupon_active(
    db: Database, actor: Principal, request_id: str, coupon_id: str, *, active: bool
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT active FROM coupons WHERE id = ?", (coupon_id,))
    if current is None:
        raise NotFoundError("Coupon not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("UPDATE coupons SET active = ? WHERE id = ?", (1 if active else 0, coupon_id)),
            audit_statement(
                action="coupon.activated" if active else "coupon.deactivated",
                entity_type="coupon",
                entity_id=coupon_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"active": bool(current["active"])},
                after={"active": active},
            ),
        ]
    )
    return {"id": coupon_id, "active": active}


async def delete_coupon(
    db: Database, actor: Principal, request_id: str, coupon_id: str
) -> dict[str, Any]:
    """Same redeemed-history guard as `delete_promotion`: a used code is
    deactivated, never erased."""
    current = await db.fetch_one("SELECT active FROM coupons WHERE id = ?", (coupon_id,))
    if current is None:
        raise NotFoundError("Coupon not found.")
    redeemed = await db.fetch_one(
        "SELECT COUNT(*) AS total FROM coupon_redemptions WHERE coupon_id = ?", (coupon_id,)
    )
    if redeemed and int(redeemed["total"]) > 0:
        return await set_coupon_active(db, actor, request_id, coupon_id, active=False)

    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM coupons WHERE id = ?", (coupon_id,)),
            audit_statement(
                action="coupon.deleted",
                entity_type="coupon",
                entity_id=coupon_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": coupon_id, "deleted": True}


def _compute_discount(
    action: dict[str, Any], subtotal_minor: int, delivery_minor: int
) -> dict[str, Any]:
    action_type = action["action_type"]
    if action_type == "percentage_discount":
        discount = basis_points_discount(
            subtotal_minor, action["value_basis_points"], action["maximum_discount_minor"]
        )
        return {"discount_minor": discount, "free_delivery": False}
    if action_type == "fixed_discount":
        discount = subtotal_minor - apply_discount(subtotal_minor, action["amount_minor"])
        return {"discount_minor": discount, "free_delivery": False}
    # free_delivery
    return {"discount_minor": delivery_minor, "free_delivery": True}


def _rule_matches(rule: dict[str, Any] | None, subtotal_minor: int) -> bool:
    if rule is None:
        return True
    conditions = json.loads(rule["rule_json"])
    minimum = conditions.get("minSubtotalMinor")
    return minimum is None or subtotal_minor >= int(minimum)


async def resolve_checkout_discount(
    db: Database,
    *,
    subtotal_minor: int,
    delivery_minor: int,
    coupon_code: str | None,
    customer_user_id: str,
) -> dict[str, Any] | None:
    """What, if anything, applies to this cart. Returns `None` when nothing
    does. Raises on a coupon code that cannot be honoured -- unlike an
    automatic promotion silently not matching, a customer who typed a code
    deserves a reason it did not work."""
    repository = PromotionRepository(db)
    now = utc_now_iso()

    if coupon_code:
        clean_code = _clean_code(coupon_code)
        row = await repository.get_coupon_by_code(clean_code)
        if row is None or not row["coupon_active"]:
            raise ValidationAppError("This code is not valid.")
        if row["status"] != "active":
            raise ValidationAppError("This code is no longer active.")
        if row["starts_at"] and row["starts_at"] > now:
            raise ValidationAppError("This code is not active yet.")
        if row["ends_at"] and row["ends_at"] <= now:
            raise ValidationAppError("This code has expired.")
        if row["usage_limit_total"] is not None:
            used = await repository.count_redemptions(row["coupon_id"])
            if used >= int(row["usage_limit_total"]):
                raise ValidationAppError("This code has reached its usage limit.")
        if row["usage_limit_per_customer"] is not None:
            used_by_customer = await repository.count_redemptions(
                row["coupon_id"], customer_user_id=customer_user_id
            )
            if used_by_customer >= int(row["usage_limit_per_customer"]):
                raise ValidationAppError("You have already used this code.")
        rule = await repository.get_rule(row["promotion_id"])
        if not _rule_matches(rule, subtotal_minor):
            raise ValidationAppError("Your order does not meet this code's minimum.")
        action = await repository.get_action(row["promotion_id"])
        if action is None:
            raise ValidationAppError("This code is not configured correctly.")
        computed = _compute_discount(action, subtotal_minor, delivery_minor)
        return {
            "promotion_id": row["promotion_id"],
            "coupon_id": row["coupon_id"],
            "code": row["code"],
            "headline": row["headline"] or row["code"],
            **computed,
        }

    for promotion in await repository.list_active_automatic(now):
        rule = await repository.get_rule(promotion["id"])
        if not _rule_matches(rule, subtotal_minor):
            continue
        action = await repository.get_action(promotion["id"])
        if action is None:
            continue
        computed = _compute_discount(action, subtotal_minor, delivery_minor)
        if computed["discount_minor"] <= 0 and not computed["free_delivery"]:
            continue
        return {
            "promotion_id": promotion["id"],
            "coupon_id": None,
            "code": None,
            "headline": promotion["headline"] or promotion["name"],
            **computed,
        }
    return None

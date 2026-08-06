"""Gift card issuance and checkout redemption.

Balance is derived, never stored: `initial_balance_minor - SUM(gift_card_
redemptions.amount_minor)` for a card, computed fresh on every read. See the
WHY note in migration 0082 for why this is a ledger, not a mutable counter,
and why redemption lands on `orders.gift_card_applied_minor`/`gift_card_code`
rather than a new `order_adjustments.adjustment_type`.

Read the resolver (`resolve_checkout_redemption`) and the writer
(`services.checkout.place_order`) together: the resolver only ever computes
what *would* be applied, never writes -- exactly the split
`services.promotions.resolve_checkout_discount` already uses for coupons, so
a redemption can never be computed without landing in the same order-creation
batch, or recorded without an order behind it.
"""

from __future__ import annotations

import re
import secrets
import string
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

MIN_BALANCE_MINOR = 10_000  # INR 100 -- a card small enough to be pointless costs more in
MAX_BALANCE_MINOR = 5_000_000  # support time than it is worth issuing. INR 50,000 ceiling.
_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 12
_CODE_PATTERN = re.compile(r"^[A-Z0-9]{6,24}$")


def _generate_code() -> str:
    return "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def _balance_minor(db: Database, gift_card: dict[str, Any]) -> int:
    redeemed = await db.fetch_one(
        "SELECT COALESCE(SUM(amount_minor), 0) AS redeemed FROM gift_card_redemptions"
        " WHERE gift_card_id = ?",
        (gift_card["id"],),
    )
    redeemed_minor = int(redeemed["redeemed"]) if redeemed else 0
    return max(int(gift_card["initial_balance_minor"]) - redeemed_minor, 0)


def _is_expired(gift_card: dict[str, Any], now: str) -> bool:
    return gift_card["expires_at"] is not None and gift_card["expires_at"] < now


async def get_balance_by_code(db: Database, code: str) -> dict[str, Any]:
    """Public balance lookup -- a customer checking what is left on a card
    they hold, independent of any checkout in progress."""
    clean_code = code.strip()
    if not clean_code:
        raise NotFoundError("Gift card not found.")
    gift_card = await db.fetch_one(
        "SELECT * FROM gift_cards WHERE code = ? COLLATE NOCASE", (clean_code,)
    )
    if gift_card is None:
        raise NotFoundError("Gift card not found.")
    now = utc_now_iso()
    status = "expired" if _is_expired(gift_card, now) else gift_card["status"]
    balance = await _balance_minor(db, gift_card) if status == "active" else 0
    return {
        "code": gift_card["code"],
        "status": status,
        "balanceMinor": balance,
        "currencyCode": gift_card["currency_code"],
        "expiresAt": gift_card["expires_at"],
    }


async def resolve_checkout_redemption(
    db: Database, *, code: str | None, amount_needed_minor: int
) -> dict[str, Any] | None:
    """What a gift card code would cover toward `amount_needed_minor`, or
    None if no code was given. Raises for a code that cannot be applied at
    all (not found, inactive, expired, empty) -- same "tell the customer
    their code did not work" behaviour `resolve_checkout_discount` uses for
    coupons, rather than silently ignoring a typo."""
    clean_code = (code or "").strip()
    if not clean_code:
        return None
    gift_card = await db.fetch_one(
        "SELECT * FROM gift_cards WHERE code = ? COLLATE NOCASE", (clean_code,)
    )
    if gift_card is None:
        raise ValidationAppError("That gift card code was not found.")
    if gift_card["status"] != "active":
        raise ValidationAppError("That gift card is no longer active.")
    now = utc_now_iso()
    if _is_expired(gift_card, now):
        raise ValidationAppError("That gift card has expired.")
    balance = await _balance_minor(db, gift_card)
    if balance <= 0:
        raise ValidationAppError("That gift card has no balance remaining.")
    applied = min(balance, max(amount_needed_minor, 0))
    return {
        "gift_card_id": gift_card["id"],
        "code": gift_card["code"],
        "applied_minor": applied,
        "balance_minor": balance,
        "remaining_after_minor": balance - applied,
    }


async def issue_gift_card(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    balance_minor: int,
    issued_to_email: str | None = None,
    note: str | None = None,
    expires_at: str | None = None,
    code: str | None = None,
) -> dict[str, Any]:
    if balance_minor < MIN_BALANCE_MINOR or balance_minor > MAX_BALANCE_MINOR:
        raise ValidationAppError(
            f"Gift card value must be between {MIN_BALANCE_MINOR // 100} and"
            f" {MAX_BALANCE_MINOR // 100} INR."
        )
    clean_email = (issued_to_email or "").strip() or None
    clean_note = (note or "").strip()[:300] or None
    clean_code = (code or "").strip().upper() or _generate_code()
    if not _CODE_PATTERN.match(clean_code):
        raise ValidationAppError("Gift card codes must be 6-24 letters and numbers.")
    existing = await db.fetch_one(
        "SELECT id FROM gift_cards WHERE code = ? COLLATE NOCASE", (clean_code,)
    )
    if existing is not None:
        raise ConflictError("A gift card with this code already exists.")

    gift_card_id = new_id("gft")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO gift_cards"
                " (id, code, initial_balance_minor, currency_code, status,"
                "  issued_to_email, note, expires_at, created_at, created_by)"
                " VALUES (?, ?, ?, 'INR', 'active', ?, ?, ?, ?, ?)",
                (
                    gift_card_id,
                    clean_code,
                    balance_minor,
                    clean_email,
                    clean_note,
                    expires_at,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="gift_card.issued",
                entity_type="gift_card",
                entity_id=gift_card_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "code": clean_code,
                    "balanceMinor": balance_minor,
                    "issuedToEmail": clean_email,
                },
            ),
        ]
    )
    return {"id": gift_card_id, "code": clean_code, "balanceMinor": balance_minor}


async def cancel_gift_card(
    db: Database, actor: Principal, request_id: str, gift_card_id: str
) -> None:
    """Stops future redemption. Past redemptions are untouched -- cancelling
    a partially-spent card does not claw back what already paid for an
    order, the same reasoning a coupon's usage history survives the coupon
    being deleted (0005's ON DELETE RESTRICT on coupon_redemptions)."""
    gift_card = await db.fetch_one(
        "SELECT id, status FROM gift_cards WHERE id = ?", (gift_card_id,)
    )
    if gift_card is None:
        raise NotFoundError("Gift card not found.")
    if gift_card["status"] == "cancelled":
        return
    now = utc_now_iso()
    await db.batch(
        [
            ("UPDATE gift_cards SET status = 'cancelled' WHERE id = ?", (gift_card_id,)),
            audit_statement(
                action="gift_card.cancelled",
                entity_type="gift_card",
                entity_id=gift_card_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"status": "cancelled"},
            ),
        ]
    )

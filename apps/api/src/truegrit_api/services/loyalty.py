"""Loyalty points and referral codes.

Balance is derived, never stored: `SUM(loyalty_transactions.points)` for an
account, computed fresh on every read.  Same reasoning as gift_cards -- a
mutable counter invites exactly the lost-update bug a derived balance exists
to prevent.

Points are earned on completed orders and redeemable at checkout toward the
order total, same integration shape as gift cards.  Referral codes reward both
parties (referrer + referred) once the referred customer's first order is
placed.
"""

from __future__ import annotations

import secrets
import string
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_CODE_ALPHABET = string.ascii_uppercase + string.digits
_CODE_LENGTH = 8


def _generate_referral_code() -> str:
    return "REF-" + "".join(secrets.choice(_CODE_ALPHABET) for _ in range(_CODE_LENGTH))


async def _ensure_account(db: Database, customer_user_id: str) -> dict[str, Any]:
    """Get or lazily create a loyalty account for a customer."""
    account = await db.fetch_one(
        "SELECT * FROM loyalty_accounts WHERE customer_user_id = ?",
        (customer_user_id,),
    )
    if account is not None:
        return account
    account_id = new_id("loy")
    now = utc_now_iso()
    code = _generate_referral_code()
    # Retry once if the referral code collides (astronomically unlikely).
    for _attempt in range(3):
        existing = await db.fetch_one(
            "SELECT id FROM loyalty_accounts WHERE referral_code = ? COLLATE NOCASE",
            (code,),
        )
        if existing is None:
            break
        code = _generate_referral_code()
    await db.execute(
        "INSERT OR IGNORE INTO loyalty_accounts"
        " (id, customer_user_id, referral_code, status, created_at)"
        " VALUES (?, ?, ?, 'active', ?)",
        (account_id, customer_user_id, code, now),
    )
    return await db.fetch_one(
        "SELECT * FROM loyalty_accounts WHERE customer_user_id = ?",
        (customer_user_id,),
    )  # type: ignore[return-value]


async def get_balance(db: Database, customer_user_id: str) -> int:
    """Derived balance for a customer -- sum of all transaction points."""
    account = await db.fetch_one(
        "SELECT id FROM loyalty_accounts WHERE customer_user_id = ?",
        (customer_user_id,),
    )
    if account is None:
        return 0
    row = await db.fetch_one(
        "SELECT COALESCE(SUM(points), 0) AS balance FROM loyalty_transactions"
        " WHERE loyalty_account_id = ?",
        (account["id"],),
    )
    return max(int(row["balance"]) if row else 0, 0)


async def get_customer_loyalty(db: Database, customer_user_id: str) -> dict[str, Any]:
    """Public loyalty info for a customer: balance + referral code."""
    account = await _ensure_account(db, customer_user_id)
    balance = 0
    if account:
        row = await db.fetch_one(
            "SELECT COALESCE(SUM(points), 0) AS balance FROM loyalty_transactions"
            " WHERE loyalty_account_id = ?",
            (account["id"],),
        )
        balance = max(int(row["balance"]) if row else 0, 0)
    return {
        "balance": balance,
        "referralCode": account["referral_code"] if account else None,
        "status": account["status"] if account else "active",
    }


async def earn_points_for_order(
    db: Database, customer_user_id: str, order_id: str, order_total_minor: int,
    points_per_100: int,
) -> int:
    """Credit points for a completed order.  Points = floor(total / 100) * rate."""
    if points_per_100 <= 0 or order_total_minor <= 0:
        return 0
    account = await _ensure_account(db, customer_user_id)
    # Money is stored in paise: 100 rupees is 10,000 minor units.
    points = (order_total_minor // 10_000) * points_per_100
    if points <= 0:
        return 0
    now = utc_now_iso()
    await db.execute(
        "INSERT OR IGNORE INTO loyalty_transactions"
        " (id, loyalty_account_id, points, transaction_type, reference_id,"
        "  description, created_at)"
        " VALUES (?, ?, ?, 'earn_order', ?, ?, ?)",
        (
            new_id("ltx"),
            account["id"],
            points,
            order_id,
            "Points earned on order",
            now,
        ),
    )
    return points


async def resolve_checkout_redemption(
    db: Database, *, customer_user_id: str, points_to_redeem: int,
    points_value_minor: int, amount_needed_minor: int,
) -> dict[str, Any] | None:
    """What redeeming `points_to_redeem` loyalty points would cover.
    Returns None if nothing to redeem.  Raises for insufficient balance."""
    if points_to_redeem <= 0:
        return None
    if points_value_minor <= 0:
        raise ValidationAppError("Loyalty point value is not configured correctly.")
    balance = await get_balance(db, customer_user_id)
    if balance < points_to_redeem:
        raise ValidationAppError(
            f"You have {balance} loyalty points but tried to redeem {points_to_redeem}."
        )
    value_minor = points_to_redeem * points_value_minor
    applied = min(value_minor, max(amount_needed_minor, 0))
    # How many points are actually needed (may be less if the order is small).
    actual_points = min(
        points_to_redeem,
        (max(amount_needed_minor, 0) + points_value_minor - 1) // points_value_minor,
    )
    if actual_points == 0:
        return None
    return {
        "points_redeemed": actual_points,
        "applied_minor": applied,
        "balance_after": balance - actual_points,
    }


async def record_checkout_redemption(
    db: Database, customer_user_id: str, order_id: str, points: int,
) -> None:
    """Record the actual loyalty point spend for an order.  Called in the
    same batch as the order creation."""
    account = await db.fetch_one(
        "SELECT id FROM loyalty_accounts WHERE customer_user_id = ?",
        (customer_user_id,),
    )
    if account is None:
        return
    now = utc_now_iso()
    await db.execute(
        "INSERT INTO loyalty_transactions"
        " (id, loyalty_account_id, points, transaction_type, reference_id,"
        "  description, created_at)"
        " VALUES (?, ?, ?, 'redeem_checkout', ?, ?, ?)",
        (
            new_id("ltx"),
            account["id"],
            -points,
            order_id,
            "Points redeemed at checkout",
            now,
        ),
    )


async def apply_referral_code(
    db: Database, referred_user_id: str, referral_code: str,
) -> dict[str, Any] | None:
    """Record that a customer was referred.  Returns the referral or None
    if the code is invalid / self-referral / already used."""
    clean = referral_code.strip().upper()
    if not clean:
        return None
    referrer = await db.fetch_one(
        "SELECT * FROM loyalty_accounts WHERE referral_code = ? COLLATE NOCASE",
        (clean,),
    )
    if referrer is None:
        raise ValidationAppError("That referral code was not found.")
    if referrer["customer_user_id"] == referred_user_id:
        raise ValidationAppError("You cannot use your own referral code.")
    existing = await db.fetch_one(
        "SELECT id FROM referral_redemptions WHERE referred_user_id = ?",
        (referred_user_id,),
    )
    if existing is not None:
        raise ConflictError("You have already used a referral code.")
    prior_order = await db.fetch_one(
        "SELECT id FROM orders WHERE customer_user_id = ?"
        " AND order_status != 'cancelled' LIMIT 1",
        (referred_user_id,),
    )
    if prior_order is not None:
        raise ConflictError("A referral code must be applied before your first order.")
    now = utc_now_iso()
    redemption_id = new_id("ref")
    await db.execute(
        "INSERT INTO referral_redemptions"
        " (id, referral_code, referrer_account_id, referred_user_id, status, created_at)"
        " VALUES (?, ?, ?, ?, 'pending', ?)",
        (redemption_id, clean, referrer["id"], referred_user_id, now),
    )
    return {"id": redemption_id, "referralCode": clean}


async def complete_referral(
    db: Database, referred_user_id: str, order_id: str,
    referrer_points: int, referred_points: int,
) -> None:
    """Award both parties when the referred customer's first order completes."""
    redemption = await db.fetch_one(
        "SELECT * FROM referral_redemptions"
        " WHERE referred_user_id = ? AND status = 'pending'",
        (referred_user_id,),
    )
    if redemption is None:
        return
    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        (
            "UPDATE referral_redemptions"
            " SET status = 'completed', referred_order_id = ?,"
            "     referrer_points = ?, referred_points = ?, completed_at = ?"
            " WHERE id = ?",
            (order_id, referrer_points, referred_points, now, redemption["id"]),
        ),
    ]
    if referrer_points > 0:
        statements.append((
            "INSERT OR IGNORE INTO loyalty_transactions"
            " (id, loyalty_account_id, points, transaction_type, reference_id,"
            "  description, created_at)"
            " VALUES (?, ?, ?, 'referral_reward', ?, ?, ?)",
            (
                new_id("ltx"),
                redemption["referrer_account_id"],
                referrer_points,
                redemption["id"],
                "Referral reward — your friend placed their first order",
                now,
            ),
        ))
    if referred_points > 0:
        referred_account = await _ensure_account(db, referred_user_id)
        statements.append((
            "INSERT OR IGNORE INTO loyalty_transactions"
            " (id, loyalty_account_id, points, transaction_type, reference_id,"
            "  description, created_at)"
            " VALUES (?, ?, ?, 'referral_reward', ?, ?, ?)",
            (
                new_id("ltx"),
                referred_account["id"],
                referred_points,
                redemption["id"],
                "Welcome reward — thanks for being referred",
                now,
            ),
        ))
    await db.batch(statements)


async def admin_adjust_points(
    db: Database, actor: Principal, request_id: str,
    *, customer_user_id: str, points: int, reason: str,
) -> dict[str, Any]:
    """Manual admin credit/debit for goodwill gestures or corrections."""
    if points == 0:
        raise ValidationAppError("Points adjustment cannot be zero.")
    account = await _ensure_account(db, customer_user_id)
    current_balance = await get_balance(db, customer_user_id)
    if current_balance + points < 0:
        raise ConflictError("This adjustment would make the loyalty balance negative.")
    tx_type = "admin_credit" if points > 0 else "admin_debit"
    now = utc_now_iso()
    tx_id = new_id("ltx")
    await db.batch([
        (
            "INSERT INTO loyalty_transactions"
            " (id, loyalty_account_id, points, transaction_type, reference_id,"
            "  description, created_at, created_by)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (tx_id, account["id"], points, tx_type, None, reason[:300], now, actor.user_id),
        ),
        audit_statement(
            action=f"loyalty.{tx_type}",
            entity_type="loyalty_account",
            entity_id=account["id"],
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"points": points, "reason": reason[:300], "customerUserId": customer_user_id},
        ),
    ])
    balance = await get_balance(db, customer_user_id)
    return {"accountId": account["id"], "points": points, "balance": balance}


async def list_loyalty_accounts(
    db: Database, *, search: str | None = None, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    """Admin list of all loyalty accounts with derived balances."""
    clean_search = f"%{search.strip()}%" if search and search.strip() else None
    where = ""
    params: tuple[Any, ...] = ()
    if clean_search:
        where = (
            " JOIN users u ON u.id = la.customer_user_id"
            " WHERE u.email LIKE ? OR u.name LIKE ? OR la.referral_code LIKE ?"
        )
        params = (clean_search, clean_search, clean_search)

    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM loyalty_accounts la{where}", params,
    )
    rows = await db.fetch_all(
        f"""
        SELECT la.*,
               COALESCE((SELECT SUM(points) FROM loyalty_transactions
                         WHERE loyalty_account_id = la.id), 0) AS balance,
               u.email, u.name AS customer_name
        FROM loyalty_accounts la
        JOIN users u ON u.id = la.customer_user_id
        {where.replace('JOIN users u ON u.id = la.customer_user_id', '') if clean_search else ''}
        ORDER BY la.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "customerUserId": row["customer_user_id"],
                "customerEmail": row["email"],
                "customerName": row["customer_name"],
                "referralCode": row["referral_code"],
                "balance": max(int(row["balance"]), 0),
                "status": row["status"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def list_referrals(
    db: Database, *, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    """Admin list of all referral redemptions."""
    total_row = await db.fetch_one("SELECT COUNT(*) AS cnt FROM referral_redemptions")
    rows = await db.fetch_all(
        """
        SELECT rr.*,
               referrer_u.email AS referrer_email,
               referred_u.email AS referred_email
        FROM referral_redemptions rr
        JOIN loyalty_accounts la ON la.id = rr.referrer_account_id
        JOIN users referrer_u ON referrer_u.id = la.customer_user_id
        JOIN users referred_u ON referred_u.id = rr.referred_user_id
        ORDER BY rr.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "referralCode": row["referral_code"],
                "referrerEmail": row["referrer_email"],
                "referredEmail": row["referred_email"],
                "referrerPoints": row["referrer_points"],
                "referredPoints": row["referred_points"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "completedAt": row["completed_at"],
            }
            for row in rows
        ],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


async def get_transaction_history(
    db: Database, customer_user_id: str, *, limit: int = 50, offset: int = 0,
) -> dict[str, Any]:
    """Transaction history for a single customer."""
    account = await db.fetch_one(
        "SELECT id FROM loyalty_accounts WHERE customer_user_id = ?",
        (customer_user_id,),
    )
    if account is None:
        return {"items": [], "total": 0, "limit": limit, "offset": offset}
    total_row = await db.fetch_one(
        "SELECT COUNT(*) AS cnt FROM loyalty_transactions WHERE loyalty_account_id = ?",
        (account["id"],),
    )
    rows = await db.fetch_all(
        """
        SELECT * FROM loyalty_transactions
        WHERE loyalty_account_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        (account["id"], limit, offset),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "points": row["points"],
                "type": row["transaction_type"],
                "referenceId": row["reference_id"],
                "description": row["description"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }

"""Turning a proven mobile number into an account.

`services.otp` answers "does this caller hold this handset?". This module answers
"what does holding it entitle them to?" — find the account, create one, or attach
the number to an account that already exists. Keeping the two apart means the
same verified-phone primitive serves phone-first signup, email registration and
adding a number to a Google account, without any of them re-implementing OTP
rules.

The awkward part it exists to contain: `users.email` is NOT NULL and cannot be
relaxed on D1 (see migration 0016), so an account created from a phone alone gets
a reserved `@phone.invalid` placeholder. Everything that could leak that
placeholder to a human or a mail server goes through `services.contact`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from truegrit_api.domain.phone import mask_phone
from truegrit_api.errors import ConflictError, ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.contact import contactable_email, placeholder_email_for_phone
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_NAME_LENGTH = 120
# Shown until a phone-first customer tells us their name. Never blank: the
# storefront greets people by display_name and "Hello, " reads as a bug.
_FALLBACK_DISPLAY_NAME = "Organic member"


@dataclass(frozen=True)
class PhoneAccount:
    id: str
    display_name: str
    email: str | None
    phone_e164: str | None
    phone_verified: bool

    @property
    def is_phone_only(self) -> bool:
        return self.email is None


def account_payload(user: dict[str, Any]) -> dict[str, Any]:
    """The account shape the storefront consumes. `email` is null — not a
    placeholder — for phone-only accounts, so the UI renders the mobile instead
    of a fake address."""
    return {
        "id": user["id"],
        "displayName": user["display_name"],
        "email": contactable_email(user.get("email")),
        "phone": user.get("phone_e164"),
        "phoneVerified": user.get("phone_verified_at") is not None,
    }


async def find_user_by_phone(db: Database, phone_e164: str) -> dict[str, Any] | None:
    """The active customer holding `phone_e164`, if any.

    Matches only verified numbers: an unverified value is a claim, not a fact,
    and letting one resolve an account would let anybody type a stranger's number
    into their profile and hijack that stranger's phone login.
    """
    return await db.fetch_one(
        """
        SELECT id, display_name, email, phone_e164, phone_verified_at, user_type, status
        FROM users
        WHERE phone_e164 = ?
          AND phone_verified_at IS NOT NULL
          AND user_type = 'customer'
          AND status = 'active'
        """,
        (phone_e164,),
    )


async def _assert_phone_unclaimed(db: Database, phone_e164: str, *, excluding_user_id: str) -> None:
    existing = await db.fetch_one(
        "SELECT id FROM users WHERE phone_e164 = ? AND phone_verified_at IS NOT NULL AND id <> ?",
        (phone_e164, excluding_user_id),
    )
    if existing is not None:
        raise ConflictError(
            "That mobile number is already linked to another account. "
            "Sign in with it, or use a different number."
        )


async def create_phone_only_account(
    db: Database, *, phone_e164: str, display_name: str
) -> dict[str, Any]:
    """Create an account whose only identifier is a verified mobile."""
    name = (display_name or "").strip()[:_MAX_NAME_LENGTH]
    if not name:
        raise ValidationAppError("Enter your name.")

    existing = await db.fetch_one(
        "SELECT id FROM users WHERE phone_e164 = ? AND phone_verified_at IS NOT NULL",
        (phone_e164,),
    )
    if existing is not None:
        raise ConflictError("That mobile number is already registered.")

    user_id = new_id("usr")
    now = utc_now_iso()
    await db.batch(
        [
            (
                """
                INSERT INTO users (
                  id, email, display_name, user_type, status, email_verified_at,
                  phone_e164, phone_verified_at, created_at, updated_at, last_sign_in_at
                ) VALUES (?, ?, ?, 'customer', 'active', NULL, ?, ?, ?, ?, NULL)
                """,
                (user_id, placeholder_email_for_phone(phone_e164), name, phone_e164, now, now, now),
            ),
            (
                """
                INSERT INTO customer_profiles (user_id, phone_e164, marketing_email_consent,
                  created_at, updated_at)
                VALUES (?, ?, 0, ?, ?)
                """,
                (user_id, phone_e164, now, now),
            ),
        ]
    )
    log_event("info", "account_created_from_phone", user_id=user_id, to=mask_phone(phone_e164))
    return {
        "id": user_id,
        "display_name": name,
        "email": placeholder_email_for_phone(phone_e164),
        "phone_e164": phone_e164,
        "phone_verified_at": now,
    }


async def attach_verified_phone(db: Database, *, user_id: str, phone_e164: str) -> None:
    """Record `phone_e164` as this account's verified mobile.

    Also mirrors it onto `customer_profiles.phone_e164` so checkout can prefill a
    delivery number the customer has already proven they hold.
    """
    await _assert_phone_unclaimed(db, phone_e164, excluding_user_id=user_id)
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE users SET phone_e164 = ?, phone_verified_at = ?, updated_at = ?"
                " WHERE id = ?",
                (phone_e164, now, now, user_id),
            ),
            (
                "UPDATE customer_profiles SET phone_e164 = ?, updated_at = ? WHERE user_id = ?",
                (phone_e164, now, user_id),
            ),
        ]
    )
    log_event("info", "phone_attached", user_id=user_id, to=mask_phone(phone_e164))


async def get_account(db: Database, user_id: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        """
        SELECT id, display_name, email, phone_e164, phone_verified_at
        FROM users WHERE id = ? AND status = 'active'
        """,
        (user_id,),
    )

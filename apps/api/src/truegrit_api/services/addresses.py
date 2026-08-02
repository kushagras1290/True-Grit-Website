"""Customer delivery addresses (`addresses`, migration 0005) -- a saved
address a customer can reuse rather than retyping one at every checkout.

This table predates every feature in this session (0005_commerce.sql) but
was never wired to a repository/service/route -- ordinary checkout is
still one-off, taking an ad-hoc address on the request itself (see
`services.checkout.place_order`) and never persisting it. Subscriptions are
the first feature that genuinely needs a *reusable* address (a renewal
has no request to take one from), so this activates the table for exactly
that purpose, the same "extend the dormant table" precedent this session
already used for `reviews` and `promotions`. Ordinary checkout is
deliberately left untouched.
"""

from __future__ import annotations

from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.addresses import AddressRepository
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_REQUIRED: Final = ("recipient_name", "line1", "city", "state", "postal_code")
_MAX_LABEL: Final = 60
_MAX_LINE: Final = 200
_MAX_CITY_STATE: Final = 120
_MAX_POSTAL: Final = 20
_MAX_PHONE: Final = 20


def _clean(value: str | None, *, max_length: int) -> str:
    return (value or "").strip()[:max_length]


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "label": row["label"],
        "recipientName": row["recipient_name"],
        "phoneE164": row["phone_e164"],
        "line1": row["line1"],
        "line2": row["line2"],
        "city": row["city"],
        "state": row["state"],
        "postalCode": row["postal_code"],
        "countryCode": row["country_code"],
        "isDefaultDelivery": bool(row["is_default_delivery"]),
        "createdAt": row["created_at"],
    }


async def list_my_addresses(db: Database, customer: Principal) -> list[dict[str, Any]]:
    rows = await AddressRepository(db).list_for_customer(customer.user_id)
    return [_serialize(row) for row in rows]


async def create_address(
    db: Database,
    customer: Principal,
    *,
    label: str | None,
    recipient_name: str,
    phone_e164: str | None,
    line1: str,
    line2: str | None,
    city: str,
    state: str,
    postal_code: str,
    country_code: str | None,
) -> dict[str, Any]:
    fields = {
        "recipient_name": recipient_name,
        "line1": line1,
        "city": city,
        "state": state,
        "postal_code": postal_code,
    }
    for key in _REQUIRED:
        if not (fields[key] or "").strip():
            raise ValidationAppError(f"Address is missing {key.replace('_', ' ')}.")

    repository = AddressRepository(db)
    existing = await repository.list_for_customer(customer.user_id)
    now = utc_now_iso()
    address_id = new_id("addr")
    await db.execute(
        """
        INSERT INTO addresses (
          id, user_id, label, recipient_name, phone_e164, line1, line2, city, state,
          postal_code, country_code, is_default_delivery, is_default_billing,
          created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (
            address_id,
            customer.user_id,
            _clean(label, max_length=_MAX_LABEL) or None,
            _clean(recipient_name, max_length=150),
            _clean(phone_e164, max_length=_MAX_PHONE) or None,
            _clean(line1, max_length=_MAX_LINE),
            _clean(line2, max_length=_MAX_LINE) or None,
            _clean(city, max_length=_MAX_CITY_STATE),
            _clean(state, max_length=_MAX_CITY_STATE),
            _clean(postal_code, max_length=_MAX_POSTAL),
            _clean(country_code, max_length=2) or "IN",
            # A customer's first saved address is their default by
            # construction -- there is nothing else it could default over.
            1 if not existing else 0,
            now,
            now,
        ),
    )
    created = await repository.get_owned(address_id, customer.user_id)
    assert created is not None
    return _serialize(created)


async def archive_address(db: Database, customer: Principal, address_id: str) -> None:
    repository = AddressRepository(db)
    current = await repository.get_owned(address_id, customer.user_id)
    if current is None:
        raise NotFoundError("Address not found.")
    in_use = await db.fetch_one(
        "SELECT id FROM subscriptions WHERE address_id = ? AND status != 'cancelled'",
        (address_id,),
    )
    if in_use is not None:
        raise ValidationAppError(
            "This address is in use by an active subscription. Pause or cancel it first,"
            " or update the subscription to a different address."
        )
    await db.execute(
        "UPDATE addresses SET archived_at = ?, updated_at = ? WHERE id = ?",
        (utc_now_iso(), utc_now_iso(), address_id),
    )

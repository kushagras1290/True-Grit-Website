"""Stored INR-to-display-currency conversion values.

Only presentation uses these rates. Catalogue, checkout and ledger amounts stay
in their original currency, which makes an operator rate change reversible and
prevents historical orders from changing value.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

RATE_SCALE: Final = 1_000_000
MAX_RATE: Final = Decimal("1000000")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")


def _response(row: dict[str, Any]) -> dict[str, Any]:
    rate = (Decimal(int(row["rate_micros"])) / RATE_SCALE).normalize()
    return {
        "currencyCode": str(row["currency_code"]),
        "locale": str(row["locale"]),
        "ratePerInr": format(rate, "f"),
        "active": bool(row["active"]),
        "updatedAt": str(row["updated_at"]),
    }


async def list_rates(db: Database, *, active_only: bool = False) -> list[dict[str, Any]]:
    where = "WHERE active = 1" if active_only else ""
    rows = await db.fetch_all(
        "SELECT currency_code, locale, rate_micros, active, updated_at"
        f" FROM currency_exchange_rates {where}"
        " ORDER BY CASE WHEN currency_code = 'INR' THEN 0 ELSE 1 END, currency_code"
    )
    return [_response(row) for row in rows]


def _rate_micros(value: Decimal | str | float) -> int:
    try:
        rate = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValidationAppError("Enter a valid conversion value.") from exc
    if not rate.is_finite() or rate <= 0 or rate > MAX_RATE:
        raise ValidationAppError(
            "A conversion value must be greater than zero and no more than 1,000,000."
        )
    micros = int((rate * RATE_SCALE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if micros <= 0:
        raise ValidationAppError("That conversion value is too small to store safely.")
    return micros


async def save_rate(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    currency_code: str,
    locale: str,
    rate_per_inr: Decimal | str | float,
    active: bool,
) -> dict[str, Any]:
    code = currency_code.strip().upper()
    locale = locale.strip()
    if not _CURRENCY_PATTERN.fullmatch(code):
        raise ValidationAppError("Use a three-letter ISO currency code, for example USD.")
    if not _LOCALE_PATTERN.fullmatch(locale):
        raise ValidationAppError("Use a valid formatting locale, for example en-US.")
    micros = _rate_micros(rate_per_inr)
    if code == "INR" and (not active or micros != RATE_SCALE):
        raise ValidationAppError("INR is the base currency and must remain active at 1.")
    before = await db.fetch_one(
        "SELECT currency_code, locale, rate_micros, active, updated_at"
        " FROM currency_exchange_rates WHERE currency_code = ?",
        (code,),
    )
    now = utc_now_iso()
    after = {
        "currencyCode": code,
        "locale": locale,
        "ratePerInr": format((Decimal(micros) / RATE_SCALE).normalize(), "f"),
        "active": active,
    }
    await db.batch(
        [
            (
                "INSERT INTO currency_exchange_rates"
                " (currency_code, locale, rate_micros, active, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(currency_code) DO UPDATE SET locale = excluded.locale,"
                " rate_micros = excluded.rate_micros, active = excluded.active,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (code, locale, micros, int(active), now, actor.user_id),
            ),
            audit_statement(
                action="currency_rate.updated" if before else "currency_rate.created",
                entity_type="currency_exchange_rate",
                entity_id=code,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before=_response(before) if before else None,
                after=after,
            ),
        ]
    )
    row = await db.fetch_one(
        "SELECT currency_code, locale, rate_micros, active, updated_at"
        " FROM currency_exchange_rates WHERE currency_code = ?",
        (code,),
    )
    assert row is not None
    return _response(row)

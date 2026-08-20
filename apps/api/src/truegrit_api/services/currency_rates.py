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
from truegrit_api.config import Settings
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform import google_sheets
from truegrit_api.platform.database import Database
from truegrit_api.platform.http import HttpError, get_json_async
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

RATE_SCALE: Final = 1_000_000
MAX_RATE: Final = Decimal("1000000")
_CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")
_LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")

# Free, keyless, INR directly as base -- `rates.USD` maps straight onto
# `rate_micros / RATE_SCALE`, no conversion hop. Updates daily on their side,
# matching the once-a-day cron this feeds.
LIVE_RATE_SOURCE_URL: Final = "https://open.er-api.com/v6/latest/INR"

_SHEET_HEADER_RANGE: Final = "A1:D4"
_SHEET_DATA_RANGE: Final = "A5:D500"  # generous ceiling; the table is a few dozen rows


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


async def refresh_live_rates(
    db: Database, request_id: str, *, actor: Principal | None = None
) -> dict[str, Any]:
    """Refresh `rate_micros` for every currency already in the table from
    :data:`LIVE_RATE_SOURCE_URL`. Never creates a new currency row -- a new
    row also needs a sensible `locale`, which the source doesn't provide.
    INR is never touched: it is the fixed base, always 1,000,000 micros.

    `actor` is `None` when called from the nightly cron (`worker.py`), which
    stores `updated_by = NULL` -- the same nullable-FK convention this table
    already uses to mark a system update distinctly from a real admin's user
    id. The admin-triggered "Refresh now" button passes a real actor.
    """
    try:
        result = await get_json_async(LIVE_RATE_SOURCE_URL)
    except HttpError as exc:
        raise ValidationAppError(f"Could not fetch live currency rates: {exc}") from exc
    rates = (result or {}).get("rates")
    if not isinstance(rates, dict):
        raise ValidationAppError("The live rate source returned an unexpected response.")

    existing_rows = await db.fetch_all("SELECT currency_code FROM currency_exchange_rates")
    known_codes = {str(row["currency_code"]) for row in existing_rows}

    now = utc_now_iso()
    updated: list[str] = []
    statements: list[tuple[str, Any]] = []
    for raw_code, raw_rate in rates.items():
        code = str(raw_code).upper()
        if code == "INR" or code not in known_codes:
            continue
        try:
            micros = _rate_micros(raw_rate)
        except ValidationAppError:
            continue
        statements.append(
            (
                "UPDATE currency_exchange_rates"
                " SET rate_micros = ?, updated_at = ?, updated_by = ? WHERE currency_code = ?",
                (micros, now, actor.user_id if actor else None, code),
            )
        )
        updated.append(code)

    if statements:
        statements.append(
            audit_statement(
                action="currency_rates.live_synced",
                entity_type="currency_exchange_rate",
                entity_id="bulk",
                actor_id=actor.user_id if actor else None,
                request_id=request_id,
                created_at=now,
                after={"updatedCount": len(updated), "currencies": updated},
            )
        )
        await db.batch(statements)
    return {"updatedCount": len(updated), "currencies": updated}


async def push_to_sheet(db: Database, settings: Settings) -> dict[str, Any]:
    """Write the current table state into the configured Google Sheet.
    Admin-triggered only -- the nightly live-rate cron never touches the
    sheet (see `sync_from_sheet`), so a manual tuning session in progress can
    never be silently overwritten by an automatic write partway through."""
    rows = await list_rates(db)
    header = [
        ["Source:", LIVE_RATE_SOURCE_URL, "", ""],
        ["Last pushed:", utc_now_iso(), "", ""],
        ["", "", "", ""],
        ["Currency Code", "Locale", "Rate per INR", "Active"],
    ]
    data = [
        [
            row["currencyCode"],
            row["locale"],
            row["ratePerInr"],
            "TRUE" if row["active"] else "FALSE",
        ]
        for row in rows
    ]
    await google_sheets.write_values(settings, cell_range=_SHEET_HEADER_RANGE, values=header)
    await google_sheets.write_values(
        settings, cell_range=f"A5:D{4 + max(len(data), 1)}", values=data
    )
    return {"pushedCount": len(data)}


async def sync_from_sheet(
    db: Database, actor: Principal, request_id: str, settings: Settings
) -> dict[str, Any]:
    """Read the sheet from row 5 and apply matching currency rows back into
    the table. Never creates a new currency row (same conservative rule as
    `refresh_live_rates`) and never touches INR; skips blank or malformed
    rows without failing the rest of the sync."""
    rows = await google_sheets.read_values(settings, cell_range=_SHEET_DATA_RANGE)
    existing_rows = await db.fetch_all("SELECT currency_code FROM currency_exchange_rates")
    known_codes = {str(row["currency_code"]) for row in existing_rows}

    now = utc_now_iso()
    updated: list[str] = []
    skipped: list[str] = []
    statements: list[tuple[str, Any]] = []
    for row in rows:
        code = row[0].strip().upper() if len(row) >= 1 and row[0] else ""
        if not code or len(row) < 3:
            continue
        if code == "INR" or code not in known_codes:
            skipped.append(code)
            continue
        try:
            micros = _rate_micros(row[2])
        except ValidationAppError:
            skipped.append(code)
            continue
        active = row[3].strip().upper() not in {"FALSE", "0", "NO"} if len(row) >= 4 else True
        statements.append(
            (
                "UPDATE currency_exchange_rates"
                " SET rate_micros = ?, active = ?, updated_at = ?, updated_by = ?"
                " WHERE currency_code = ?",
                (micros, int(active), now, actor.user_id, code),
            )
        )
        updated.append(code)

    if statements:
        statements.append(
            audit_statement(
                action="currency_rates.sheet_synced",
                entity_type="currency_exchange_rate",
                entity_id="bulk",
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"updatedCount": len(updated), "currencies": updated, "skipped": skipped},
            )
        )
        await db.batch(statements)
    return {"updatedCount": len(updated), "skippedCount": len(skipped)}

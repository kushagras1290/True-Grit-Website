"""Country pricing brackets: a convenience manager for a batch of
global-scope, no-product, no-category `price_adjustments` rows.

A bracket ("Tier 1" at +100%, say) is not a second pricing engine -- it is a
named percent plus a set of countries, and assigning a country to it writes
exactly the kind of row `services/price_adjustments.py::save_rule` already
knows how to resolve (the existing "scope-only" tier: least specific, so a
manual per-product/per-category rule added later on the Sale & Discounts page
still overrides a bracket for that one case). Checkout and the storefront
read `price_adjustments` exactly as before; nothing here changes what a
customer is charged beyond writing to that same table.

`price_adjustments.bracket_id` tags which rows are bracket-managed, which is
what lets a bracket be edited or deleted without guessing which rows belong
to it, and what stops a bracket assignment and a hand-written global country
rule from silently fighting over the same country.
"""

from __future__ import annotations

import re
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

MIN_PERCENT: Final = -90
MAX_PERCENT: Final = 500
_COUNTRY_CODE_PATTERN: Final = re.compile(r"^[A-Za-z]{2}$")
# "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not real countries --
# same exclusion `price_adjustments.py`/`homepage_geo.py` already apply.
_NOT_REAL_COUNTRIES: Final = frozenset({"XX", "T1"})


def _validate_country_code(code: str) -> str:
    candidate = code.strip().upper()
    if not _COUNTRY_CODE_PATTERN.match(candidate) or candidate in _NOT_REAL_COUNTRIES:
        raise ValidationAppError("Enter a real two-letter country code, such as US.")
    return candidate


def _validate_percent(percent: int) -> int:
    if not MIN_PERCENT <= percent <= MAX_PERCENT:
        raise ValidationAppError(
            f"A bracket percent must be between {MIN_PERCENT}% and {MAX_PERCENT}%."
        )
    return percent


async def list_brackets(db: Database) -> list[dict[str, Any]]:
    brackets = await db.fetch_all(
        "SELECT id, label, percent, sort_order, updated_at FROM price_tier_brackets"
        " ORDER BY sort_order, label"
    )
    countries = await db.fetch_all(
        "SELECT country_code, bracket_id FROM price_tier_countries ORDER BY country_code"
    )
    by_bracket: dict[str, list[str]] = {}
    for row in countries:
        by_bracket.setdefault(str(row["bracket_id"]), []).append(str(row["country_code"]))
    return [
        {
            "id": row["id"],
            "label": row["label"],
            "percent": int(row["percent"]),
            "sortOrder": int(row["sort_order"]),
            "updatedAt": row["updated_at"],
            "countries": by_bracket.get(str(row["id"]), []),
        }
        for row in brackets
    ]


async def create_bracket(
    db: Database, actor: Principal, request_id: str, *, label: str, percent: int
) -> dict[str, Any]:
    clean_label = label.strip()
    if not clean_label:
        raise ValidationAppError("Give the bracket a name.")
    resolved_percent = _validate_percent(percent)

    row = await db.fetch_one("SELECT MAX(sort_order) AS max_order FROM price_tier_brackets")
    next_order = (int(row["max_order"]) + 1) if row and row["max_order"] is not None else 0

    bracket_id = new_id("ptier")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO price_tier_brackets"
                " (id, label, percent, sort_order, created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    bracket_id,
                    clean_label,
                    resolved_percent,
                    next_order,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="price_tier.bracket_created",
                entity_type="price_tier_bracket",
                entity_id=bracket_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"label": clean_label, "percent": resolved_percent},
            ),
        ]
    )
    return {"id": bracket_id, "label": clean_label, "percent": resolved_percent, "countries": []}


async def update_bracket(
    db: Database, actor: Principal, request_id: str, bracket_id: str, *, label: str, percent: int
) -> dict[str, Any]:
    existing = await db.fetch_one(
        "SELECT id, label, percent FROM price_tier_brackets WHERE id = ?", (bracket_id,)
    )
    if existing is None:
        raise NotFoundError("That pricing bracket could not be found.")
    clean_label = label.strip()
    if not clean_label:
        raise ValidationAppError("Give the bracket a name.")
    resolved_percent = _validate_percent(percent)

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = [
        (
            "UPDATE price_tier_brackets SET label = ?, percent = ?, updated_at = ?, updated_by = ?"
            " WHERE id = ?",
            (clean_label, resolved_percent, now, actor.user_id, bracket_id),
        ),
        # Every country already in this bracket feels the new percent
        # immediately -- "reduce this bracket by 25%" is one edit, not one
        # edit per country.
        (
            "UPDATE price_adjustments SET percent = ?, updated_at = ?, updated_by = ?"
            " WHERE bracket_id = ?",
            (resolved_percent, now, actor.user_id, bracket_id),
        ),
        audit_statement(
            action="price_tier.bracket_updated",
            entity_type="price_tier_bracket",
            entity_id=bracket_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"label": existing["label"], "percent": existing["percent"]},
            after={"label": clean_label, "percent": resolved_percent},
        ),
    ]
    await db.batch(statements)
    return {"id": bracket_id, "label": clean_label, "percent": resolved_percent}


async def delete_bracket(db: Database, actor: Principal, request_id: str, bracket_id: str) -> None:
    existing = await db.fetch_one(
        "SELECT label FROM price_tier_brackets WHERE id = ?", (bracket_id,)
    )
    if existing is None:
        raise NotFoundError("That pricing bracket could not be found.")
    now = utc_now_iso()
    await db.batch(
        [
            # ON DELETE CASCADE on both price_tier_countries.bracket_id and
            # price_adjustments.bracket_id removes every country assignment
            # and every bracket-driven price rule together -- no orphaned,
            # untagged, still-active global rule left behind.
            ("DELETE FROM price_tier_brackets WHERE id = ?", (bracket_id,)),
            audit_statement(
                action="price_tier.bracket_deleted",
                entity_type="price_tier_bracket",
                entity_id=bracket_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"label": existing["label"]},
            ),
        ]
    )


async def assign_country(
    db: Database, actor: Principal, request_id: str, *, country_code: str, bracket_id: str
) -> dict[str, Any]:
    code = _validate_country_code(country_code)
    bracket = await db.fetch_one(
        "SELECT id, percent FROM price_tier_brackets WHERE id = ?", (bracket_id,)
    )
    if bracket is None:
        raise NotFoundError("That pricing bracket could not be found.")

    existing_rule = await db.fetch_one(
        "SELECT id, bracket_id FROM price_adjustments"
        " WHERE scope = ? AND product_id IS NULL AND category_id IS NULL",
        (code,),
    )
    if existing_rule is not None and existing_rule["bracket_id"] is None:
        raise ConflictError(
            "This country already has a manual global pricing rule on the Sale & Discounts"
            " page. Remove it there before assigning a bracket."
        )

    now = utc_now_iso()
    percent = int(bracket["percent"])
    statements: list[tuple[str, Any]] = [
        (
            "INSERT INTO price_tier_countries (country_code, bracket_id, assigned_at, assigned_by)"
            " VALUES (?, ?, ?, ?)"
            " ON CONFLICT(country_code) DO UPDATE SET bracket_id = excluded.bracket_id,"
            " assigned_at = excluded.assigned_at, assigned_by = excluded.assigned_by",
            (code, bracket_id, now, actor.user_id),
        ),
    ]
    if existing_rule is not None:
        statements.append(
            (
                "UPDATE price_adjustments SET bracket_id = ?, percent = ?, updated_at = ?,"
                " updated_by = ? WHERE id = ?",
                (bracket_id, percent, now, actor.user_id, existing_rule["id"]),
            )
        )
    else:
        statements.append(
            (
                "INSERT INTO price_adjustments"
                " (id, scope, product_id, category_id, percent, active, bracket_id,"
                "  created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, NULL, NULL, ?, 1, ?, ?, ?, ?, ?)",
                (new_id("padj"), code, percent, bracket_id, now, actor.user_id, now, actor.user_id),
            )
        )
    statements.append(
        audit_statement(
            action="price_tier.country_assigned",
            entity_type="price_tier_country",
            entity_id=code,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"countryCode": code, "bracketId": bracket_id, "percent": percent},
        )
    )
    await db.batch(statements)
    return {"countryCode": code, "bracketId": bracket_id}


async def unassign_country(
    db: Database, actor: Principal, request_id: str, *, country_code: str
) -> None:
    code = _validate_country_code(country_code)
    existing = await db.fetch_one(
        "SELECT bracket_id FROM price_tier_countries WHERE country_code = ?", (code,)
    )
    if existing is None:
        raise NotFoundError("That country is not assigned to a pricing bracket.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM price_tier_countries WHERE country_code = ?", (code,)),
            (
                "DELETE FROM price_adjustments"
                " WHERE scope = ? AND bracket_id IS NOT NULL"
                " AND product_id IS NULL AND category_id IS NULL",
                (code,),
            ),
            audit_statement(
                action="price_tier.country_unassigned",
                entity_type="price_tier_country",
                entity_id=code,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"bracketId": existing["bracket_id"]},
            ),
        ]
    )

"""The announcement banner, site-wide or per visitor country (migration 0053).

One row is `'global'`, the shipped default shown to everyone; any other row is
an ISO-3166 alpha-2 country code, shown instead of the global banner to
visitors Cloudflare resolves to that country -- the same signal
`resolveCountry()` already uses for currency, catalogue release, and the
theme/effects overrides in `services/appearance.py`.

A country row is a full replacement, not a patch: unlike theme colours, a
banner either is or is not shown, with one message and one destination, so
there is nothing sensible to merge key by key the way colours are. Resolution
(`resolve_announcement`) is therefore just "the visitor's country row if it is
active, else the global row if it is active, else nothing" -- see its
docstring for the exact order.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

GLOBAL_SCOPE: Final = "global"
MAX_MESSAGE_LENGTH: Final = 220
MAX_PATH_LENGTH: Final = 200
# Real-world markets, not a limit anyone should ever approach in practice --
# see the identical reasoning on `MAX_COUNTRY_SCOPES` in `services/appearance.py`.
MAX_COUNTRY_SCOPES: Final = 60

_COUNTRY_CODE_PATTERN: Final = re.compile(r"^[A-Za-z]{2}$")
# "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not real countries --
# see `resolveCountry()` in the storefront. A banner saved under one would
# never resolve for an actual visitor.
_NOT_REAL_COUNTRIES: Final = frozenset({"XX", "T1"})


def validate_country_scope(scope: str) -> str:
    """`'global'` or an ISO-3166 alpha-2 code, uppercase. Anything else is refused."""
    candidate = scope.strip()
    if candidate == GLOBAL_SCOPE:
        return GLOBAL_SCOPE
    code = candidate.upper()
    if not _COUNTRY_CODE_PATTERN.match(code) or code in _NOT_REAL_COUNTRIES:
        raise ValidationAppError(
            "An announcement scope must be 'global' or a real two-letter country code, such as IN."
        )
    return code


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "scope": row["country"],
        "active": bool(row["active"]),
        "message": row["message"],
        "path": row["destination_path"] or "",
        "updatedAt": row["updated_at"],
    }


async def list_announcements(db: Database) -> list[dict[str, Any]]:
    """Every stored scope, for the admin console's picker. The global row
    always exists (migration 0053's default), so this is never empty."""
    rows = await db.fetch_all(
        "SELECT country, active, message, destination_path, updated_at FROM announcements"
        " ORDER BY (country != 'global'), country"
    )
    return [_row_to_dict(row) for row in rows]


async def resolve_announcement(
    db: Database, country: str | None, *, locale: str | None = None
) -> dict[str, str] | None:
    """What the storefront should show, for one visitor.

    Priority: the visitor's own country row, if one exists and is active; else
    the global row, if it is active; else nothing. A country row that exists
    but is switched off is a deliberate "no banner here" and does *not* fall
    back to the global message -- an owner silencing a market-specific banner
    should not have the general one reappear underneath it unannounced.
    """
    code = country.strip().upper() if country else None
    if code and _COUNTRY_CODE_PATTERN.match(code):
        country_row = await db.fetch_one(
            "SELECT id, active, message, destination_path FROM announcements WHERE country = ?",
            (code,),
        )
        if country_row is not None:
            if not bool(country_row["active"]):
                return None
            from truegrit_api.services.translation_hub import override_map

            translated = await override_map(db, "announcement", country_row["id"], locale or "")
            return {
                "message": translated.get("message") or country_row["message"],
                "path": country_row["destination_path"] or "",
            }
    global_row = await db.fetch_one(
        "SELECT id, active, message, destination_path FROM announcements WHERE country = 'global'"
    )
    if global_row is None or not bool(global_row["active"]):
        return None
    from truegrit_api.services.translation_hub import override_map

    translated = await override_map(db, "announcement", global_row["id"], locale or "")
    return {
        "message": translated.get("message") or global_row["message"],
        "path": global_row["destination_path"] or "",
    }


async def save_announcement(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    scope: str,
    active: bool,
    message: str,
    path: str,
) -> None:
    resolved = validate_country_scope(scope)
    message = message.strip()
    if not message:
        raise ValidationAppError("The announcement needs a message.")
    if len(message) > MAX_MESSAGE_LENGTH:
        raise ValidationAppError(
            f"The announcement message must be {MAX_MESSAGE_LENGTH} characters or fewer."
        )
    path = path.strip()
    if len(path) > MAX_PATH_LENGTH:
        raise ValidationAppError(
            f"The announcement link must be {MAX_PATH_LENGTH} characters or fewer."
        )

    if resolved != GLOBAL_SCOPE:
        existing = await db.fetch_one(
            "SELECT 1 AS ok FROM announcements WHERE country = ?", (resolved,)
        )
        if existing is None:
            count = await db.fetch_one(
                "SELECT COUNT(*) AS total FROM announcements WHERE country != 'global'"
            )
            if count and int(count["total"]) >= MAX_COUNTRY_SCOPES:
                raise ValidationAppError(
                    f"At most {MAX_COUNTRY_SCOPES} countries can carry their own announcement."
                    " Remove one before adding another."
                )

    now = utc_now_iso()
    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO announcements"
            " (id, country, message, destination_path, active, created_at, created_by, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(country) DO UPDATE SET"
            "  message = excluded.message, destination_path = excluded.destination_path,"
            "  active = excluded.active, updated_at = excluded.updated_at",
            (
                new_id("ann"),
                resolved,
                message,
                path or None,
                int(active),
                now,
                actor.user_id,
                now,
            ),
        ),
        audit_statement(
            action="settings.announcement_updated",
            entity_type="announcement",
            entity_id=resolved,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"scope": resolved, "active": active, "message": message, "path": path},
        ),
    ]
    await db.batch(statements)


async def delete_country_announcement(
    db: Database, actor: Principal, request_id: str, *, scope: str
) -> None:
    resolved = validate_country_scope(scope)
    if resolved == GLOBAL_SCOPE:
        raise ValidationAppError(
            "The site-wide announcement cannot be deleted. Turn it off instead."
        )
    existing = await db.fetch_one(
        "SELECT 1 AS ok FROM announcements WHERE country = ?", (resolved,)
    )
    if existing is None:
        raise NotFoundError(f"No announcement is saved for {resolved}.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM announcements WHERE country = ?", (resolved,)),
            audit_statement(
                action="settings.announcement_deleted",
                entity_type="announcement",
                entity_id=resolved,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"scope": resolved},
            ),
        ]
    )

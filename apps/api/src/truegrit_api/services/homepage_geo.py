"""Per-country visibility overrides for homepage sections (migration 0053).

The homepage's own `enabled` flag on each block (edited from Homepage
Settings, see `api/admin.py`'s `/homepage/sections` routes) is the global
default a visitor gets. This module adds one narrower opinion on top: "for
visitors in this country, force this one section on or off", without touching
the block's stored default or its content.

Deliberately visibility-only, not reordering or content: a section that moves
to a different position per visitor is a much larger claim on the page's
layout than one that is simply present or absent, and presence/absence covers
the real cases this exists for (a festival section shown only in its home
market, a section retired everywhere except where it still applies).
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

_COUNTRY_CODE_PATTERN: Final = re.compile(r"^[A-Za-z]{2}$")
# "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not real countries --
# see `resolveCountry()` in the storefront.
_NOT_REAL_COUNTRIES: Final = frozenset({"XX", "T1"})
# A handful of sections on a handful of markets -- see the identical reasoning
# on `MAX_COUNTRY_SCOPES` in `services/appearance.py`.
MAX_OVERRIDES_PER_COUNTRY: Final = 40


def validate_country(code: str) -> str:
    candidate = code.strip().upper()
    if not _COUNTRY_CODE_PATTERN.match(candidate) or candidate in _NOT_REAL_COUNTRIES:
        raise ValidationAppError("Enter a real two-letter country code, such as IN.")
    return candidate


async def list_country_overrides(db: Database) -> dict[str, dict[str, bool]]:
    """Every stored override, grouped by country, for the admin console."""
    rows = await db.fetch_all(
        "SELECT country, block_id, enabled FROM homepage_country_overrides"
        " ORDER BY country, block_id"
    )
    result: dict[str, dict[str, bool]] = {}
    for row in rows:
        result.setdefault(row["country"], {})[row["block_id"]] = bool(row["enabled"])
    return result


async def set_country_override(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    country: str,
    block_id: str,
    enabled: bool | None,
) -> None:
    """`enabled=None` clears the override, so the section falls back to
    whatever Homepage Settings' own tickbox says for every other visitor."""
    resolved = validate_country(country)
    if not block_id.strip():
        raise ValidationAppError("A section id is required.")
    now = utc_now_iso()

    if enabled is None:
        await db.batch(
            [
                (
                    "DELETE FROM homepage_country_overrides WHERE country = ? AND block_id = ?",
                    (resolved, block_id),
                ),
                audit_statement(
                    action="settings.homepage_override_cleared",
                    entity_type="homepage_override",
                    entity_id=f"{resolved}:{block_id}",
                    actor_id=actor.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"country": resolved, "blockId": block_id},
                ),
            ]
        )
        return

    existing = await db.fetch_one(
        "SELECT 1 AS ok FROM homepage_country_overrides WHERE country = ? AND block_id = ?",
        (resolved, block_id),
    )
    if existing is None:
        count = await db.fetch_one(
            "SELECT COUNT(*) AS total FROM homepage_country_overrides WHERE country = ?",
            (resolved,),
        )
        if count and int(count["total"]) >= MAX_OVERRIDES_PER_COUNTRY:
            raise ValidationAppError(
                f"At most {MAX_OVERRIDES_PER_COUNTRY} section overrides are allowed per country."
            )

    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO homepage_country_overrides"
            " (country, block_id, enabled, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT(country, block_id) DO UPDATE SET"
            "  enabled = excluded.enabled, updated_at = excluded.updated_at,"
            "  updated_by = excluded.updated_by",
            (resolved, block_id, int(enabled), now, actor.user_id),
        ),
        audit_statement(
            action="settings.homepage_override_updated",
            entity_type="homepage_override",
            entity_id=f"{resolved}:{block_id}",
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"country": resolved, "blockId": block_id, "enabled": enabled},
        ),
    ]
    await db.batch(statements)


async def resolve_public_home(db: Database, country: str | None) -> dict[str, Any] | None:
    """The homepage, with this visitor's country overrides already applied.

    Reads the *unfiltered* block list (including sections switched off by
    default) so a country override can force one back on, then applies each
    block's effective `enabled` -- the country override if one exists for that
    block, else the block's own stored flag -- before dropping disabled blocks.
    This mirrors `PageRepository.get_published_by_slug`'s shape exactly; it is
    a separate query rather than a shared one because that method's filtering
    happens before any override could ever see the blocks it discarded.
    """
    page = await db.fetch_one(
        """
        SELECT p.id, p.slug, p.title, p.seo_title, p.seo_description, p.seo_keywords,
               p.indexing_policy, v.content_json
        FROM pages p
        JOIN page_versions v ON v.id = p.published_version_id
        WHERE p.slug = 'home' AND p.status = 'published'
        """
    )
    if page is None:
        return None

    content = json.loads(page["content_json"])
    blocks = content.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []

    overrides: dict[str, bool] = {}
    code = country.strip().upper() if country else None
    if code and _COUNTRY_CODE_PATTERN.match(code):
        rows = await db.fetch_all(
            "SELECT block_id, enabled FROM homepage_country_overrides WHERE country = ?",
            (code,),
        )
        overrides = {row["block_id"]: bool(row["enabled"]) for row in rows}

    visible = [
        block
        for block in blocks
        if isinstance(block, dict) and overrides.get(block.get("id"), block.get("enabled", True))
    ]

    return {
        "id": page["id"],
        "slug": page["slug"],
        "title": page["title"],
        "blocks": visible,
        "seo": {
            "title": page["seo_title"] or page["title"],
            "description": page["seo_description"] or "",
            "keywords": page["seo_keywords"],
            "canonical_path": "/",
            "indexing": page["indexing_policy"],
        },
    }

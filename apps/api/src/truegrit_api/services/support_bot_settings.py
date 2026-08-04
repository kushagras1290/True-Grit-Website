"""On/off switches and answer-tuning knobs for each support bot, shared by
`services.support_bot` (admin) and `services.support_bot_public`
(storefront).

Stored in the existing `app_settings` key/value table (migration 0034),
exactly the same pattern `services.discussions`' min-account-age setting
already uses -- no new table needed for a handful of scalars. Both bots
default to enabled; an admin with `support_bot.manage` can turn either off
(e.g. while a Workers AI incident is ongoing, or the knowledge base is being
reworked) without a deploy.

The two tuning values are here rather than as module constants for the same
reason: they change how every answer is built, and an operator tuning answer
quality should not need a deploy to do it. Both are clamped to a sane range
on the way in, so a bad value cannot make the prompt unbounded.
"""

from __future__ import annotations

import re
from typing import Any, Literal

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

BotScope = Literal["admin", "storefront"]
TuningKey = Literal["historyTurns", "knowledgeSnippets", "searchResults", "policyChars"]

_SETTING_KEYS: dict[BotScope, str] = {
    "admin": "support_bot.admin_enabled",
    "storefront": "support_bot.storefront_enabled",
}
_DEFAULT_ENABLED = True

# key -> (app_settings key, default, minimum, maximum)
_TUNING: dict[TuningKey, tuple[str, int, int, int]] = {
    # How many prior turns the client may replay into the prompt. Higher keeps
    # more context, at a proportional cost in tokens and CPU per answer.
    "historyTurns": ("support_bot.history_turns", 10, 0, 40),
    # How many knowledge-base entries are embedded as reference material.
    "knowledgeSnippets": ("support_bot.knowledge_snippets", 6, 1, 30),
    # How many catalogue/content hits the storefront bot's search tools return
    # per call. More gives the model more to ground an answer in; too many and
    # the results crowd out the rest of the prompt.
    "searchResults": ("support_bot.search_results", 5, 1, 20),
    # How much of a policy page's text `read_policy` hands to the model. Long
    # enough to carry the specifics a customer asked about, short enough that
    # one page cannot swallow the whole prompt.
    "policyChars": ("support_bot.policy_chars", 4000, 500, 12000),
}

_POLICY_PAGES_KEY = "support_bot.policy_pages"
_DEFAULT_POLICY_PAGES = ("returns", "delivery", "help", "terms", "privacy", "standards", "about")
_MAX_POLICY_PAGES = 20
# Slugs only. These are looked up as published CMS pages and offered to the
# model as an enum, so anything that is not slug-shaped is dropped rather than
# trusted.
_SLUG_PATTERN = re.compile(r"^[a-z0-9-]{1,80}$")


async def get_policy_pages(db: Database) -> tuple[str, ...]:
    """Which published pages `read_policy` may quote, in operator-chosen order."""
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (_POLICY_PAGES_KEY,))
    if row is None:
        return _DEFAULT_POLICY_PAGES
    slugs = _clean_policy_pages(str(row["value"] or ""))
    return slugs or _DEFAULT_POLICY_PAGES


def _clean_policy_pages(raw: str) -> tuple[str, ...]:
    candidates = [part.strip().lower() for part in raw.replace(",", " ").split()]
    kept = [slug for slug in dict.fromkeys(candidates) if _SLUG_PATTERN.match(slug)]
    return tuple(kept[:_MAX_POLICY_PAGES])


async def set_policy_pages(
    db: Database, actor: Principal, request_id: str, raw: str
) -> dict[str, Any]:
    slugs = _clean_policy_pages(raw)
    if not slugs:
        raise ValidationAppError(
            "List at least one page slug, e.g. 'returns delivery help'. Slugs use lowercase"
            " letters, numbers and hyphens."
        )
    now = utc_now_iso()
    value = " ".join(slugs)
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (_POLICY_PAGES_KEY, value, now, actor.user_id),
            ),
            audit_statement(
                action="support_bot.policy_pages_changed",
                entity_type="app_setting",
                entity_id=_POLICY_PAGES_KEY,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"pages": value},
            ),
        ]
    )
    return {"policyPages": value}


async def get_tuning(db: Database, key: TuningKey) -> int:
    setting_key, default, minimum, maximum = _TUNING[key]
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (setting_key,))
    if row is None:
        return default
    try:
        value = int(row["value"])
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, value))


async def set_tuning(
    db: Database, actor: Principal, request_id: str, key: TuningKey, value: int
) -> dict[str, Any]:
    setting_key, _default, minimum, maximum = _TUNING[key]
    clamped = max(minimum, min(maximum, value))
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (setting_key, str(clamped), now, actor.user_id),
            ),
            audit_statement(
                action="support_bot.tuning_changed",
                entity_type="app_setting",
                entity_id=setting_key,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"key": key, "value": clamped},
            ),
        ]
    )
    return {"key": key, "value": clamped}


async def is_enabled(db: Database, scope: BotScope) -> bool:
    row = await db.fetch_one(
        "SELECT value FROM app_settings WHERE key = ?", (_SETTING_KEYS[scope],)
    )
    if row is None:
        return _DEFAULT_ENABLED
    return row["value"] == "true"


async def set_enabled(
    db: Database, actor: Principal, request_id: str, scope: BotScope, enabled: bool
) -> dict[str, Any]:
    key = _SETTING_KEYS[scope]
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (key, "true" if enabled else "false", now, actor.user_id),
            ),
            audit_statement(
                action="support_bot.enabled_changed",
                entity_type="app_setting",
                entity_id=key,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"scope": scope, "enabled": enabled},
            ),
        ]
    )
    return {"scope": scope, "enabled": enabled}


_WIDGET_COLOR_KEY = "support_bot.widget_color"
# Deliberately only `#rgb`/`#rrggbb`. This value is interpolated into an inline
# `style` attribute on both widgets, so anything richer (a `url(...)`, a
# `color-mix(...)`, a stray `;`) would be an injection point for whoever can
# reach the settings screen. A plain hex triplet cannot express anything but a
# colour.
_HEX_COLOR_PATTERN = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


async def get_widget_color(db: Database) -> str:
    """The operator's chat-widget colour, or "" meaning "inherit the site brand"."""
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (_WIDGET_COLOR_KEY,))
    if row is None:
        return ""
    value = str(row["value"] or "").strip()
    return value if _HEX_COLOR_PATTERN.match(value) else ""


async def set_widget_color(
    db: Database, actor: Principal, request_id: str, color: str
) -> dict[str, str]:
    value = color.strip()
    if value and not _HEX_COLOR_PATTERN.match(value):
        raise ValidationAppError(
            "Use a hex colour like #1f7a4d, or leave it blank to use the site brand colour."
        )
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                " updated_by = excluded.updated_by",
                (_WIDGET_COLOR_KEY, value, now, actor.user_id),
            ),
            audit_statement(
                action="support_bot.widget_color_changed",
                entity_type="app_setting",
                entity_id=_WIDGET_COLOR_KEY,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"color": value},
            ),
        ]
    )
    return {"widgetColor": value}


async def get_all(db: Database) -> dict[str, Any]:
    settings: dict[str, Any] = {scope: await is_enabled(db, scope) for scope in _SETTING_KEYS}
    for key in _TUNING:
        settings[key] = await get_tuning(db, key)
    settings["widgetColor"] = await get_widget_color(db)
    settings["policyPages"] = " ".join(await get_policy_pages(db))
    return settings

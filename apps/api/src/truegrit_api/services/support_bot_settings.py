"""On/off switches and answer-tuning knobs for the support bots.

Two bots, and they are no longer the same kind of thing:

* The **admin panel bot** (`services.support_bot`) is model-backed, so it has
  a prompt whose size and reference material are worth tuning. The knobs below
  are its.
* The **storefront bot** (`truegrit_api.support_bot`) is deterministic and has
  no prompt at all. It reads exactly one value from this module,
  `support_bot.storefront_enabled`, and nothing else here applies to it. What
  it needs from an operator instead lives in `services.support_bot_operations`:
  the policy facts it quotes, and the queue of questions it could not answer.

Three settings were removed when the storefront bot stopped using a model:
`policyPages` (the allowlist for a `read_policy` tool that no longer exists),
`searchResults` and `policyChars` (limits on that bot's prompt). All three had
become inert, and a settings screen offering knobs that do nothing is worse
than one that omits them.

Stored in the existing `app_settings` key/value table (migration 0034),
exactly the same pattern `services.discussions`' min-account-age setting
already uses -- no new table needed for a handful of scalars. Both bots
default to enabled; an admin with `support_bot.manage` can turn either off
(e.g. while a Workers AI incident is ongoing, or the knowledge base is being
reworked) without a deploy.

The tuning values are here rather than as module constants because they change
how every admin-bot answer is built, and an operator tuning answer quality
should not need a deploy to do it. Both are clamped to a sane range on the way
in, so a bad value cannot make the prompt unbounded.
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
TuningKey = Literal["historyTurns", "knowledgeSnippets"]

_SETTING_KEYS: dict[BotScope, str] = {
    "admin": "support_bot.admin_enabled",
    "storefront": "support_bot.storefront_enabled",
}
_DEFAULT_ENABLED = True

# key -> (app_settings key, default, minimum, maximum). Admin bot only.
_TUNING: dict[TuningKey, tuple[str, int, int, int]] = {
    # How many prior turns the client may replay into the prompt. Higher keeps
    # more context, at a proportional cost in tokens and CPU per answer.
    "historyTurns": ("support_bot.history_turns", 10, 0, 40),
    # How many knowledge-base entries are embedded as reference material.
    "knowledgeSnippets": ("support_bot.knowledge_snippets", 6, 1, 30),
}


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
    return settings

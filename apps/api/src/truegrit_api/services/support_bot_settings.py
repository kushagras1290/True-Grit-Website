"""On/off switch for each support bot, shared by `services.support_bot`
(admin) and `services.support_bot_public` (storefront).

Stored in the existing `app_settings` key/value table (migration 0034),
exactly the same pattern `services.discussions`' min-account-age setting
already uses -- no new table needed for a single boolean. Both bots default
to enabled; an admin with `support_bot.manage` can turn either off (e.g.
while a Workers AI incident is ongoing, or the knowledge base is being
reworked) without a deploy.
"""

from __future__ import annotations

from typing import Any, Literal

from truegrit_api.auth.principal import Principal
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

BotScope = Literal["admin", "storefront"]

_SETTING_KEYS: dict[BotScope, str] = {
    "admin": "support_bot.admin_enabled",
    "storefront": "support_bot.storefront_enabled",
}
_DEFAULT_ENABLED = True


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


async def get_all(db: Database) -> dict[str, bool]:
    return {scope: await is_enabled(db, scope) for scope in _SETTING_KEYS}

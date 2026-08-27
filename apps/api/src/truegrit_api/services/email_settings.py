"""Admin-controlled email provider, category toggles and rate limits.

Every switch lives in ``app_settings`` (migration 0034), the same table
``feature_settings.py`` uses for storefront switches -- no new settings
table, and the same admin console pattern applies: configure first, reveal
deliberately, and a missing/unparseable row degrades to the shipped default
rather than raising, so a corrupted row can never brick email delivery.

``EMAIL_CATEGORIES`` is the single source of truth for what a category *is*
-- the admin router, ``services.jobs`` dispatch, and the three direct
staff-account send sites in ``api.admin`` all import it rather than each
keeping their own list, so a category can never exist in one place and not
the others.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

KEY_PROVIDER: Final = "email.provider"
KEY_LIMIT_GLOBAL_HOURLY: Final = "email.limit.global.hourly"
KEY_LIMIT_GLOBAL_DAILY: Final = "email.limit.global.daily"
_CATEGORY_ENABLED_PREFIX: Final = "email.category."
_CATEGORY_ENABLED_SUFFIX: Final = ".enabled"
_CATEGORY_LIMIT_PREFIX: Final = "email.limit.category."

# category -> (human label, one-line description shown in the admin UI).
EMAIL_CATEGORIES: Final[dict[str, tuple[str, str]]] = {
    "order_confirmation": ("Order confirmation", "Sent to a customer when their order is placed."),
    "order_farm_notification": (
        "Farm order notice",
        "Sent to a farm owner when one of their products is ordered.",
    ),
    "customer_welcome": ("Customer welcome", "Sent when a new customer account is created."),
    "customer_password_reset": (
        "Customer password reset",
        "Sent when a customer requests a password reset.",
    ),
    "contact_form": ("Contact form", "Sent to staff when a storefront contact form is submitted."),
    "farm_partnership_application": (
        "Farm partnership application",
        "Sent to staff and the applicant when a farm applies to supply True Grit.",
    ),
    "farm_partnership_decision": (
        "Farm partnership decision",
        "Sent to an applicant when staff approve or reject their application.",
    ),
    "content_submission_decision": (
        "Content submission decision",
        "Sent to a contributor when staff approve, request changes on, or reject a submission.",
    ),
    "staff_account": (
        "Staff account",
        "Staff invitations and staff password resets. Disabling this can block staff "
        "self-service password reset -- the recovery path into this very admin panel.",
    ),
    "refund_orchestrator": (
        "Refund orchestrator",
        "Sent to a customer when the automated refund agent approves or denies their return.",
    ),
    "ai_quota": (
        "Workers AI quota",
        "Sent to staff when Cloudflare Workers AI appears to exhaust its daily free-neuron allowance.",
    ),
}

_DEFAULT_GLOBAL_HOURLY: Final = 300
_DEFAULT_GLOBAL_DAILY: Final = 3000
# Sanity ceilings, not realistic values -- the same role HERO_SLIDES_HARD_LIMIT
# plays in feature_settings.py: guard against a fat-fingered entry turning the
# rate limit into no limit at all.
_MAX_HOURLY_LIMIT: Final = 20_000
_MAX_DAILY_LIMIT: Final = 100_000

_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})
_VALID_PROVIDERS: Final = frozenset({"resend", "brevo"})


@dataclass(frozen=True)
class CategoryLimits:
    hourly: int | None  # None = no category-specific cap; global limit still applies.
    daily: int | None


@dataclass(frozen=True)
class EmailControlSettings:
    provider: str | None  # None = auto (best configured provider wins).
    category_enabled: dict[str, bool]
    global_hourly_limit: int
    global_daily_limit: int
    category_limits: dict[str, CategoryLimits]

    def to_camel_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "categories": {
                category: {
                    "label": EMAIL_CATEGORIES[category][0],
                    "description": EMAIL_CATEGORIES[category][1],
                    "enabled": self.category_enabled[category],
                    "hourlyLimit": self.category_limits[category].hourly,
                    "dailyLimit": self.category_limits[category].daily,
                }
                for category in EMAIL_CATEGORIES
            },
            "globalHourlyLimit": self.global_hourly_limit,
            "globalDailyLimit": self.global_daily_limit,
        }


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def _parse_optional_int(raw: str | None, *, maximum: int) -> int | None:
    if raw is None or not raw.strip():
        return None
    try:
        parsed = int(raw.strip())
    except ValueError:
        return None
    if parsed < 1:
        return None
    return min(parsed, maximum)


def _parse_bounded_int(raw: str | None, *, default: int, maximum: int) -> int:
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    if parsed < 1:
        return default
    return min(parsed, maximum)


async def _read_values(db: Database) -> dict[str, str]:
    rows = await db.fetch_all("SELECT key, value FROM app_settings")
    return {row["key"]: row["value"] for row in rows}


async def load_email_settings(db: Database) -> EmailControlSettings:
    values = await _read_values(db)
    provider_raw = (values.get(KEY_PROVIDER) or "").strip().lower()
    provider = provider_raw if provider_raw in _VALID_PROVIDERS else None
    category_enabled = {
        category: _parse_bool(
            values.get(f"{_CATEGORY_ENABLED_PREFIX}{category}{_CATEGORY_ENABLED_SUFFIX}"),
            default=True,
        )
        for category in EMAIL_CATEGORIES
    }
    category_limits = {
        category: CategoryLimits(
            hourly=_parse_optional_int(
                values.get(f"{_CATEGORY_LIMIT_PREFIX}{category}.hourly"), maximum=_MAX_HOURLY_LIMIT
            ),
            daily=_parse_optional_int(
                values.get(f"{_CATEGORY_LIMIT_PREFIX}{category}.daily"), maximum=_MAX_DAILY_LIMIT
            ),
        )
        for category in EMAIL_CATEGORIES
    }
    return EmailControlSettings(
        provider=provider,
        category_enabled=category_enabled,
        global_hourly_limit=_parse_bounded_int(
            values.get(KEY_LIMIT_GLOBAL_HOURLY),
            default=_DEFAULT_GLOBAL_HOURLY,
            maximum=_MAX_HOURLY_LIMIT,
        ),
        global_daily_limit=_parse_bounded_int(
            values.get(KEY_LIMIT_GLOBAL_DAILY),
            default=_DEFAULT_GLOBAL_DAILY,
            maximum=_MAX_DAILY_LIMIT,
        ),
        category_limits=category_limits,
    )


async def category_enabled(db: Database, category: str) -> bool:
    """Whether ``category`` is switched on -- checked by the outbox dispatcher
    and by the three direct staff-account send sites before they call
    ``send_email`` at all."""
    return (await load_email_settings(db)).category_enabled.get(category, True)


async def preferred_provider(db: Database) -> str | None:
    return (await load_email_settings(db)).provider


async def update_email_settings(
    db: Database, actor: Principal, request_id: str, *, updates: dict[str, Any]
) -> EmailControlSettings:
    """Persist changed fields and record one audit entry. Only keys present in
    ``updates`` are written, the same partial-update discipline
    ``update_storefront_settings`` uses -- a PATCH toggling one category must
    never reset the others to whatever the client last happened to render."""
    now = utc_now_iso()
    pending: list[tuple[str, str]] = []
    changed: dict[str, Any] = {}

    if "provider" in updates:
        raw = updates["provider"]
        provider = None if raw is None else str(raw).strip().lower()
        if provider is not None and provider not in _VALID_PROVIDERS:
            raise ValidationAppError("Email provider must be 'resend', 'brevo', or unset.")
        pending.append((KEY_PROVIDER, provider or ""))
        changed["provider"] = provider

    if "global_hourly_limit" in updates:
        value = int(updates["global_hourly_limit"])
        if not 1 <= value <= _MAX_HOURLY_LIMIT:
            raise ValidationAppError(
                f"Global hourly limit must be between 1 and {_MAX_HOURLY_LIMIT}."
            )
        pending.append((KEY_LIMIT_GLOBAL_HOURLY, str(value)))
        changed["global_hourly_limit"] = value

    if "global_daily_limit" in updates:
        value = int(updates["global_daily_limit"])
        if not 1 <= value <= _MAX_DAILY_LIMIT:
            raise ValidationAppError(
                f"Global daily limit must be between 1 and {_MAX_DAILY_LIMIT}."
            )
        pending.append((KEY_LIMIT_GLOBAL_DAILY, str(value)))
        changed["global_daily_limit"] = value

    categories_update = updates.get("categories")
    if isinstance(categories_update, dict):
        for category, fields in categories_update.items():
            if category not in EMAIL_CATEGORIES or not isinstance(fields, dict):
                continue
            if "enabled" in fields and fields["enabled"] is not None:
                enabled = bool(fields["enabled"])
                enabled_key = f"{_CATEGORY_ENABLED_PREFIX}{category}{_CATEGORY_ENABLED_SUFFIX}"
                pending.append((enabled_key, "1" if enabled else "0"))
                changed[f"{category}.enabled"] = enabled
            if "hourly_limit" in fields:
                raw_limit = fields["hourly_limit"]
                value = "" if raw_limit in (None, "") else str(int(raw_limit))
                if value and not 1 <= int(value) <= _MAX_HOURLY_LIMIT:
                    raise ValidationAppError(
                        f"{category} hourly limit must be blank or between"
                        f" 1 and {_MAX_HOURLY_LIMIT}."
                    )
                pending.append((f"{_CATEGORY_LIMIT_PREFIX}{category}.hourly", value))
                changed[f"{category}.hourly_limit"] = value or None
            if "daily_limit" in fields:
                raw_limit = fields["daily_limit"]
                value = "" if raw_limit in (None, "") else str(int(raw_limit))
                if value and not 1 <= int(value) <= _MAX_DAILY_LIMIT:
                    raise ValidationAppError(
                        f"{category} daily limit must be blank or between 1 and {_MAX_DAILY_LIMIT}."
                    )
                pending.append((f"{_CATEGORY_LIMIT_PREFIX}{category}.daily", value))
                changed[f"{category}.daily_limit"] = value or None

    if not pending:
        return await load_email_settings(db)

    statements: list[tuple[str, tuple[Any, ...]]] = [
        (
            "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET"
            "  value = excluded.value, updated_at = excluded.updated_at,"
            "  updated_by = excluded.updated_by",
            (key, value, now, actor.user_id),
        )
        for key, value in pending
    ]
    statements.append(
        audit_statement(
            action="settings.email_updated",
            entity_type="app_setting",
            entity_id="email",
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        )
    )
    await db.batch(statements)
    return await load_email_settings(db)

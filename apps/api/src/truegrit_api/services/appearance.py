"""Owner-editable colours and ambient effects (migration 0052).

The storefront's palette is a set of CSS custom properties. A theme is a sparse
map of overrides for them: one site-wide baseline, plus a set per page that
wants its own look, plus a set per visitor country. Effects -- falling snow, a
cursor trail -- ride on the same rows because they are the same decision, made
on the same admin page.

Three scope kinds, and how they combine (see `load_public_appearance`):

* ``global``       -- the site-wide baseline. Always exists.
* ``/path``         -- one page and everything beneath it, for every visitor
  regardless of country. Wins over a country override for the same colour: an
  editorial page's intentional design should not be silently undone by a geo
  experiment.
* ``country:XX``    -- an ISO-3166 alpha-2 code, uppercase. Overrides the
  global palette (or the global effects) for visitors Cloudflare's edge
  resolves to that country -- the same signal ``resolveCountry()`` already
  uses for currency and catalogue release.

Colours merge key-by-key across layers (global, then country, then page).
Effects do not merge: "snowfall" and "no effect" have no sensible in-between,
so a country's effects override replaces the whole ambient+cursor
configuration rather than patching pieces of it.

Three rules make this safe to hand to an owner:

* **Sparse wins.** Only the colours somebody deliberately changed are stored. A
  missing key means "keep the shipped value", so a half-written theme degrades
  to the stock palette rather than to a page of undefined colours, and adding a
  token to the design system does not require rewriting stored rows.
* **Colours are validated here, not only in the browser.** These strings end up
  interpolated into a ``<style>`` element. A value that is not a hex colour or
  one of a short list of CSS colour functions is rejected on write, so the
  database can never hold a CSS injection waiting for a render.
* **Everything defaults to off/stock.** An unreadable row resolves to no
  overrides and no effects. A storefront that started snowing because a column
  failed to parse would be a worse failure than one that never snowed.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

GLOBAL_SCOPE: Final = "global"
COUNTRY_SCOPE_PREFIX: Final = "country:"

# Mirrors THEME_TOKEN_KEYS in `@truegrit/contracts`. Order is the order the
# admin console renders them in, which is why it is a tuple rather than a set.
THEME_TOKEN_KEYS: Final[tuple[str, ...]] = (
    "bgCanvas",
    "bgSurface",
    "bgSubtle",
    "bgInverse",
    "bannerBackdrop",
    "textPrimary",
    "textSecondary",
    "textInverse",
    "brandPrimary",
    "brandAccent",
    "brandGold",
    "borderSubtle",
    "borderStrong",
    "danger",
    "success",
    "warning",
)

AMBIENT_EFFECT_KEYS: Final[tuple[str, ...]] = (
    "none",
    "snow",
    "leaves",
    "petals",
    "rain",
    "fireflies",
    "bubbles",
    "confetti",
    "stars",
    "embers",
    "dust",
    "seeds",
    "hearts",
    "sparkles",
    "fog",
    "meteors",
)

CURSOR_TRAIL_KEYS: Final[tuple[str, ...]] = (
    "none",
    "dots",
    "ribbon",
    "comet",
    "sparkle",
    "bubbles",
    "stars",
    "hearts",
    "snow",
    "glow",
    "rings",
    "paint",
    "fireflies",
    "leaves",
    "petals",
    "embers",
)

DEFAULT_AMBIENT_COLOR: Final = "#ffffff"
DEFAULT_CURSOR_COLOR: Final = "#24483a"
DEFAULT_INTENSITY: Final = 3
MIN_INTENSITY: Final = 1
MAX_INTENSITY: Final = 5

# Every scope ships on every storefront response (or, for country rows, is at
# least scanned on every request to resolve one visitor's country), so each
# cap keeps the table from growing without bound. Neither is remotely close to
# what a real store needs: a handful of campaign pages, a handful of markets.
MAX_PAGE_SCOPES: Final = 40
MAX_COUNTRY_SCOPES: Final = 60
MAX_PATH_LENGTH: Final = 200
MAX_COLOR_LENGTH: Final = 200

_HEX_PATTERN: Final = re.compile(r"^#(?:[0-9a-f]{3}|[0-9a-f]{4}|[0-9a-f]{6}|[0-9a-f]{8})$", re.I)
# Deliberately narrow: enough for the alpha-bearing borders the stock theme
# uses, with no room for `url(...)`, a semicolon, or a closing brace.
_FUNCTIONAL_PATTERN: Final = re.compile(
    r"^(?:rgb|rgba|hsl|hsla|color-mix)\([a-z0-9\s%,./#-]{1,180}\)$", re.I
)
_PATH_PATTERN: Final = re.compile(r"^/[A-Za-z0-9\-._~/]*$")
_COUNTRY_CODE_PATTERN: Final = re.compile(r"^[A-Za-z]{2}$")
# "XX" (unknown) and "T1" (Tor) are Cloudflare sentinels, not real countries --
# see `resolveCountry()` in the storefront. A theme saved under one of them
# would never resolve for an actual visitor, only silently fail to apply.
_NOT_REAL_COUNTRIES: Final = frozenset({"XX", "T1"})


def is_valid_color(value: str) -> bool:
    """True when a value is safe to interpolate into a stylesheet as a colour."""
    candidate = value.strip()
    if not candidate or len(candidate) > MAX_COLOR_LENGTH:
        return False
    return bool(_HEX_PATTERN.match(candidate) or _FUNCTIONAL_PATTERN.match(candidate))


def country_scope(country_code: str) -> str:
    """`'IN'` -> `'country:IN'`. The one place that string is assembled."""
    return f"{COUNTRY_SCOPE_PREFIX}{country_code.strip().upper()}"


def is_country_scope(scope: str) -> bool:
    return scope.startswith(COUNTRY_SCOPE_PREFIX)


def country_code_from_scope(scope: str) -> str | None:
    """`'country:IN'` -> `'IN'`, or `None` for a scope that is not a country."""
    if not is_country_scope(scope):
        return None
    return scope[len(COUNTRY_SCOPE_PREFIX) :]


def validate_scope(scope: str) -> str:
    """`'global'`, a storefront path, or `'country:XX'`. Anything else is refused."""
    candidate = scope.strip()
    if candidate == GLOBAL_SCOPE:
        return GLOBAL_SCOPE
    if candidate.upper().startswith(COUNTRY_SCOPE_PREFIX.upper()):
        code = candidate[len(COUNTRY_SCOPE_PREFIX) :].strip().upper()
        if not _COUNTRY_CODE_PATTERN.match(code) or code in _NOT_REAL_COUNTRIES:
            raise ValidationAppError(
                "A country theme needs a real two-letter country code, such as country:IN."
            )
        return country_scope(code)
    if len(candidate) > MAX_PATH_LENGTH or candidate.startswith("//"):
        raise ValidationAppError(
            "A theme scope must be a storefront path (such as /shop) or a country"
            " (such as country:IN)."
        )
    if not _PATH_PATTERN.match(candidate):
        raise ValidationAppError(
            "A theme scope must be a storefront path (such as /shop) or a country"
            " (such as country:IN)."
        )
    # `/shop/` and `/shop` are the same page; storing both would make which one
    # wins depend on insertion order.
    return candidate.rstrip("/") or "/"


def validate_tokens(raw: Any) -> dict[str, str]:
    """Keep the known token keys carrying a valid colour; reject the rest loudly.

    Silently dropping a bad colour would leave an owner staring at a page that
    did not change, with nothing to tell them why.
    """
    if not isinstance(raw, dict):
        raise ValidationAppError("Theme colours must be an object of token names to colours.")
    tokens: dict[str, str] = {}
    for key, value in raw.items():
        if key not in THEME_TOKEN_KEYS:
            raise ValidationAppError(f"Unknown theme colour {key!r}.")
        if value is None:
            continue
        if not isinstance(value, str):
            raise ValidationAppError(f"Theme colour {key!r} must be text.")
        candidate = value.strip()
        # Blank is how the console says "back to the shipped colour", so it is
        # an erasure rather than an error.
        if not candidate:
            continue
        if not is_valid_color(candidate):
            raise ValidationAppError(
                f"{key} must be a hex colour such as #24483a, or an rgb()/hsl()/color-mix() value."
            )
        tokens[key] = candidate
    return tokens


def _default_effects() -> dict[str, Any]:
    return {
        "ambient": {
            "effect": "none",
            "color": DEFAULT_AMBIENT_COLOR,
            "intensity": DEFAULT_INTENSITY,
        },
        "cursor": {"trail": "none", "color": DEFAULT_CURSOR_COLOR, "hideNativeCursor": False},
    }


def validate_effects(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValidationAppError("Effects must be an object.")
    ambient = raw.get("ambient") or {}
    cursor = raw.get("cursor") or {}
    if not isinstance(ambient, dict) or not isinstance(cursor, dict):
        raise ValidationAppError("Effects must contain an 'ambient' and a 'cursor' object.")

    effect = ambient.get("effect", "none")
    if effect not in AMBIENT_EFFECT_KEYS:
        raise ValidationAppError(f"Unknown ambient effect {effect!r}.")
    trail = cursor.get("trail", "none")
    if trail not in CURSOR_TRAIL_KEYS:
        raise ValidationAppError(f"Unknown cursor trail {trail!r}.")

    try:
        intensity = int(ambient.get("intensity", DEFAULT_INTENSITY))
    except (TypeError, ValueError) as exc:
        raise ValidationAppError("Effect intensity must be a whole number.") from exc
    if not MIN_INTENSITY <= intensity <= MAX_INTENSITY:
        raise ValidationAppError(
            f"Effect intensity must be between {MIN_INTENSITY} and {MAX_INTENSITY}."
        )

    def colour(value: Any, fallback: str, label: str) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            return fallback
        if not isinstance(value, str) or not is_valid_color(value):
            raise ValidationAppError(f"{label} must be a hex colour such as #ffffff.")
        return value.strip()

    return {
        "ambient": {
            "effect": effect,
            "color": colour(ambient.get("color"), DEFAULT_AMBIENT_COLOR, "Ambient effect colour"),
            "intensity": intensity,
        },
        "cursor": {
            "trail": trail,
            "color": colour(cursor.get("color"), DEFAULT_CURSOR_COLOR, "Cursor trail colour"),
            "hideNativeCursor": bool(cursor.get("hideNativeCursor", False)),
        },
    }


def _read_json(raw: Any, fallback: dict[str, Any]) -> dict[str, Any]:
    """Parse a stored JSON column, degrading to the fallback on anything odd.

    Reads must never raise: this runs on the storefront's hot path, and a
    hand-edited row should cost a visitor the decoration, not the page.
    """
    if not isinstance(raw, str) or not raw.strip():
        return fallback
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return fallback
    return parsed if isinstance(parsed, dict) else fallback


def _clean_tokens(raw_json: Any) -> dict[str, str]:
    tokens = _read_json(raw_json, {})
    return {
        key: value
        for key, value in tokens.items()
        if key in THEME_TOKEN_KEYS and isinstance(value, str) and is_valid_color(value)
    }


def _clean_effects(raw_json: Any) -> dict[str, Any] | None:
    """The stored effects override, or `None` when the row carries none.

    Distinct from `_default_effects()`: a country row with no override must
    fall back to the *global* effects, not silently to the shipped default --
    those are different things once an owner has customised the global ones.
    """
    stored = _read_json(raw_json, {})
    if not stored:
        return None
    try:
        return validate_effects(stored)
    except ValidationAppError:
        return None


async def load_appearance(db: Database) -> dict[str, Any]:
    """Every scope, unmerged -- the admin console's raw editing view.

    Unlike `load_public_appearance`, nothing here is resolved for a particular
    visitor: the console edits one scope at a time, so it needs to see exactly
    what is stored in each one, not a blend.
    """
    rows = await db.fetch_all(
        "SELECT scope, tokens_json, effects_json FROM theme_settings ORDER BY scope"
    )
    global_tokens: dict[str, Any] = {}
    countries: dict[str, Any] = {}
    pages: dict[str, Any] = {}
    effects = _default_effects()
    country_effects: dict[str, Any] = {}

    for row in rows:
        clean = _clean_tokens(row["tokens_json"])
        scope = row["scope"]
        if scope == GLOBAL_SCOPE:
            global_tokens = clean
            effects = _clean_effects(row["effects_json"]) or _default_effects()
        elif is_country_scope(scope):
            if clean:
                countries[scope] = clean
            override = _clean_effects(row["effects_json"])
            if override is not None:
                country_effects[scope] = override
        elif clean:
            pages[scope] = clean

    return {
        "theme": {"global": global_tokens, "countries": countries, "pages": pages},
        "effects": effects,
        "countryEffects": country_effects,
    }


async def load_public_appearance(db: Database, country: str | None) -> dict[str, Any]:
    """The resolved view one visitor actually gets: global, country, then page.

    Colours merge key-by-key, layer over layer -- a page override never has to
    repeat colours the country override (or the global palette) already set.
    Effects do not merge: the visitor's country override replaces the global
    ambient+cursor configuration outright when one exists, since "some snow"
    is not a meaningful blend of "snow" and "no effect".

    `pages` in the returned theme is still per-path and unresolved -- the
    storefront picks the right one client-side by pathname (`resolveThemeTokens`)
    exactly as it does today, so page navigation re-themes with no second
    request. Only the *global* layer changes per visitor here.
    """
    rows = await db.fetch_all(
        "SELECT scope, tokens_json, effects_json FROM theme_settings ORDER BY scope"
    )
    global_tokens: dict[str, str] = {}
    country_tokens: dict[str, str] = {}
    pages: dict[str, Any] = {}
    effects = _default_effects()
    country_override: dict[str, Any] | None = None
    target_scope = country_scope(country) if country else None

    for row in rows:
        clean = _clean_tokens(row["tokens_json"])
        scope = row["scope"]
        if scope == GLOBAL_SCOPE:
            global_tokens = clean
            effects = _clean_effects(row["effects_json"]) or _default_effects()
        elif is_country_scope(scope):
            if scope == target_scope:
                country_tokens = clean
                country_override = _clean_effects(row["effects_json"])
        elif clean:
            pages[scope] = clean

    return {
        "theme": {"global": {**global_tokens, **country_tokens}, "pages": pages},
        "effects": country_override if country_override is not None else effects,
    }


async def list_theme_scopes(db: Database) -> list[dict[str, Any]]:
    """Every stored scope, for the admin console's scope picker."""
    rows = await db.fetch_all(
        "SELECT scope, tokens_json, effects_json, updated_at FROM theme_settings ORDER BY scope"
    )
    return [
        {
            "scope": row["scope"],
            "tokens": _clean_tokens(row["tokens_json"]),
            "hasEffectsOverride": _clean_effects(row["effects_json"]) is not None,
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


async def _assert_scope_room(db: Database, resolved: str) -> None:
    """Refuse a brand-new scope once its kind is at its cap.

    Only new scopes are checked (`known is None`) -- editing a scope that
    already exists never has to fight the cap it was created under.
    """
    if resolved == GLOBAL_SCOPE:
        return
    known = await db.fetch_one("SELECT 1 AS ok FROM theme_settings WHERE scope = ?", (resolved,))
    if known is not None:
        return
    if is_country_scope(resolved):
        existing = await db.fetch_one(
            "SELECT COUNT(*) AS total FROM theme_settings WHERE scope LIKE ?",
            (f"{COUNTRY_SCOPE_PREFIX}%",),
        )
        if existing and int(existing["total"]) >= MAX_COUNTRY_SCOPES:
            raise ValidationAppError(
                f"At most {MAX_COUNTRY_SCOPES} countries can carry their own appearance."
                " Remove one before adding another."
            )
    else:
        existing = await db.fetch_one(
            "SELECT COUNT(*) AS total FROM theme_settings WHERE scope != ? AND scope NOT LIKE ?",
            (GLOBAL_SCOPE, f"{COUNTRY_SCOPE_PREFIX}%"),
        )
        if existing and int(existing["total"]) >= MAX_PAGE_SCOPES:
            raise ValidationAppError(
                f"At most {MAX_PAGE_SCOPES} pages can carry their own colours."
                " Remove one before adding another."
            )


async def save_theme_scope(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    scope: str,
    tokens: dict[str, str],
) -> None:
    resolved = validate_scope(scope)
    await _assert_scope_room(db, resolved)

    now = utc_now_iso()
    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO theme_settings (scope, tokens_json, effects_json, updated_at, updated_by)"
            " VALUES (?, ?, '{}', ?, ?)"
            " ON CONFLICT(scope) DO UPDATE SET"
            "  tokens_json = excluded.tokens_json, updated_at = excluded.updated_at,"
            "  updated_by = excluded.updated_by",
            (resolved, json.dumps(tokens, separators=(",", ":")), now, actor.user_id),
        ),
        audit_statement(
            action="settings.theme_updated",
            entity_type="theme",
            entity_id=resolved,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"scope": resolved, "tokens": tokens},
        ),
    ]
    await db.batch(statements)


async def delete_theme_scope(
    db: Database, actor: Principal, request_id: str, *, scope: str
) -> None:
    resolved = validate_scope(scope)
    if resolved == GLOBAL_SCOPE:
        raise ValidationAppError(
            "The site-wide colours cannot be deleted. Clear the individual colours instead."
        )
    existing = await db.fetch_one("SELECT 1 AS ok FROM theme_settings WHERE scope = ?", (resolved,))
    if existing is None:
        raise NotFoundError(f"No colours are saved for {resolved}.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM theme_settings WHERE scope = ?", (resolved,)),
            audit_statement(
                action="settings.theme_deleted",
                entity_type="theme",
                entity_id=resolved,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"scope": resolved},
            ),
        ]
    )


async def save_effects(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    effects: dict[str, Any],
    scope: str = GLOBAL_SCOPE,
) -> dict[str, Any]:
    """Save the ambient effect and cursor trail for `scope`.

    `scope` is `'global'` (the site-wide default) or `'country:XX'` (a
    per-country override) -- never a page path, because effects are a
    whole-visit decision, not something that makes sense to swap mid-browse the
    way a page's colours do.
    """
    resolved = scope if scope == GLOBAL_SCOPE else validate_scope(scope)
    if resolved != GLOBAL_SCOPE and not is_country_scope(resolved):
        raise ValidationAppError("Effects can only be set globally or for a country.")
    await _assert_scope_room(db, resolved)
    validated = validate_effects(effects)
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO theme_settings (scope, tokens_json, effects_json, updated_at,"
                " updated_by) VALUES (?, '{}', ?, ?, ?)"
                " ON CONFLICT(scope) DO UPDATE SET"
                "  effects_json = excluded.effects_json, updated_at = excluded.updated_at,"
                "  updated_by = excluded.updated_by",
                (
                    resolved,
                    json.dumps(validated, separators=(",", ":")),
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="settings.effects_updated",
                entity_type="theme",
                entity_id=resolved,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=validated,
            ),
        ]
    )
    return validated


async def clear_country_effects(
    db: Database, actor: Principal, request_id: str, *, scope: str
) -> None:
    """Remove a country's effects override so it falls back to the global default.

    Distinct from `delete_theme_scope`: a country can carry colour tokens with
    no effects override (or vice versa), so clearing one must not discard the
    other. If the row would then carry neither tokens nor an override, it is
    dropped entirely rather than left as an empty husk for the console to list.
    """
    resolved = validate_scope(scope)
    if not is_country_scope(resolved):
        raise ValidationAppError("Only a country's effects override can be cleared this way.")
    row = await db.fetch_one("SELECT tokens_json FROM theme_settings WHERE scope = ?", (resolved,))
    if row is None:
        raise NotFoundError(f"No effects are saved for {resolved}.")
    now = utc_now_iso()
    if _clean_tokens(row["tokens_json"]):
        statements: list[tuple[str, Sequence[Any]]] = [
            (
                "UPDATE theme_settings SET effects_json = '{}', updated_at = ?, updated_by = ?"
                " WHERE scope = ?",
                (now, actor.user_id, resolved),
            )
        ]
    else:
        statements = [("DELETE FROM theme_settings WHERE scope = ?", (resolved,))]
    statements.append(
        audit_statement(
            action="settings.effects_deleted",
            entity_type="theme",
            entity_id=resolved,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"scope": resolved},
        )
    )
    await db.batch(statements)

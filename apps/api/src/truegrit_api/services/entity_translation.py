"""Per-locale field overrides for database-sourced content (migration 0068)
-- navigation labels, category names/descriptions, and (as the same registry
grows) farms, products, articles and recipes.

Distinct from `services.translation` (migration 0067), which translates a
whole CMS page's block tree. Here each entity type is just a handful of flat
string fields, so translating one is: look the entity up, translate the
fields the registry names for its type, store the small result object. See
the migration's own docstring for why one generic table backs every type
instead of one table each.
"""

from __future__ import annotations

import json
from typing import Any, Final

from pydantic.alias_generators import to_snake

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.repositories.entity_translations import EntityTranslationRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

# Which flat string fields are translatable per entity type, and the table +
# column each is read from for auto-translate's source text. Adding a new
# entity type or field is a code change here, never a migration -- the
# storage side (fields_json) already accepts any shape (see 0068's docstring).
TRANSLATABLE_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "navigation_item": ("label",),
    "category": (
        "name",
        "short_description",
        "hero_eyebrow",
        "hero_title",
        "hero_description",
        "hero_image_alt",
        "thumbnail_image_alt",
        "season_label",
        "seo_title",
        "seo_description",
    ),
    # `farmer_name` is deliberately absent: it is a person's name, and a machine
    # translator asked for one returns a mistranslation, not a transliteration.
    "farm": (
        "name",
        "region",
        "hero_image_alt",
        "seo_title",
        "seo_description",
    ),
    "product": (
        "name",
        "short_description",
        "storage_guidance",
        "harvest_note",
        "growing_method",
        "image_alt",
        "seo_title",
        "seo_description",
    ),
    "article": ("title", "excerpt", "hero_image_alt", "seo_title", "seo_description"),
    "recipe": ("title", "excerpt", "hero_image_alt", "seo_title", "seo_description"),
    "bundle": ("name", "description"),
}

_SOURCE_TABLE: Final[dict[str, str]] = {
    "navigation_item": "navigation_items",
    "category": "categories",
    "farm": "farms",
    "product": "products",
    "article": "articles",
    "recipe": "recipes",
    "bundle": "bundles",
}

# A sanity ceiling on one auto-translate call's work, the same role
# `_MAX_STRINGS_PER_PAGE` plays in `services.translation` -- every entity type
# here has at most 5 fields, so this is a generous margin, not a real limit.
_MAX_FIELDS_PER_ENTITY: Final = 20


class UnknownEntityTypeError(ValidationAppError):
    """`entity_type` is not one this registry knows how to translate."""


def _require_known_type(entity_type: str) -> None:
    if entity_type not in TRANSLATABLE_FIELDS:
        raise UnknownEntityTypeError(f"'{entity_type}' has no translatable fields registered.")


async def get_entity_translation(
    db: Database, entity_type: str, entity_id: str, locale: str
) -> dict[str, Any] | None:
    _require_known_type(entity_type)
    return await EntityTranslationRepository(db).get(entity_type, entity_id, locale)


async def list_entity_translations(
    db: Database, entity_type: str, entity_id: str
) -> list[dict[str, Any]]:
    _require_known_type(entity_type)
    return await EntityTranslationRepository(db).list_for_entity(entity_type, entity_id)


async def get_source_fields(db: Database, entity_type: str, entity_id: str) -> dict[str, str]:
    """The entity's current English field values, for the fields this type
    supports translating. Backs the admin editor's "no translation saved yet"
    state -- it opens pre-filled with the English copy to edit from, the same
    starting point `auto_translate_entity` itself translates."""
    _require_known_type(entity_type)
    row = await _fetch_source_row(db, entity_type, entity_id)
    return {field: str(row[field] or "") for field in TRANSLATABLE_FIELDS[entity_type]}


async def _fetch_source_row(db: Database, entity_type: str, entity_id: str) -> dict[str, Any]:
    table = _SOURCE_TABLE[entity_type]
    row = await db.fetch_one(f"SELECT * FROM {table} WHERE id = ?", (entity_id,))
    if row is None:
        raise NotFoundError(f"{entity_type.replace('_', ' ').capitalize()} not found.")
    return row


async def save_entity_translation(
    db: Database,
    actor: Principal,
    request_id: str,
    entity_type: str,
    entity_id: str,
    locale: str,
    fields: dict[str, str],
    *,
    auto_translated: bool,
) -> dict[str, Any]:
    _require_known_type(entity_type)
    await _fetch_source_row(db, entity_type, entity_id)  # 404s a bad id before writing

    # `fields` is a free-form map, not a Pydantic model, so the request's own
    # camelCase-in/snake_case-out convention (`_CamelModel`) never touches its
    # keys -- normalized here instead, so the admin UI can send `heroTitle`
    # like every other field in this codebase rather than the Python-internal
    # `hero_title` `TRANSLATABLE_FIELDS` is keyed by.
    normalized = {to_snake(key): value for key, value in fields.items()}
    allowed = TRANSLATABLE_FIELDS[entity_type]
    unknown = set(normalized) - set(allowed)
    if unknown:
        raise ValidationAppError(
            f"'{entity_type}' does not support translating: {', '.join(sorted(unknown))}."
        )
    if len(normalized) > _MAX_FIELDS_PER_ENTITY:
        raise ValidationAppError("Too many fields in one translation save.")
    cleaned = {key: value for key, value in normalized.items() if isinstance(value, str)}

    now = utc_now_iso()

    await db.batch(
        [
            (
                "INSERT INTO entity_translations"
                " (entity_type, entity_id, locale, fields_json, auto_translated,"
                "  updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(entity_type, entity_id, locale) DO UPDATE SET"
                "  fields_json = excluded.fields_json,"
                "  auto_translated = excluded.auto_translated,"
                "  updated_at = excluded.updated_at,"
                "  updated_by = excluded.updated_by",
                (
                    entity_type,
                    entity_id,
                    locale,
                    json.dumps(cleaned),
                    1 if auto_translated else 0,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="entity_translation.saved",
                entity_type=entity_type,
                entity_id=entity_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"locale": locale, "autoTranslated": auto_translated},
            ),
        ]
    )
    saved = await EntityTranslationRepository(db).get(entity_type, entity_id, locale)
    assert saved is not None
    return saved


async def delete_entity_translation(
    db: Database, entity_type: str, entity_id: str, locale: str
) -> None:
    _require_known_type(entity_type)
    await db.execute(
        "DELETE FROM entity_translations WHERE entity_type = ? AND entity_id = ? AND locale = ?",
        (entity_type, entity_id, locale),
    )


async def invalidate_stale_auto_translations(
    db: Database, entity_type: str, entity_id: str, changed_fields: set[str]
) -> None:
    """Drop every auto-translated row for this entity when an English field
    the translation registry tracks just changed.

    Without this, renaming a category (or product, ...) from English left
    every other locale showing the *old* English text's translation
    indefinitely -- correct-looking, wrong content, with no visible sign
    anything was stale. Only `auto_translated = 1` rows are touched: a
    reviewed/hand-written translation (`auto_translated = 0`) is a deliberate
    editorial choice, never discarded just because the English source moved.
    Dropping the row rather than re-translating inline means a save stays
    fast (no external translation call in the request path) and falls back
    to English immediately instead of showing stale text -- the existing
    `backfill-entity-translations` batch script is what regenerates the
    dropped rows.
    """
    if entity_type not in TRANSLATABLE_FIELDS:
        return
    if not (changed_fields & set(TRANSLATABLE_FIELDS[entity_type])):
        return
    await db.execute(
        "DELETE FROM entity_translations"
        " WHERE entity_type = ? AND entity_id = ? AND auto_translated = 1",
        (entity_type, entity_id),
    )


async def auto_translate_entity(
    db: Database,
    actor: Principal,
    request_id: str,
    translator: Translator,
    entity_type: str,
    entity_id: str,
    locale: str,
) -> dict[str, Any]:
    """Machine-translate this entity's current field values into `locale` and
    store them, flagged `auto_translated` so an editor reads it as a draft to
    review. Overwrites any existing translation for this locale -- re-running
    it is how an editor gets a fresh starting point after the English fields
    change. Mirrors `services.translation.auto_translate_page`."""
    _require_known_type(entity_type)
    row = await _fetch_source_row(db, entity_type, entity_id)

    translated: dict[str, str] = {}
    for field in TRANSLATABLE_FIELDS[entity_type]:
        value = row.get(field)
        if not value or not str(value).strip():
            continue
        translated[field] = await translator.translate(str(value), target_lang=locale)

    return await save_entity_translation(
        db, actor, request_id, entity_type, entity_id, locale, translated, auto_translated=True
    )

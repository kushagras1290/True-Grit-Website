"""Central translation workspace for runtime content and interface copy.

The older page/entity translation tables remain supported.  This service adds
fine-grained string rows on top so editors can translate complete structured
documents (blocks, recipe steps and user discussions), detect source changes,
and correct interface catalogue entries without rebuilding the storefront.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

MAX_FIELDS_PER_RESOURCE: Final = 180
MAX_TEXT_LENGTH: Final = 10_000
_LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8}){0,3}$")

# Values under these keys are identifiers, links or machine tokens rather than
# prose.  Everything else that is a non-empty string is intentionally included:
# image alt text and SEO copy are customer-facing text too.
_STRUCTURAL_KEYS: Final = frozenset(
    {
        "id",
        "type",
        "version",
        "enabled",
        "href",
        "imageUrl",
        "image_url",
        "farmSlug",
        "farm_slug",
        "productSlug",
        "product_slug",
        "productSlugs",
        "product_slugs",
        "categorySlugs",
        "category_slugs",
        "promotionId",
        "promotion_id",
        "reviewIds",
        "review_ids",
        "source",
        "layout",
    }
)


@dataclass(frozen=True)
class ResourceSpec:
    table: str
    title_column: str
    fields: tuple[str, ...]
    status_column: str | None = "status"
    updated_column: str = "updated_at"


RESOURCE_SPECS: Final[dict[str, ResourceSpec]] = {
    "announcement": ResourceSpec("announcements", "message", ("message",), None),
    "navigation_item": ResourceSpec("navigation_items", "label", ("label",), None, "id"),
    "category": ResourceSpec(
        "categories",
        "name",
        (
            "name",
            "short_description",
            "hero_eyebrow",
            "hero_title",
            "hero_description",
            "season_label",
            "seo_title",
            "seo_description",
            "hero_image_alt",
        ),
    ),
    "farm": ResourceSpec(
        "farms",
        "name",
        ("name", "region", "seo_title", "seo_description", "hero_image_alt"),
    ),
    "product": ResourceSpec(
        "products",
        "name",
        (
            "name",
            "short_description",
            "seo_title",
            "seo_description",
            "image_alt",
            "harvest_note",
            "growing_method",
            "storage_guidance",
        ),
    ),
    "article": ResourceSpec(
        "articles",
        "title",
        ("title", "excerpt", "seo_title", "seo_description", "hero_image_alt"),
    ),
    "recipe": ResourceSpec(
        "recipes",
        "title",
        ("title", "excerpt", "seo_title", "seo_description", "hero_image_alt"),
    ),
    "bundle": ResourceSpec("bundles", "name", ("name", "description")),
    "discussion": ResourceSpec(
        "discussions", "title", ("title", "body", "image_alt"), None
    ),
    "discussion_comment": ResourceSpec(
        "discussion_comments", "body", ("body",), None
    ),
    "content_comment": ResourceSpec("content_comments", "body", ("body",), None),
    "review": ResourceSpec("reviews", "title", ("title", "body"), "status", "created_at"),
    "promotion": ResourceSpec(
        "promotions", "name", ("headline", "description"), "status", "updated_at"
    ),
    "page": ResourceSpec(
        "pages", "title", ("title", "seo_title", "seo_description"), "status", "updated_at"
    ),
}


def validate_locale(code: str) -> str:
    value = code.strip()
    if not _LOCALE_PATTERN.fullmatch(value) or len(value) > 35:
        raise ValidationAppError("Use a valid BCP-47 language code, for example hi or pt-BR.")
    if value.lower() == "en":
        raise ValidationAppError("English is the source language and does not need translations.")
    return value


def source_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _path_part(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _flatten_strings(value: Any, *, prefix: str) -> dict[str, str]:
    fields: dict[str, str] = {}

    def walk(node: Any, path: str, parent_key: str | None = None) -> None:
        if isinstance(node, str):
            text = node.strip()
            if text and parent_key not in _STRUCTURAL_KEYS:
                fields[path] = node
            return
        if isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}/{index}")
            return
        if isinstance(node, dict):
            for key, item in node.items():
                walk(item, f"{path}/{_path_part(str(key))}", str(key))

    walk(value, prefix)
    return fields


async def _source_row(db: Database, resource_type: str, resource_id: str) -> dict[str, Any]:
    spec = RESOURCE_SPECS.get(resource_type)
    if spec is None:
        raise ValidationAppError(f"Unsupported translation resource: {resource_type}.")
    row = await db.fetch_one(f"SELECT * FROM {spec.table} WHERE id = ?", (resource_id,))
    if row is None:
        raise NotFoundError("Translation resource not found.")
    return row


async def get_source_fields(
    db: Database, resource_type: str, resource_id: str
) -> tuple[dict[str, str], dict[str, Any]]:
    spec = RESOURCE_SPECS.get(resource_type)
    if spec is None:
        raise ValidationAppError(f"Unsupported translation resource: {resource_type}.")
    row = await _source_row(db, resource_type, resource_id)
    fields = {
        field: str(row.get(field) or "")
        for field in spec.fields
        if str(row.get(field) or "").strip()
    }

    if resource_type == "page" and row.get("published_version_id"):
        version = await db.fetch_one(
            "SELECT content_json FROM page_versions WHERE id = ?", (row["published_version_id"],)
        )
        if version:
            fields.update(_flatten_strings(json.loads(version["content_json"]), prefix="content"))
    elif resource_type == "article" and row.get("published_version_id"):
        version = await db.fetch_one(
            "SELECT content_json FROM article_versions WHERE id = ?", (row["published_version_id"],)
        )
        if version:
            fields.update(_flatten_strings(json.loads(version["content_json"]), prefix="content"))
    elif resource_type == "recipe":
        if row.get("published_version_id"):
            version = await db.fetch_one(
                "SELECT content_json FROM recipe_versions WHERE id = ?",
                (row["published_version_id"],),
            )
            if version:
                fields.update(
                    _flatten_strings(json.loads(version["content_json"]), prefix="content")
                )
        ingredients = await db.fetch_all(
            "SELECT id, label, quantity_text FROM recipe_ingredients"
            " WHERE recipe_id = ? ORDER BY sort_order, id",
            (resource_id,),
        )
        for ingredient in ingredients:
            token = _path_part(str(ingredient["id"]))
            if str(ingredient.get("label") or "").strip():
                fields[f"ingredient/{token}/label"] = str(ingredient["label"])
            if str(ingredient.get("quantity_text") or "").strip():
                fields[f"ingredient/{token}/quantity_text"] = str(ingredient["quantity_text"])
    elif resource_type == "farm":
        story = json.loads(row.get("story_json") or "{}")
        fields.update(_flatten_strings(story, prefix="story"))

    if len(fields) > MAX_FIELDS_PER_RESOURCE:
        raise ValidationAppError(
            f"This item contains more than {MAX_FIELDS_PER_RESOURCE} translatable strings."
        )
    meta = {
        "id": resource_id,
        "type": resource_type,
        "title": str(row.get(spec.title_column) or resource_id),
        "status": str(row.get(spec.status_column) or "") if spec.status_column else "",
        "updatedAt": str(row.get(spec.updated_column) or ""),
    }
    return fields, meta


async def get_saved_entries(
    db: Database, resource_type: str, resource_id: str, locale: str
) -> dict[str, dict[str, Any]]:
    rows = await db.fetch_all(
        "SELECT field_key, source_text, source_hash, translated_text, status, updated_at"
        " FROM translation_entries WHERE resource_type = ? AND resource_id = ? AND locale = ?",
        (resource_type, resource_id, locale),
    )
    return {str(row["field_key"]): row for row in rows}


async def resource_detail(
    db: Database, resource_type: str, resource_id: str, locale: str
) -> dict[str, Any]:
    locale = validate_locale(locale)
    fields, meta = await get_source_fields(db, resource_type, resource_id)
    saved = await get_saved_entries(db, resource_type, resource_id, locale)
    items = []
    for key, source in fields.items():
        entry = saved.get(key)
        items.append(
            {
                "key": key,
                "source": source,
                "translation": str(entry["translated_text"]) if entry else "",
                "status": str(entry["status"]) if entry else "missing",
                "stale": bool(entry and entry["source_hash"] != source_hash(source)),
                "updatedAt": str(entry["updated_at"]) if entry else None,
            }
        )
    return {**meta, "locale": locale, "fields": items}


async def list_resources(
    db: Database,
    resource_type: str,
    locale: str,
    *,
    search: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    locale = validate_locale(locale)
    spec = RESOURCE_SPECS.get(resource_type)
    if spec is None:
        raise ValidationAppError(f"Unsupported translation resource: {resource_type}.")
    params: list[Any] = []
    where = ""
    if search and search.strip():
        where = f" WHERE {spec.title_column} LIKE ?"
        params.append(f"%{search.strip()}%")
    count = await db.fetch_one(f"SELECT COUNT(*) AS total FROM {spec.table}{where}", tuple(params))
    rows = await db.fetch_all(
        f"SELECT id, {spec.title_column} AS title, {spec.updated_column} AS updated_at"
        + (f", {spec.status_column} AS status" if spec.status_column else ", '' AS status")
        + f" FROM {spec.table}{where} ORDER BY {spec.updated_column} DESC LIMIT ? OFFSET ?",
        (*params, limit, offset),
    )
    items: list[dict[str, Any]] = []
    for row in rows:
        fields, _ = await get_source_fields(db, resource_type, str(row["id"]))
        saved = await get_saved_entries(db, resource_type, str(row["id"]), locale)
        translated = sum(
            1
            for key, source in fields.items()
            if key in saved and str(saved[key]["translated_text"]).strip()
        )
        stale = sum(
            1
            for key, source in fields.items()
            if key in saved and saved[key]["source_hash"] != source_hash(source)
        )
        items.append(
            {
                "id": row["id"],
                "type": resource_type,
                "title": row["title"] or row["id"],
                "status": row["status"] or "",
                "updatedAt": row["updated_at"] or "",
                "fieldCount": len(fields),
                "translatedCount": translated,
                "staleCount": stale,
            }
        )
    return {
        "items": items,
        "total": int(count["total"]) if count else 0,
        "limit": limit,
        "offset": offset,
    }


async def save_resource(
    db: Database,
    actor: Principal,
    request_id: str,
    resource_type: str,
    resource_id: str,
    locale: str,
    translations: dict[str, str],
    *,
    status: str = "reviewed",
) -> dict[str, Any]:
    locale = validate_locale(locale)
    if status not in {"machine", "reviewed"}:
        raise ValidationAppError("Unsupported translation status.")
    sources, _ = await get_source_fields(db, resource_type, resource_id)
    unknown = set(translations) - set(sources)
    if unknown:
        raise ValidationAppError("The source changed. Reload this item before saving.")
    if len(translations) > MAX_FIELDS_PER_RESOURCE:
        raise ValidationAppError("Too many translation fields in one request.")
    now = utc_now_iso()
    statements: list[tuple[str, Any]] = []
    for key, raw in translations.items():
        translated = raw.strip()
        if len(translated) > MAX_TEXT_LENGTH:
            raise ValidationAppError(f"Translation for {key} is too long.")
        if not translated:
            statements.append(
                (
                    "DELETE FROM translation_entries WHERE resource_type = ?"
                    " AND resource_id = ? AND field_key = ? AND locale = ?",
                    (resource_type, resource_id, key, locale),
                )
            )
            continue
        source = sources[key]
        statements.append(
            (
                "INSERT INTO translation_entries"
                " (resource_type, resource_id, field_key, locale, source_text, source_hash,"
                " translated_text, status, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(resource_type, resource_id, field_key, locale) DO UPDATE SET"
                " source_text = excluded.source_text, source_hash = excluded.source_hash,"
                " translated_text = excluded.translated_text, status = excluded.status,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (
                    resource_type,
                    resource_id,
                    key,
                    locale,
                    source,
                    source_hash(source),
                    translated,
                    status,
                    now,
                    actor.user_id,
                ),
            )
        )
    statements.append(
        audit_statement(
            action="translation_hub.saved",
            entity_type=resource_type,
            entity_id=resource_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"locale": locale, "fields": len(translations), "status": status},
        )
    )
    await db.batch(statements)
    return await resource_detail(db, resource_type, resource_id, locale)


async def auto_translate_resource(
    db: Database,
    actor: Principal,
    request_id: str,
    translator: Translator,
    resource_type: str,
    resource_id: str,
    locale: str,
) -> dict[str, Any]:
    locale = validate_locale(locale)
    sources, _ = await get_source_fields(db, resource_type, resource_id)
    translated: dict[str, str] = {}
    for key, source in sources.items():
        translated[key] = await translator.translate(source, target_lang=locale)
    return await save_resource(
        db,
        actor,
        request_id,
        resource_type,
        resource_id,
        locale,
        translated,
        status="machine",
    )


async def delete_resource_locale(
    db: Database, resource_type: str, resource_id: str, locale: str
) -> None:
    locale = validate_locale(locale)
    await db.execute(
        "DELETE FROM translation_entries WHERE resource_type = ? AND resource_id = ?"
        " AND locale = ?",
        (resource_type, resource_id, locale),
    )


async def override_map(
    db: Database, resource_type: str, resource_id: str, locale: str
) -> dict[str, str]:
    if not locale or locale.lower() == "en":
        return {}
    rows = await db.fetch_all(
        "SELECT field_key, translated_text FROM translation_entries"
        " WHERE resource_type = ? AND resource_id = ? AND locale = ?"
        " AND translated_text != ''",
        (resource_type, resource_id, locale),
    )
    return {str(row["field_key"]): str(row["translated_text"]) for row in rows}


def apply_path_overrides(document: Any, overrides: dict[str, str], *, prefix: str) -> Any:
    """Apply only paths rooted at ``prefix`` to a copied JSON document."""
    copied = json.loads(json.dumps(document))
    marker = f"{prefix}/"
    for key, translated in overrides.items():
        if not key.startswith(marker):
            continue
        parts = [
            part.replace("~1", "/").replace("~0", "~")
            for part in key[len(marker) :].split("/")
        ]
        target = copied
        try:
            for part in parts[:-1]:
                target = target[int(part)] if isinstance(target, list) else target[part]
            last = parts[-1]
            if isinstance(target, list):
                target[int(last)] = translated
            elif isinstance(target, dict):
                target[last] = translated
        except (KeyError, IndexError, TypeError, ValueError):
            # A source edit made the path obsolete.  It is shown as stale in the
            # hub and ignored here rather than breaking a public page.
            continue
    return copied


async def interface_overrides(
    db: Database, locale: str, *, target: str = "storefront"
) -> dict[str, str]:
    if target not in {"storefront", "admin"}:
        raise ValidationAppError("Unsupported interface translation target.")
    rows = await db.fetch_all(
        "SELECT field_key, source_text, translated_text FROM translation_entries"
        " WHERE resource_type = 'interface' AND resource_id = ? AND locale = ?"
        " AND translated_text != ''",
        (target, locale),
    )
    if target == "admin":
        return {str(row["source_text"]): str(row["translated_text"]) for row in rows}
    return {str(row["field_key"]): str(row["translated_text"]) for row in rows}


async def save_interface_entries(
    db: Database,
    actor: Principal,
    request_id: str,
    translator: Translator | None,
    locale: str,
    entries: dict[str, dict[str, str]],
    *,
    auto_translate: bool,
    target: str = "storefront",
) -> dict[str, str]:
    locale = validate_locale(locale)
    if target not in {"storefront", "admin"}:
        raise ValidationAppError("Unsupported interface translation target.")
    if len(entries) > 100:
        raise ValidationAppError("Translate at most 100 interface strings at a time.")
    now = utc_now_iso()
    statements: list[tuple[str, Any]] = []
    for key, item in entries.items():
        source = str(item.get("source") or "").strip()
        if not source or len(source) > MAX_TEXT_LENGTH or len(key) > 160:
            raise ValidationAppError("Invalid interface translation entry.")
        translated = str(item.get("translation") or "").strip()
        if auto_translate:
            assert translator is not None
            translated = await translator.translate(source, target_lang=locale)
        if not translated:
            statements.append(
                (
                    "DELETE FROM translation_entries WHERE resource_type = 'interface'"
                    " AND resource_id = ? AND field_key = ? AND locale = ?",
                    (target, key, locale),
                )
            )
            continue
        statements.append(
            (
                "INSERT INTO translation_entries"
                " (resource_type, resource_id, field_key, locale, source_text, source_hash,"
                " translated_text, status, updated_at, updated_by)"
                " VALUES ('interface', ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(resource_type, resource_id, field_key, locale) DO UPDATE SET"
                " source_text = excluded.source_text, source_hash = excluded.source_hash,"
                " translated_text = excluded.translated_text, status = excluded.status,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (
                    target,
                    key,
                    locale,
                    source,
                    source_hash(source),
                    translated,
                    "machine" if auto_translate else "reviewed",
                    now,
                    actor.user_id,
                ),
            )
        )
    statements.append(
        audit_statement(
            action="translation_hub.interface_saved",
            entity_type="interface",
            entity_id=target,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={
                "locale": locale,
                "target": target,
                "fields": len(entries),
                "autoTranslated": auto_translate,
            },
        )
    )
    await db.batch(statements)
    return await interface_overrides(db, locale, target=target)


async def list_custom_locales(db: Database, *, active_only: bool) -> list[dict[str, Any]]:
    where = " WHERE active = 1" if active_only else ""
    rows = await db.fetch_all(
        "SELECT code, native_name, english_name, direction, group_name, active, updated_at"
        f" FROM supported_locales{where} ORDER BY english_name",
    )
    return [
        {
            "code": row["code"],
            "nativeName": row["native_name"],
            "englishName": row["english_name"],
            "direction": row["direction"],
            "groupName": row["group_name"],
            "active": bool(row["active"]),
            "updatedAt": row["updated_at"],
        }
        for row in rows
    ]


async def save_custom_locale(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    code: str,
    native_name: str,
    english_name: str,
    direction: str,
    group_name: str,
    active: bool,
) -> dict[str, Any]:
    normalized = code.strip()
    if not _LOCALE_PATTERN.fullmatch(normalized) or len(normalized) > 35:
        raise ValidationAppError("Use a valid BCP-47 language code, for example ga or pt-BR.")
    if normalized.lower() == "en":
        raise ValidationAppError("The built-in English source language cannot be replaced.")
    if direction not in {"ltr", "rtl"} or group_name not in {"indian", "world"}:
        raise ValidationAppError("Invalid language direction or group.")
    native_name = native_name.strip()
    english_name = english_name.strip()
    if not native_name or not english_name or len(native_name) > 120 or len(english_name) > 120:
        raise ValidationAppError("Language names are required and must be at most 120 characters.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO supported_locales"
                " (code, native_name, english_name, direction, group_name, active,"
                " created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(code) DO UPDATE SET native_name = excluded.native_name,"
                " english_name = excluded.english_name, direction = excluded.direction,"
                " group_name = excluded.group_name, active = excluded.active,"
                " updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (
                    normalized,
                    native_name,
                    english_name,
                    direction,
                    group_name,
                    1 if active else 0,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="translation_hub.locale_saved",
                entity_type="locale",
                entity_id=normalized,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"active": active, "direction": direction, "group": group_name},
            ),
        ]
    )
    row = await db.fetch_one(
        "SELECT code, native_name, english_name, direction, group_name, active, updated_at"
        " FROM supported_locales WHERE code = ?",
        (normalized,),
    )
    assert row is not None
    return {
        "code": row["code"],
        "nativeName": row["native_name"],
        "englishName": row["english_name"],
        "direction": row["direction"],
        "groupName": row["group_name"],
        "active": bool(row["active"]),
        "updatedAt": row["updated_at"],
    }


async def delete_custom_locale(db: Database, code: str) -> None:
    if code.strip().lower() == "en":
        raise ValidationAppError("English cannot be removed.")
    await db.execute("DELETE FROM supported_locales WHERE code = ?", (code.strip(),))

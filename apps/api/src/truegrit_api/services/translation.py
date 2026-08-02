"""Per-locale content for CMS pages (migration 0067) — the homepage and
static pages both use `pages`/`page_versions`, so one mechanism translates
both. See the migration for why this stores a parallel `content_json` per
locale rather than per-field translation rows.

Auto-translation (`auto_translate_page`) walks the same block JSON structure
`domain.blocks.validate_blocks` already validates, translating only the
values under known text-bearing keys — everything else (ids, types, hrefs,
slugs, booleans, numbers) passes through untouched. The result is validated
through the identical block schema before it is stored, so a translated page
can never render a shape the storefront does not know how to draw.
"""

from __future__ import annotations

import json
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.blocks import validate_blocks
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.repositories.translations import PageTranslationRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

# Keys whose string value is customer-facing copy, translated wherever they
# appear in the block tree regardless of nesting (a hero's own `heading` and
# a `slides[].heading` are both this key, one level apart).
_TRANSLATABLE_KEYS: Final = frozenset(
    {
        "heading",
        "subheading",
        "text",
        "title",
        "label",
        "description",
        "question",
        "answer",
        "quote",
        "attribution",
        "intro",
        "eyebrow",
        "consentText",
        "imageAlt",
        "message",
    }
)
# Arrays of plain strings (not objects) that are themselves customer copy --
# `rich_text`'s `paragraphs` is the one block shape like this.
_TRANSLATABLE_STRING_LIST_KEYS: Final = frozenset({"paragraphs"})

# A sanity ceiling on one auto-translate call's work, the same role
# `HERO_SLIDES_HARD_LIMIT` plays elsewhere -- guards against a runaway
# CPU-bound request on the Workers Free plan's tight per-request budget
# (see the WHY note in wrangler.jsonc), not a realistic page size.
_MAX_STRINGS_PER_PAGE: Final = 120


class _Budget:
    def __init__(self, limit: int):
        self._remaining = limit

    def spend(self) -> None:
        if self._remaining <= 0:
            raise ValidationAppError(
                f"This page has more than {_MAX_STRINGS_PER_PAGE} translatable strings —"
                " too many to auto-translate in one pass. Translate it in sections by hand."
            )
        self._remaining -= 1


async def _translate_string(translator: Translator, value: str, target_lang: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        return value
    return await translator.translate(value, target_lang=target_lang)


async def _translate_node(
    translator: Translator, node: Any, target_lang: str, budget: _Budget
) -> Any:
    if isinstance(node, dict):
        translated: dict[str, Any] = {}
        for key, value in node.items():
            if key in _TRANSLATABLE_KEYS and isinstance(value, str):
                budget.spend()
                translated[key] = await _translate_string(translator, value, target_lang)
            elif key in _TRANSLATABLE_STRING_LIST_KEYS and isinstance(value, list):
                items = []
                for entry in value:
                    if isinstance(entry, str):
                        budget.spend()
                        items.append(await _translate_string(translator, entry, target_lang))
                    else:
                        items.append(entry)
                translated[key] = items
            else:
                translated[key] = await _translate_node(translator, value, target_lang, budget)
        return translated
    if isinstance(node, list):
        return [await _translate_node(translator, item, target_lang, budget) for item in node]
    return node


async def _current_published_blocks(db: Database, page_id: str) -> dict[str, Any]:
    page = await db.fetch_one(
        "SELECT p.id, v.content_json FROM pages p"
        " LEFT JOIN page_versions v ON v.id = p.published_version_id"
        " WHERE p.id = ? AND p.archived_at IS NULL",
        (page_id,),
    )
    if page is None:
        raise NotFoundError("Page not found.")
    return json.loads(page["content_json"] or '{"blocks":[]}')


async def get_page_translation(db: Database, page_id: str, locale: str) -> dict[str, Any] | None:
    return await PageTranslationRepository(db).get(page_id, locale)


async def list_page_translations(db: Database, page_id: str) -> list[dict[str, Any]]:
    return await PageTranslationRepository(db).list_for_page(page_id)


async def save_page_translation(
    db: Database,
    actor: Principal,
    request_id: str,
    page_id: str,
    locale: str,
    content: dict[str, Any],
    *,
    auto_translated: bool,
) -> dict[str, Any]:
    page = await db.fetch_one(
        "SELECT id FROM pages WHERE id = ? AND archived_at IS NULL", (page_id,)
    )
    if page is None:
        raise NotFoundError("Page not found.")
    blocks = content.get("blocks") if isinstance(content, dict) else None
    validated = validate_blocks(blocks if blocks is not None else [])
    stored_json = json.dumps(
        {
            "blocks": [
                block.model_dump(mode="json", by_alias=True, exclude_none=True)
                for block in validated
            ]
        }
    )

    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO page_content_translations"
                " (page_id, locale, content_json, auto_translated, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?)"
                " ON CONFLICT(page_id, locale) DO UPDATE SET"
                "  content_json = excluded.content_json,"
                "  auto_translated = excluded.auto_translated,"
                "  updated_at = excluded.updated_at,"
                "  updated_by = excluded.updated_by",
                (page_id, locale, stored_json, 1 if auto_translated else 0, now, actor.user_id),
            ),
            audit_statement(
                action="page_translation.saved",
                entity_type="page",
                entity_id=page_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"locale": locale, "autoTranslated": auto_translated},
            ),
        ]
    )
    saved = await PageTranslationRepository(db).get(page_id, locale)
    assert saved is not None
    return saved


async def delete_page_translation(db: Database, page_id: str, locale: str) -> None:
    await db.execute(
        "DELETE FROM page_content_translations WHERE page_id = ? AND locale = ?",
        (page_id, locale),
    )


async def auto_translate_page(
    db: Database,
    actor: Principal,
    request_id: str,
    translator: Translator,
    page_id: str,
    locale: str,
) -> dict[str, Any]:
    """Machine-translate the page's current published content into `locale`
    and store it, flagged `auto_translated` so the editor reads as a draft to
    review, not a finished translation. Overwrites any existing translation
    for this locale -- re-running it is how an editor gets a fresh
    machine-translated starting point after the English content changes."""
    content = await _current_published_blocks(db, page_id)
    budget = _Budget(_MAX_STRINGS_PER_PAGE)
    translated_content = await _translate_node(translator, content, locale, budget)
    return await save_page_translation(
        db, actor, request_id, page_id, locale, translated_content, auto_translated=True
    )

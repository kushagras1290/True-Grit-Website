"""Read-only queries for per-locale CMS page content (migration 0067).
Writes live in `services.translation`, matching every other repository in
this codebase.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database


class PageTranslationRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get(self, page_id: str, locale: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT page_id, locale, content_json, auto_translated, updated_at, updated_by"
            " FROM page_content_translations WHERE page_id = ? AND locale = ?",
            (page_id, locale),
        )

    async def list_for_page(self, page_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT locale, auto_translated, updated_at"
            " FROM page_content_translations WHERE page_id = ? ORDER BY locale",
            (page_id,),
        )

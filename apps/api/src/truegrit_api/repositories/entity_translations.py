"""Read-only queries for per-locale field overrides on database-sourced
content (migration 0068). Writes live in `services.entity_translation`,
matching every other repository in this codebase.
"""

from __future__ import annotations

import json
from typing import Any

from truegrit_api.platform.database import Database


class EntityTranslationRepository:
    def __init__(self, db: Database):
        self._db = db

    async def get(self, entity_type: str, entity_id: str, locale: str) -> dict[str, Any] | None:
        row = await self._db.fetch_one(
            "SELECT entity_type, entity_id, locale, fields_json, auto_translated,"
            " updated_at, updated_by"
            " FROM entity_translations WHERE entity_type = ? AND entity_id = ? AND locale = ?",
            (entity_type, entity_id, locale),
        )
        if row is None:
            return None
        return {**row, "fields": json.loads(row["fields_json"])}

    async def list_for_entity(self, entity_type: str, entity_id: str) -> list[dict[str, Any]]:
        return await self._db.fetch_all(
            "SELECT locale, auto_translated, updated_at FROM entity_translations"
            " WHERE entity_type = ? AND entity_id = ? ORDER BY locale",
            (entity_type, entity_id),
        )

    async def get_fields_map(
        self, entity_type: str, entity_ids: list[str], locale: str
    ) -> dict[str, dict[str, Any]]:
        """`{entity_id: fields}` for every id in `entity_ids` that has a saved
        translation in `locale` -- one query for a whole listing page, so a
        category grid or nav menu never issues N lookups for N rows."""
        if not entity_ids:
            return {}
        placeholders = ",".join("?" for _ in entity_ids)
        rows = await self._db.fetch_all(
            f"SELECT entity_id, fields_json FROM entity_translations"
            f" WHERE entity_type = ? AND locale = ? AND entity_id IN ({placeholders})",
            (entity_type, locale, *entity_ids),
        )
        return {row["entity_id"]: json.loads(row["fields_json"]) for row in rows}

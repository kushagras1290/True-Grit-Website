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
        runtime_rows = await self._db.fetch_all(
            "SELECT field_key, translated_text, status, updated_at, updated_by"
            " FROM translation_entries WHERE resource_type = ? AND resource_id = ?"
            " AND locale = ? AND field_key NOT LIKE '%/%'",
            (entity_type, entity_id, locale),
        )
        if row is None and not runtime_rows:
            return None
        fields = json.loads(row["fields_json"]) if row is not None else {}
        fields.update({entry["field_key"]: entry["translated_text"] for entry in runtime_rows})
        latest = max(runtime_rows, key=lambda entry: entry["updated_at"]) if runtime_rows else None
        return {
            **(row or {}),
            "entity_type": entity_type,
            "entity_id": entity_id,
            "locale": locale,
            "auto_translated": (
                row["auto_translated"]
                if row is not None
                else (1 if latest and latest["status"] == "machine" else 0)
            ),
            "updated_at": latest["updated_at"] if latest else row["updated_at"],
            "updated_by": latest["updated_by"] if latest else row["updated_by"],
            "fields": fields,
        }

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
        result = {row["entity_id"]: json.loads(row["fields_json"]) for row in rows}
        runtime_rows = await self._db.fetch_all(
            f"SELECT resource_id, field_key, translated_text FROM translation_entries"
            f" WHERE resource_type = ? AND locale = ? AND field_key NOT LIKE '%/%'"
            f" AND resource_id IN ({placeholders})",
            (entity_type, locale, *entity_ids),
        )
        for entry in runtime_rows:
            result.setdefault(entry["resource_id"], {})[entry["field_key"]] = entry[
                "translated_text"
            ]
        return result

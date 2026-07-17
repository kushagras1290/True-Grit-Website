"""Media asset repository: the D1 `media_assets` table is the library's
source of truth. R2 (or the local filesystem in dev) only holds the bytes;
`object_key` is the join between the two.
"""

from __future__ import annotations

from typing import Any

from truegrit_api.platform.database import Database

# Every column with a foreign key onto media_assets(id) — checked before a
# hard delete so an in-use image is never silently unlinked.
_REFERENCING_COLUMNS = (
    ("pages", "social_media_id"),
    ("articles", "hero_media_id"),
    ("recipes", "hero_media_id"),
    ("farms", "hero_media_id"),
    ("products", "primary_media_id"),
)


class MediaRepository:
    def __init__(self, db: Database):
        self._db = db

    async def list_all(self, *, limit: int = 60, offset: int = 0, search: str | None = None) -> list[dict[str, Any]]:
        where_clause = ""
        params: list[Any] = []
        if search:
            where_clause = "WHERE original_filename LIKE ? OR alt_text LIKE ?"
            params.extend([f"%{search}%", f"%{search}%"])
            
        params.extend([min(max(limit, 1), 200), max(offset, 0)])
        
        return await self._db.fetch_all(
            f"""
            SELECT id, object_key, original_filename, mime_type, size_bytes,
                   width_px, height_px, alt_text, caption, visibility,
                   processing_status, created_at, created_by, updated_at
            FROM media_assets
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    async def get(self, media_id: str) -> dict[str, Any] | None:
        return await self._db.fetch_one(
            "SELECT * FROM media_assets WHERE id = ?", (media_id,)
        )

    async def references(self, media_id: str) -> list[str]:
        """Human-readable labels for every record still pointing at this
        asset — empty if it is safe to delete."""
        found: list[str] = []
        for table, column in _REFERENCING_COLUMNS:
            row = await self._db.fetch_one(
                f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = ?", (media_id,)
            )
            if row and int(row["n"]) > 0:
                found.append(f"{int(row['n'])} {table.replace('_', ' ')}")
        return found

"""Admin media uploads and library management.

Images are stored through the app's ``MediaStore`` — Cloudflare R2 in the
Workers runtime, the local filesystem in development — and served back from
the API under ``/media``. Every stored object also gets a ``media_assets``
row, which is the library's source of truth for listing, alt text, and
deletion; the store only ever holds bytes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import base64
import binascii

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database, repo_root
from truegrit_api.platform.media_store import MediaStore
from truegrit_api.repositories.media import MediaRepository
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def media_root() -> Path:
    return repo_root() / "apps" / "api" / ".media"


async def save_image_upload(
    store: MediaStore,
    db: Database,
    actor: Principal,
    *,
    content_type: str,
    data_base64: str,
    original_filename: str | None = None,
) -> dict[str, str]:
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationAppError("The uploaded image could not be decoded.") from exc
    return await save_image_bytes(
        store, db, actor, content_type=content_type, data=raw, original_filename=original_filename
    )


async def save_image_bytes(
    store: MediaStore,
    db: Database,
    actor: Principal,
    *,
    content_type: str,
    data: bytes,
    original_filename: str | None = None,
) -> dict[str, str]:
    extension = _IMAGE_TYPES.get(content_type)
    if extension is None:
        raise ValidationAppError("Upload a JPG, PNG, WebP, or GIF image.")
    if not data:
        raise ValidationAppError("The uploaded image is empty.")
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValidationAppError("Images must be 5 MB or smaller.")

    image_id = new_id("med")
    key = f"images/{image_id}{extension}"
    await store.put(key, data, content_type)

    now = utc_now_iso()
    await db.execute(
        "INSERT INTO media_assets"
        " (id, object_key, original_filename, mime_type, size_bytes, alt_text,"
        "  visibility, processing_status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, ?, NULL, 'public', 'ready', ?, ?, ?, ?)",
        (
            image_id,
            key,
            (original_filename or f"{image_id}{extension}")[:180],
            content_type,
            len(data),
            now,
            actor.user_id,
            now,
            actor.user_id,
        ),
    )
    return {"id": image_id, "path": f"/media/{key}"}


async def list_media(db: Database, *, limit: int = 60, offset: int = 0) -> list[dict[str, Any]]:
    return await MediaRepository(db).list_all(limit=limit, offset=offset)


async def update_media(
    db: Database,
    actor: Principal,
    request_id: str,
    media_id: str,
    *,
    alt_text: str | None = None,
    caption: str | None = None,
) -> dict[str, Any]:
    repo = MediaRepository(db)
    current = await repo.get(media_id)
    if current is None:
        raise NotFoundError("Media asset not found.")

    now = utc_now_iso()
    updates: dict[str, Any] = {"updated_at": now, "updated_by": actor.user_id}
    if alt_text is not None:
        updates["alt_text"] = alt_text.strip()[:300] or None
    if caption is not None:
        updates["caption"] = caption.strip()[:500] or None
    assignments = ", ".join(f"{key} = ?" for key in updates)
    await db.batch(
        [
            (f"UPDATE media_assets SET {assignments} WHERE id = ?", (*updates.values(), media_id)),
            audit_statement(
                action="media.updated",
                entity_type="media_asset",
                entity_id=media_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"altText": updates.get("alt_text"), "caption": updates.get("caption")},
            ),
        ]
    )
    updated = await repo.get(media_id)
    assert updated is not None
    return updated


async def delete_media(
    store: MediaStore, db: Database, actor: Principal, request_id: str, media_id: str
) -> None:
    repo = MediaRepository(db)
    current = await repo.get(media_id)
    if current is None:
        raise NotFoundError("Media asset not found.")
    used_by = await repo.references(media_id)
    if used_by:
        raise ConflictError(f"This image is still used by {', '.join(used_by)}.")

    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM media_assets WHERE id = ?", (media_id,)),
            audit_statement(
                action="media.deleted",
                entity_type="media_asset",
                entity_id=media_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"objectKey": current["object_key"]},
            ),
        ]
    )
    await store.delete(current["object_key"])

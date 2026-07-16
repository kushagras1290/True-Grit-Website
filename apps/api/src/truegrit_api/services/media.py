"""Admin media uploads.

Images are stored through the app's ``MediaStore`` — Cloudflare R2 in the
Workers runtime, the local filesystem in development — and served back from the
API under ``/media``. The admin UI only needs the final public URL.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import repo_root
from truegrit_api.platform.media_store import MediaStore
from truegrit_api.util.ids import new_id

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
    store: MediaStore, *, content_type: str, data_base64: str
) -> dict[str, str]:
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationAppError("The uploaded image could not be decoded.") from exc
    return await save_image_bytes(store, content_type=content_type, data=raw)


async def save_image_bytes(store: MediaStore, *, content_type: str, data: bytes) -> dict[str, str]:
    extension = _IMAGE_TYPES.get(content_type)
    if extension is None:
        raise ValidationAppError("Upload a JPG, PNG, WebP, or GIF image.")
    if not data:
        raise ValidationAppError("The uploaded image is empty.")
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValidationAppError("Images must be 5 MB or smaller.")

    image_id = new_id("img")
    key = f"images/{image_id}{extension}"
    await store.put(key, data, content_type)
    return {"id": image_id, "path": f"/media/{key}"}

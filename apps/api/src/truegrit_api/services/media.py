"""Admin media uploads.

Local development writes images to ``apps/api/.media`` and serves them from the
API origin. Production can replace this service with Cloudflare Images or R2
without changing the admin UI contract: it only needs a final public URL.
"""

from __future__ import annotations

import base64
import binascii
from pathlib import Path

from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import repo_root
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


def save_image_upload(*, content_type: str, data_base64: str) -> dict[str, str]:
    extension = _IMAGE_TYPES.get(content_type)
    if extension is None:
        raise ValidationAppError("Upload a JPG, PNG, WebP, or GIF image.")
    try:
        raw = base64.b64decode(data_base64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValidationAppError("The uploaded image could not be decoded.") from exc
    if not raw:
        raise ValidationAppError("The uploaded image is empty.")
    if len(raw) > _MAX_IMAGE_BYTES:
        raise ValidationAppError("Images must be 5 MB or smaller.")

    image_id = new_id("img")
    filename = f"{image_id}{extension}"
    target_dir = media_root() / "images"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / filename).write_bytes(raw)
    return {"id": image_id, "path": f"/media/images/{filename}"}

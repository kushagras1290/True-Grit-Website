"""Media object storage.

One protocol, two interchangeable backends: Cloudflare R2 inside the Workers
runtime, and the local filesystem for development and tests. Business code
(``services.media`` and the ``/media`` route) depends only on ``MediaStore``.

Kept import-safe outside Workers: the Pyodide-only imports (``pyodide.ffi``)
live inside methods, never at module load.
"""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path
from typing import Any, Protocol

# Explicit map first so uploaded image types resolve identically on every host
# (stdlib mimetypes does not know webp on some platforms).
_EXT_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
}


def content_type_for(key: str) -> str:
    """Best-effort MIME type from a stored object key's extension."""
    ext = os.path.splitext(key)[1].lower()
    return _EXT_CONTENT_TYPES.get(ext) or mimetypes.guess_type(key)[0] or "application/octet-stream"


class MediaStore(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def get(self, key: str) -> tuple[bytes, str] | None:
        """Return ``(bytes, content_type)`` for ``key`` or ``None`` if absent."""
        ...

    async def delete(self, key: str) -> None:
        """Remove the object at ``key``. A no-op if it does not exist."""
        ...


class LocalMediaStore:
    """Filesystem-backed store for local development and tests."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        return self._root / key

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)

    async def get(self, key: str) -> tuple[bytes, str] | None:
        target = self._path(key)
        if not target.is_file():
            return None
        return target.read_bytes(), content_type_for(key)

    async def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


class R2MediaStore:
    """Cloudflare R2-backed store, wrapping the ``env.MEDIA_BUCKET`` binding."""

    def __init__(self, bucket: Any) -> None:
        self._bucket = bucket

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        from pyodide.ffi import to_js  # runtime-provided (Pyodide)

        # to_js turns Python bytes into a JS Uint8Array, an accepted R2 put body.
        await self._bucket.put(key, to_js(data))

    async def get(self, key: str) -> tuple[bytes, str] | None:
        obj = await self._bucket.get(key)
        if obj is None:  # Pyodide maps JS null -> None
            return None
        buffer = await obj.arrayBuffer()
        # Depending on the runtime, arrayBuffer() yields a Pyodide JsProxy
        # (needs .to_py()) or an already-converted memoryview/bytes.
        to_py = getattr(buffer, "to_py", None)
        raw = to_py() if callable(to_py) else buffer
        return bytes(raw), content_type_for(key)

    async def delete(self, key: str) -> None:
        await self._bucket.delete(key)

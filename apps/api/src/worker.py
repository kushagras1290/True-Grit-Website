"""Cloudflare Python Workers entry point.

This module lives at ``src/worker.py`` (outside the ``truegrit_api`` package) on
purpose: Cloudflare bundles the directory that contains ``main`` as the module
root, so keeping the entry one level up makes ``truegrit_api`` a real importable
package inside the Worker. Placing the entry inside the package instead flattens
its contents to the bundle root and breaks every ``import truegrit_api.*``.

Deployed with ``pywrangler`` (the ``workers-py`` CLI), which bundles FastAPI,
pydantic, and the Workers runtime SDK (the ``workers`` and ``asgi`` modules)
into the Worker. Only this thin adapter is Workers-specific; the FastAPI
application is portable business code (ADR-003). The ASGI bridge follows
https://developers.cloudflare.com/workers/languages/python/packages/fastapi/.
"""

import hashlib
import os
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import asgi
from workers import WorkerEntrypoint

from truegrit_api.config import Settings
from truegrit_api.main import create_app
from truegrit_api.platform.d1 import D1Database
from truegrit_api.platform.media_store import R2MediaStore

# Build the FastAPI application once per isolate. The D1 binding is resolved
# from ``env`` on first request (it is not available at module-import time) and
# reused for the isolate's lifetime.
_app: Any = None

_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_IMAGE_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _to_py(value: Any) -> Any:
    to_py = getattr(value, "to_py", None)
    return to_py() if callable(to_py) else value


def _bridge_worker_env(env: Any) -> None:
    """Expose Worker ``vars``/secrets to pydantic settings.

    On Cloudflare Python Workers, configuration values live on the ``env``
    object, not the process environment — but ``Settings`` (pydantic-settings)
    reads ``os.environ``. Without this bridge every setting would silently fall
    back to its default (localhost CORS origins, Google sign-in disabled, etc.).
    Each Settings field is matched to an upper-cased Worker var; only string
    values are copied, so bindings (DB, R2, KV, Queues) are ignored.
    """
    for field_name in Settings.model_fields:
        key = field_name.upper()
        try:
            value = getattr(env, key)
        except AttributeError:
            continue
        if isinstance(value, str):
            os.environ[key] = value


def _response(body: str, status: int, headers: dict[str, str]) -> Any:
    from js import Response
    from pyodide.ffi import to_js

    return Response.new(body, to_js({"status": status, "headers": headers}))


def _json_response(body: str, status: int, headers: dict[str, str]) -> Any:
    return _response(body, status, {**headers, "content-type": "application/json"})


def _cors_headers(env: Any, request: Any) -> dict[str, str]:
    origin = str(request.headers.get("origin") or "")
    allowed = {
        getattr(env, "PUBLIC_ADMIN_URL", ""),
        getattr(env, "PUBLIC_STOREFRONT_URL", ""),
    }
    headers = {"vary": "Origin"}
    if origin in allowed:
        headers.update(
            {
                "access-control-allow-origin": origin,
                "access-control-allow-credentials": "true",
            }
        )
    return headers


def _cookie_value(request: Any, name: str) -> str | None:
    cookie_header = request.headers.get("cookie") or ""
    for item in cookie_header.split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return None


async def _can_upload_media(env: Any, token: str) -> bool:
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = await env.DB.prepare(
        """
        SELECT u.id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.revoked_at IS NULL
          AND s.expires_at > ?
          AND u.status = 'active'
        """
    ).bind(token_hash, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")).first()
    row = _to_py(row)
    if row is None:
        return False
    user_id = dict(row)["id"]
    permission = await env.DB.prepare(
        """
        SELECT 1
        FROM user_roles ur
        JOIN role_permissions rp ON rp.role_id = ur.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE ur.user_id = ? AND p.key = 'media.upload'
        LIMIT 1
        """
    ).bind(user_id).first()
    return permission is not None


async def _upload_media_direct(env: Any, request: Any) -> Any:
    from js import Response
    from pyodide.ffi import to_js

    headers = _cors_headers(env, request)
    method = str(request.method).upper()
    if method == "OPTIONS":
        return _response(
            "",
            204,
            {
                **headers,
                "access-control-allow-methods": "POST, OPTIONS",
                "access-control-allow-headers": "content-type",
                "access-control-max-age": "86400",
            },
        )

    content_type = str(request.headers.get("content-type") or "").split(";", 1)[0].lower()
    extension = _IMAGE_TYPES.get(content_type)
    if extension is None:
        return _json_response('{"detail":"Upload a JPG, PNG, WebP, or GIF image."}', 422, headers)

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            size = int(content_length)
        except ValueError:
            size = -1
        if size <= 0:
            return _json_response('{"detail":"The uploaded image is empty."}', 422, headers)
        if size > _MAX_IMAGE_BYTES:
            return _json_response('{"detail":"Images must be 5 MB or smaller."}', 422, headers)

    token = _cookie_value(request, getattr(env, "SESSION_COOKIE_NAME", "tg_session"))
    if token is None or not await _can_upload_media(env, token):
        return _json_response('{"detail":"Unauthorized"}', 401, headers)

    image_id = f"img_{secrets.token_urlsafe(16)}"
    key = f"images/{image_id}{extension}"
    await env.MEDIA_BUCKET.put(
        key,
        request.body,
        to_js({"httpMetadata": {"contentType": content_type}}),
    )
    base_url = (
        urlparse(str(request.url))._replace(path="", params="", query="", fragment="").geturl()
    )
    return Response.new(
        f'{{"id":"{image_id}","url":"{base_url}/media/{key}"}}',
        to_js({"status": 200, "headers": {**headers, "content-type": "application/json"}}),
    )


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        global _app
        path = urlparse(str(request.url)).path
        method = str(request.method).upper()
        if path == "/v1/admin/media/images" and method in {"POST", "OPTIONS"}:
            return await _upload_media_direct(self.env, request)
        if _app is None:
            _bridge_worker_env(self.env)
            _app = create_app(
                db=D1Database(self.env.DB),
                media=R2MediaStore(self.env.MEDIA_BUCKET),
            )
        return await asgi.fetch(_app, request, self.env)

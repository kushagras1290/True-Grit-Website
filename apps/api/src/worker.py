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
import secrets
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs, urlparse

import asgi
from workers import WorkerEntrypoint

from truegrit_api.config import Settings
from truegrit_api.main import create_app
from truegrit_api.platform.ai_chat import WorkersAIChat
from truegrit_api.platform.d1 import D1Database
from truegrit_api.platform.media_store import R2MediaStore
from truegrit_api.platform.translation import WorkersAITranslator
from truegrit_api.platform.worker_env import bridge_worker_env as _bridge_worker_env

# Re-exported (not just imported): wrangler resolves Durable Object classes
# by name on this entry module, so ChatRoomDO must be a top-level attribute
# here even though nothing in this file calls it directly.
from truegrit_api.realtime.chat_room import ChatRoomDO as ChatRoomDO
from truegrit_api.util.cookies import cookie_value as _cookie_value

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


class _WorkersQueuePublisher:
    def __init__(self, binding: Any) -> None:
        self._binding = binding

    async def send(self, message: dict[str, Any]) -> None:
        await self._binding.send(message)


def _to_py(value: Any) -> Any:
    to_py = getattr(value, "to_py", None)
    return to_py() if callable(to_py) else value


def _js_object(value: Any) -> Any:
    """Convert a Python dict tree into plain JS objects.

    Pyodide's default ``to_js`` turns a dict into a JS ``Map``, which the web
    platform APIs used here read as an object with **no** properties: a
    ``Response`` built with a Map init drops the status *and every header*
    (including Access-Control-Allow-Origin, so the browser reports the request
    as a CORS failure), and an R2 ``put`` with Map options loses its
    httpMetadata. ``Object.fromEntries`` is the documented Workers pattern.
    """
    from js import Object
    from pyodide.ffi import to_js

    return to_js(value, dict_converter=Object.fromEntries)


def _response(body: str, status: int, headers: dict[str, str]) -> Any:
    from js import Response

    return Response.new(body, _js_object({"status": status, "headers": headers}))


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


async def _authorized_media_uploader(env: Any, token: str) -> str | None:
    """The uploading user's id, or None if the session is missing/expired or
    lacks `media.upload`. Returning the id (not just a bool) lets the direct
    upload path below attribute the `media_assets` row it writes."""
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    row = (
        await env.DB.prepare(
            """
        SELECT u.id
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.revoked_at IS NULL
          AND s.expires_at > ?
          AND u.status = 'active'
        """
        )
        .bind(token_hash, datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
        .first()
    )
    row = _to_py(row)
    if row is None:
        return None
    user_id = dict(row)["id"]
    permission = (
        await env.DB.prepare(
            """
        SELECT 1
        FROM user_roles ur
        JOIN role_permissions rp ON rp.role_id = ur.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE ur.user_id = ? AND p.key = 'media.upload'
        LIMIT 1
        """
        )
        .bind(user_id)
        .first()
    )
    return user_id if permission is not None else None


async def _upload_media_direct(env: Any, request: Any) -> Any:
    from js import Response

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
    size_bytes = 0
    if content_length is not None:
        try:
            size_bytes = int(content_length)
        except ValueError:
            size_bytes = -1
        if size_bytes <= 0:
            return _json_response('{"detail":"The uploaded image is empty."}', 422, headers)
        if size_bytes > _MAX_IMAGE_BYTES:
            return _json_response('{"detail":"Images must be 5 MB or smaller."}', 422, headers)

    token = _cookie_value(request, getattr(env, "SESSION_COOKIE_NAME", "tg_session"))
    user_id = await _authorized_media_uploader(env, token) if token else None
    if user_id is None:
        return _json_response('{"detail":"Unauthorized"}', 401, headers)

    image_id = f"img_{secrets.token_urlsafe(16)}"
    key = f"images/{image_id}{extension}"
    await env.MEDIA_BUCKET.put(
        key,
        request.body,
        _js_object({"httpMetadata": {"contentType": content_type}}),
    )

    # This bypasses the FastAPI /v1/admin/media/images route entirely (see
    # Default.fetch below) to stay under Python Workers' CPU budget for real
    # photos, but that means it must do that route's other job itself: without
    # this insert the object lands in R2 with no `media_assets` row, and the
    # Media Library — which lists from that table, not from the bucket — would
    # never show it.
    query = parse_qs(urlparse(str(request.url)).query)
    original_filename = (query.get("filename") or [f"{image_id}{extension}"])[0][:180]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    await (
        env.DB.prepare(
            """
        INSERT INTO media_assets
          (id, object_key, original_filename, mime_type, size_bytes, alt_text,
           visibility, processing_status, created_at, created_by, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, NULL, 'public', 'ready', ?, ?, ?, ?)
        """
        )
        .bind(
            image_id,
            key,
            original_filename,
            content_type,
            max(size_bytes, 0),
            now,
            user_id,
            now,
            user_id,
        )
        .run()
    )

    return Response.new(
        f'{{"id":"{image_id}","url":"/media/{key}"}}',
        _js_object({"status": 200, "headers": {**headers, "content-type": "application/json"}}),
    )


async def _serve_media_direct(env: Any, request: Any, path: str) -> Any:
    """Stream a media object straight from R2, bypassing FastAPI/Pyodide.

    Serving images through the ASGI app converts every byte JS -> Python ->
    JS, which for real photos burns enough CPU that Cloudflare kills the
    isolate (`exceededCpu` in the Worker logs). The platform's 503 carries no
    Access-Control-Allow-Origin header, so the admin/storefront see the whole
    image-change flow die as a "CORS error". Media is public, so a wildcard
    origin is safe — the response never varies on credentials.
    """
    from js import Response

    headers = {"access-control-allow-origin": "*"}
    method = str(request.method).upper()
    if method == "OPTIONS":
        return _response(
            "",
            204,
            {
                **headers,
                "access-control-allow-methods": "GET, HEAD, OPTIONS",
                "access-control-allow-headers": "content-type",
                "access-control-max-age": "86400",
            },
        )

    from truegrit_api.platform.media_store import content_type_for

    key = path[len("/media/") :]
    obj = await env.MEDIA_BUCKET.get(key)
    if obj is None:
        return _json_response('{"detail":"Media not found."}', 404, headers)
    response_headers = {
        **headers,
        "content-type": content_type_for(key),
        "content-length": str(obj.size),
        "cache-control": "public, max-age=86400",
        "etag": str(obj.httpEtag),
    }
    body = None if method == "HEAD" else obj.body
    return Response.new(body, _js_object({"status": 200, "headers": response_headers}))


class Default(WorkerEntrypoint):
    async def scheduled(self, controller: Any, env: Any = None, ctx: Any = None) -> None:
        """Cloudflare Cron Trigger entry point (see `triggers.crons` in
        wrangler.jsonc) -- places one renewal order for every Subscribe & Save
        subscription due today, via the identical code path the admin's
        manual "run renewals now" button also calls
        (`services.subscriptions.run_due_renewals`). A no-op whenever the
        sitewide subscriptions switch is off, so this cron firing on a store
        that has never turned the feature on costs one cheap settings read.

        Deliberately does not build the FastAPI app or go through ASGI at
        all -- a scheduled event is not an HTTP request, so this talks to D1
        directly, the same way `_upload_media_direct`/`_serve_media_direct`
        bypass ASGI for their own non-request-shaped work. Any failure is
        logged and swallowed: a cron isolate has no browser waiting on a
        response, and the batch itself already isolates and records each
        subscription's own outcome (see run_due_renewals), so there is
        nothing left here that a retry would fix that tomorrow's run will
        not already retry on its own.
        """
        from truegrit_api.platform.d1 import D1Database
        from truegrit_api.services.jobs import dispatch_pending_outbox
        from truegrit_api.services.subscriptions import run_due_renewals
        from truegrit_api.util.ids import new_request_id

        try:
            _bridge_worker_env(self.env)
            db = D1Database(self.env.DB)
            dispatched = await dispatch_pending_outbox(
                db, _WorkersQueuePublisher(self.env.JOBS_QUEUE)
            )
            print(
                "outbox.scheduled: "
                f"{dispatched['published']}/{dispatched['selected']} published, "
                f"{dispatched['failed']} failed"
            )
            if str(getattr(controller, "cron", "")) == "0 3 * * *":
                result = await run_due_renewals(db, new_request_id())
                print(
                    f"subscriptions.scheduled: {result['succeeded']}/{result['processed']} renewed"
                )
        except Exception as exc:
            print(f"subscriptions.scheduled crashed: {type(exc).__name__}: {exc}")

    async def queue(self, batch: Any, env: Any = None, ctx: Any = None) -> None:
        """Consume jobs idempotently and retain exhausted messages from the DLQ."""
        import json

        from truegrit_api.services.email import OutboundEmail
        from truegrit_api.services.jobs import process_queue_job, retain_dead_letter

        _bridge_worker_env(self.env)
        db = D1Database(self.env.DB)
        queue_name = str(getattr(batch, "queue", ""))
        messages = batch.messages

        async def invalidate_cache(aggregate_type: str, aggregate_id: str) -> None:
            await self.env.CACHE.put(
                f"cache-version:{aggregate_type}:{aggregate_id}",
                datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            )

        async def deliver_email(email: OutboundEmail, idempotency_key: str) -> bool:
            settings = Settings()
            if not settings.resend_api_key:
                print("queue.email_unconfigured: RESEND_API_KEY is required")
                return False
            from js import fetch

            payload: dict[str, Any] = {
                "from": settings.email_from,
                "to": [email.to],
                "subject": email.subject,
                "text": email.body,
            }
            if email.html_body:
                payload["html"] = email.html_body
            response = await fetch(
                settings.resend_api_url,
                _js_object(
                    {
                        "method": "POST",
                        "headers": {
                            "authorization": f"Bearer {settings.resend_api_key}",
                            "content-type": "application/json",
                            "idempotency-key": idempotency_key,
                        },
                        "body": json.dumps(payload),
                    }
                ),
            )
            return bool(response.ok)

        for raw_message in messages:
            message = raw_message
            body = _to_py(message.body)
            payload = dict(_to_py(body)) if body is not None else {}
            try:
                if "dlq" in queue_name.lower():
                    await retain_dead_letter(db, payload, "Queue delivery retries exhausted.")
                    message.ack()
                    print(f"queue.dead_letter_retained: {payload.get('idempotencyKey', 'unknown')}")
                    continue
                outcome = await process_queue_job(
                    db,
                    payload,
                    deliver_email=deliver_email,
                    invalidate_cache=invalidate_cache,
                )
                message.ack()
                print(f"queue.job_{outcome}: {payload.get('idempotencyKey', 'unknown')}")
            except Exception as exc:
                print(
                    "queue.job_failed: "
                    f"{payload.get('idempotencyKey', 'unknown')} "
                    f"{type(exc).__name__}"
                )
                message.retry()

    async def fetch(self, request: Any) -> Any:
        global _app
        path = urlparse(str(request.url)).path
        method = str(request.method).upper()
        try:
            if path == "/v1/admin/media/images" and method in {"POST", "OPTIONS"}:
                return await _upload_media_direct(self.env, request)
            if path.startswith("/media/") and method in {"GET", "HEAD", "OPTIONS"}:
                return await _serve_media_direct(self.env, request, path)
            if path.startswith("/v1/admin/messages/realtime/") and method == "GET":
                # WebSocket upgrades cannot go through the FastAPI/ASGI bridge
                # (asgi.fetch is request/response-shaped, not upgrade-aware) --
                # forward straight to the conversation's Durable Object, which
                # performs its own auth/membership check and accepts the
                # upgrade itself. Same "bypass ASGI for non-request-shaped
                # work" reasoning as the media helpers above.
                conversation_id = path.rsplit("/", 1)[-1]
                # CHAT_ROOMS is a raw JS DurableObjectNamespace binding
                # (Pyodide interop, like env.DB/env.MEDIA_BUCKET elsewhere in
                # this file) -- its methods keep their native JS camelCase
                # names; there is no Python-side getByName -> get_by_name
                # rewrite the way DurableObjectState's own helper methods get.
                stub = self.env.CHAT_ROOMS.getByName(conversation_id)
                return await stub.fetch(request)
            # Binding-only deployments may reuse this isolate. Refresh text
            # vars/secrets for every ASGI request so rotated credentials do not
            # remain trapped in pydantic's process-global settings cache.
            _bridge_worker_env(self.env)
            if _app is None:
                # `AI` is optional in wrangler.jsonc's binding list -- an
                # older deploy that predates auto-translate (migration 0067)
                # simply has no `env.AI`, and getattr(..., None) degrades to
                # UnavailableTranslator (auth/dependencies.py) rather than
                # crashing cold start.
                ai_binding = getattr(self.env, "AI", None)
                _app = create_app(
                    db=D1Database(self.env.DB),
                    media=R2MediaStore(self.env.MEDIA_BUCKET),
                    translator=WorkersAITranslator(ai_binding) if ai_binding is not None else None,
                    chat=WorkersAIChat(ai_binding) if ai_binding is not None else None,
                )
            return await asgi.fetch(_app, request, self.env)
        except Exception as exc:
            # Everything inside the try — isolate cold start, the D1/R2 binding
            # lookups, and asgi.fetch() itself — runs outside FastAPI's own
            # exception handlers (truegrit_api.middleware.error_handler), which
            # only see exceptions raised *inside* the ASGI app. A crash here
            # would otherwise reach the browser as a bare platform error with no
            # Access-Control-Allow-Origin header, which Chrome reports as
            # "blocked by CORS policy" and masks the real failure. Answer with
            # genuine CORS headers so the UI sees an honest 500 instead.
            _app = None  # drop a possibly half-built app; rebuild next request
            print(f"worker.fetch crashed: {type(exc).__name__}: {exc}")
            return _json_response(
                '{"error":{"code":"internal_error","message":"Something went wrong."}}',
                500,
                _cors_headers(self.env, request),
            )

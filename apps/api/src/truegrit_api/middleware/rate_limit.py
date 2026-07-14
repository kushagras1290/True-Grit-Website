"""Global per-IP request ceiling — a stability backstop for every route.

Deliberately in-memory and fixed-window: under a flood the limiter must stay
O(1) and must not amplify traffic into database load (a DB-backed global counter
would make an attack worse). It complements — does not replace — the durable,
DB-backed limits on authentication endpoints, which defend against slow
brute-force across isolates.

Scope note: on Cloudflare Workers each isolate holds its own counter, so this is
a per-isolate guard; put Cloudflare's edge rate limiting in front for a hard,
account-wide cap. Locally (single uvicorn process) it is a true global limit.
"""

from __future__ import annotations

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from truegrit_api.auth.rate_limit import client_ip
from truegrit_api.config import get_settings

# Paths exempt from the global ceiling: liveness probes must never be throttled.
_EXEMPT_PATHS = frozenset({"/health/live"})
# Prune the bucket map once it grows past this many distinct IPs.
_PRUNE_THRESHOLD = 10_000


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        settings = get_settings()
        self._enabled = settings.rate_limit_enabled
        self._limit = settings.rate_limit_global_per_ip
        self._window = float(settings.rate_limit_global_window_seconds)
        # ip -> (window_start_monotonic, count)
        self._buckets: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not self._enabled or request.method == "OPTIONS" or request.url.path in _EXEMPT_PATHS:
            return await call_next(request)
        retry_after = self._register_hit(client_ip(request))
        if retry_after is not None:
            return self._too_many(request, retry_after)
        return await call_next(request)

    def _register_hit(self, ip: str) -> int | None:
        """Count one request for `ip`; return Retry-After seconds if over the
        ceiling, else None. Runs synchronously (no await), so it is atomic within
        the event loop and needs no lock."""
        now = time.monotonic()
        window_start, count = self._buckets.get(ip, (now, 0))
        if now - window_start >= self._window:
            window_start, count = now, 0
        count += 1
        self._buckets[ip] = (window_start, count)
        if len(self._buckets) > _PRUNE_THRESHOLD:
            self._prune(now)
        if count > self._limit:
            return max(1, int(self._window - (now - window_start)))
        return None

    def _prune(self, now: float) -> None:
        expired = [ip for ip, (start, _) in self._buckets.items() if now - start >= self._window]
        for ip in expired:
            del self._buckets[ip]

    def _too_many(self, request: Request, retry_after: int) -> JSONResponse:
        request_id = getattr(request.state, "request_id", "unknown")
        response = JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "rate_limited",
                    "message": "Too many requests. Try again shortly.",
                    "requestId": request_id,
                }
            },
        )
        response.headers["retry-after"] = str(retry_after)
        return response

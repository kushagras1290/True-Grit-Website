"""Baseline security headers for every API response."""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("x-content-type-options", "nosniff")
        response.headers.setdefault("referrer-policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("cache-control", "no-store")
        # This origin only ever returns JSON (or raw media bytes from
        # /media/{key}) and never HTML — docs_url/redoc_url are disabled in
        # main.py — so a maximally strict CSP costs nothing and closes off
        # script/frame injection on any response an attacker manages to get
        # reflected (e.g. a future HTML-rendering bug in an error path).
        response.headers.setdefault(
            "content-security-policy", "default-src 'none'; frame-ancestors 'none'"
        )
        response.headers.setdefault("x-frame-options", "DENY")
        # Cloudflare Workers only ever serve over HTTPS, so this is free
        # defense-in-depth against a client that somehow holds an http:// URL.
        response.headers.setdefault(
            "strict-transport-security", "max-age=63072000; includeSubDomains; preload"
        )
        # `payment` is deliberately left ungated: this product processes real
        # payments and a future response served in a payment-flow context
        # (e.g. a redirect target) must not have that API locked out here.
        response.headers.setdefault(
            "permissions-policy", "geolocation=(), camera=(), microphone=()"
        )
        return response

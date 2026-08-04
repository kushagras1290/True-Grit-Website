"""Shared-cache policy for anonymous, read-only public API responses."""

from __future__ import annotations

from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

_PRIVATE_PREFIXES = (
    "/v1/public/auth",
    "/v1/public/addresses",
    "/v1/public/checkout",
    "/v1/public/orders",
    "/v1/public/payments",
    "/v1/public/submissions",
    "/v1/public/subscriptions",
)
_SHORT_TTL_PREFIXES = (
    "/v1/public/community",
    "/v1/public/content/",
    "/v1/public/payment-methods",
    "/v1/public/products/",
    "/v1/public/reviews",
)
_CACHEABLE_METHODS = frozenset({"GET", "HEAD"})


@dataclass(frozen=True)
class CachePolicy:
    shared_ttl_seconds: int
    stale_while_revalidate_seconds: int


def public_cache_policy(request: Request) -> CachePolicy | None:
    """Return a policy only for requests that are safe to share between users."""
    path = request.url.path
    if request.method not in _CACHEABLE_METHODS or not path.startswith("/v1/public/"):
        return None
    if path.startswith(_PRIVATE_PREFIXES):
        return None
    if request.headers.get("authorization") or request.headers.get("cookie"):
        return None
    if path.startswith(_SHORT_TTL_PREFIXES):
        return CachePolicy(shared_ttl_seconds=60, stale_while_revalidate_seconds=30)
    return CachePolicy(shared_ttl_seconds=300, stale_while_revalidate_seconds=60)


def cache_tags(path: str) -> str:
    """Build bounded tags used by Cloudflare cache-tag purge operations."""
    segments = [segment for segment in path.split("/") if segment]
    tags = ["truegrit-public-api"]
    if len(segments) >= 3:
        resource = segments[2]
        tags.append(f"truegrit-{resource}")
        if len(segments) >= 4:
            identifier = segments[3][:80]
            tags.append(f"truegrit-{resource}-{identifier}")
    return ",".join(tags)


class PublicCachePolicyMiddleware(BaseHTTPMiddleware):
    """Mark anonymous public reads cacheable while defaulting everything else private."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        policy = public_cache_policy(request)
        response = await call_next(request)
        if policy is None or response.status_code != 200 or "set-cookie" in response.headers:
            response.headers["cache-control"] = "no-store"
            response.headers["x-cache-policy"] = "bypass"
            return response

        response.headers["cache-control"] = (
            "public, max-age=0, "
            f"s-maxage={policy.shared_ttl_seconds}, "
            f"stale-while-revalidate={policy.stale_while_revalidate_seconds}"
        )
        response.headers["cache-tag"] = cache_tags(request.url.path)
        response.headers["x-cache-policy"] = "public"
        return response

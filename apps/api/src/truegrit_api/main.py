"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from truegrit_api.api.admin import router as admin_router
from truegrit_api.api.customer_auth import router as customer_auth_router
from truegrit_api.api.phone_auth import router as phone_auth_router
from truegrit_api.api.public import router as public_router
from truegrit_api.api.storefront import router as storefront_router
from truegrit_api.config import get_settings
from truegrit_api.middleware.error_handler import install_error_handlers
from truegrit_api.middleware.rate_limit import RateLimitMiddleware
from truegrit_api.middleware.request_id import RequestIdMiddleware
from truegrit_api.middleware.security_headers import SecurityHeadersMiddleware
from truegrit_api.platform.database import Database, build_local_database
from truegrit_api.platform.media_store import LocalMediaStore, MediaStore
from truegrit_api.services.media import media_root


def create_app(db: Database | None = None, media: MediaStore | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="True Grit API",
        version="1.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url="/internal/openapi.json",
    )

    # Middleware runs in reverse registration order (last added is outermost).
    # RateLimitMiddleware is added first so it sits innermost — the global 429 it
    # returns still passes back out through SecurityHeaders, RequestId (stamps
    # x-request-id) and CORS. The request-id middleware wraps everything else.
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)

    # Outside the Workers runtime, boot a SQLite database from the real
    # migrations + development seed (identical SQL semantics to D1).
    app.state.db = db if db is not None else build_local_database()
    app.state.media = media if media is not None else LocalMediaStore(media_root())

    @app.get("/media/{key:path}", include_in_schema=False)
    async def serve_media(key: str) -> Response:
        result = await app.state.media.get(key)
        if result is None:
            return Response(status_code=404)
        data, content_type = result
        return Response(
            content=data,
            media_type=content_type,
            headers={"cache-control": "public, max-age=86400"},
        )

    app.include_router(public_router, prefix="/v1/public")
    app.include_router(customer_auth_router, prefix="/v1/public/auth")
    app.include_router(phone_auth_router, prefix="/v1/public/auth")
    app.include_router(storefront_router, prefix="/v1/public")
    app.include_router(admin_router, prefix="/v1/admin")

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    return app


def __getattr__(name: str) -> FastAPI:
    # Lazily construct the module-level ``app`` only when it is actually
    # accessed (e.g. ``uvicorn truegrit_api.main:app`` in local development).
    # This keeps importing ``create_app`` from this module side-effect free, so
    # the Cloudflare Worker entry point (worker.py) never triggers the local
    # SQLite build path — it constructs its own app bound to the D1 database.
    if name == "app":
        return create_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

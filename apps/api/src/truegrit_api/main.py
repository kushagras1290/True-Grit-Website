"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from truegrit_api.api.admin import router as admin_router
from truegrit_api.api.customer_auth import router as customer_auth_router
from truegrit_api.api.public import router as public_router
from truegrit_api.api.storefront import router as storefront_router
from truegrit_api.config import get_settings
from truegrit_api.middleware.error_handler import install_error_handlers
from truegrit_api.middleware.rate_limit import RateLimitMiddleware
from truegrit_api.middleware.request_id import RequestIdMiddleware
from truegrit_api.middleware.security_headers import SecurityHeadersMiddleware
from truegrit_api.platform.database import Database, build_local_database
from truegrit_api.services.media import media_root


def create_app(db: Database | None = None) -> FastAPI:
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
        allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
        allow_headers=["content-type", "x-request-id", "x-csrf-token"],
    )
    install_error_handlers(app)

    # Outside the Workers runtime, boot a SQLite database from the real
    # migrations + development seed (identical SQL semantics to D1).
    app.state.db = db if db is not None else build_local_database()
    media_root().mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=media_root()), name="media")

    app.include_router(public_router, prefix="/v1/public")
    app.include_router(customer_auth_router, prefix="/v1/public/auth")
    app.include_router(storefront_router, prefix="/v1/public")
    app.include_router(admin_router, prefix="/v1/admin")

    @app.get("/health/live", tags=["health"])
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()

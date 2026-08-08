"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from truegrit_api.api.admin import router as admin_router
from truegrit_api.api.community import router as community_router
from truegrit_api.api.customer_auth import router as customer_auth_router
from truegrit_api.api.deployments import router as deployments_router
from truegrit_api.api.farm_partnerships import router as farm_partnerships_router
from truegrit_api.api.messages import router as messages_router
from truegrit_api.api.phone_auth import router as phone_auth_router
from truegrit_api.api.public import router as public_router
from truegrit_api.api.roadmap_admin import router as roadmap_admin_router
from truegrit_api.api.roadmap_public import router as roadmap_public_router
from truegrit_api.api.storefront import router as storefront_router
from truegrit_api.api.submissions import router as submissions_router
from truegrit_api.api.support_bot import router as support_bot_router
from truegrit_api.api.support_bot_public import router as support_bot_public_router
from truegrit_api.config import get_settings
from truegrit_api.middleware.cache_policy import PublicCachePolicyMiddleware
from truegrit_api.middleware.error_handler import install_error_handlers
from truegrit_api.middleware.rate_limit import RateLimitMiddleware
from truegrit_api.middleware.request_id import RequestIdMiddleware
from truegrit_api.middleware.security_headers import SecurityHeadersMiddleware
from truegrit_api.platform.ai_chat import ChatModel
from truegrit_api.platform.database import Database, build_local_database
from truegrit_api.platform.github import GitHubClient
from truegrit_api.platform.media_store import LocalMediaStore, MediaStore
from truegrit_api.platform.translation import Translator
from truegrit_api.services.deployments import DeploymentService
from truegrit_api.services.media import media_root


def create_app(
    db: Database | None = None,
    media: MediaStore | None = None,
    translator: Translator | None = None,
    chat: ChatModel | None = None,
) -> FastAPI:
    settings = get_settings()  # fail fast if required env vars are missing
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
    app.add_middleware(PublicCachePolicyMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        # `allow_credentials=True` makes an unrestricted origin a real
        # information-disclosure risk, not a theoretical one: any site could
        # issue a credentialed request with a signed-in visitor's session
        # cookie and read the JSON response (orders, account data, admin
        # data) back through CORS. `allowed_origins` is exactly the
        # storefront/admin origins this deployment actually serves
        # (`PUBLIC_STOREFRONT_URL`/`PUBLIC_ADMIN_URL`/`PUBLIC_PROCESS_URL`, plus their
        # localhost/127.0.0.1 sibling for local dev) -- never a wildcard.
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
    # None outside the Workers runtime; get_translator (auth/dependencies.py)
    # falls back to UnavailableTranslator itself, the same "never None to a
    # route" contract get_database's non-nullable app.state.db keeps by
    # constructing a real local instance instead.
    app.state.translator = translator
    # Same story as translator: None outside Workers, get_chat_model falls
    # back to UnavailableChat.
    app.state.chat = chat
    app.state.deployments = DeploymentService(
        GitHubClient(
            settings.github_repository,
            settings.github_token,
            settings.github_api_version,
        ),
        testing_url=settings.deployment_testing_url,
        staging_url=settings.deployment_staging_url,
        main_url=settings.deployment_main_url,
    )

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
    app.include_router(roadmap_public_router, prefix="/v1/public")
    app.include_router(submissions_router, prefix="/v1/public")
    app.include_router(community_router, prefix="/v1/public")
    app.include_router(farm_partnerships_router, prefix="/v1/public")
    app.include_router(support_bot_public_router, prefix="/v1/public")
    app.include_router(admin_router, prefix="/v1/admin")
    app.include_router(roadmap_admin_router, prefix="/v1/admin")
    app.include_router(deployments_router, prefix="/v1/admin")
    app.include_router(messages_router, prefix="/v1/admin")
    app.include_router(support_bot_router, prefix="/v1/admin")

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

"""FastAPI auth dependencies.

Hiding a navigation item is not authorization — every admin endpoint declares
its permission here and the API enforces it independently of the UI.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from truegrit_api.auth.principal import Principal
from truegrit_api.auth.sessions import resolve_session
from truegrit_api.config import get_settings
from truegrit_api.errors import AuthenticationError, PermissionDeniedError
from truegrit_api.platform.database import Database


async def get_database(request: Request) -> Database:
    # Must be async: FastAPI runs *synchronous* dependencies in an anyio
    # threadpool, and Cloudflare Workers (Pyodide) cannot start threads
    # ("RuntimeError: can't start new thread"). Declaring it async runs it
    # inline on the event loop. It awaits nothing — it only reads app state.
    db: Database | None = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("Application database is not configured.")
    return db


async def get_current_staff(
    request: Request, db: Annotated[Database, Depends(get_database)]
) -> Principal:
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise AuthenticationError()
    principal = await resolve_session(db, token)
    if principal is None or principal.user_type != "staff":
        raise AuthenticationError()
    return principal


async def get_current_customer(
    request: Request, db: Annotated[Database, Depends(get_database)]
) -> Principal:
    """Resolve the signed-in storefront customer. A staff session never
    satisfies this dependency, keeping the two audiences isolated even though
    they share one session cookie on the API origin."""
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        raise AuthenticationError()
    principal = await resolve_session(db, token)
    if principal is None or principal.user_type != "customer":
        raise AuthenticationError()
    return principal


def require_permission(permission: str):
    async def dependency(
        principal: Annotated[Principal, Depends(get_current_staff)],
    ) -> Principal:
        if not principal.has(permission):
            raise PermissionDeniedError()
        return principal

    return dependency

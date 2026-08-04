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
from truegrit_api.platform.ai_chat import ChatModel, UnavailableChat
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator, UnavailableTranslator

_OWNER_ROLE_KEY = "super_admin"


async def get_database(request: Request) -> Database:
    # Must be async: FastAPI runs *synchronous* dependencies in an anyio
    # threadpool, and Cloudflare Workers (Pyodide) cannot start threads
    # ("RuntimeError: can't start new thread"). Declaring it async runs it
    # inline on the event loop. It awaits nothing — it only reads app state.
    db: Database | None = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("Application database is not configured.")
    return db


async def get_translator(request: Request) -> Translator:
    # Same reasoning as get_database. Falls back to UnavailableTranslator
    # (never None) so a call outside the Workers runtime fails with a clear
    # "not available locally" error instead of an AttributeError.
    translator: Translator | None = getattr(request.app.state, "translator", None)
    return translator if translator is not None else UnavailableTranslator()


async def get_chat_model(request: Request) -> ChatModel:
    # Same reasoning as get_translator: falls back to UnavailableChat (never
    # None) so the support bot fails with a clear "not available locally"
    # error outside the Workers runtime instead of an AttributeError.
    chat: ChatModel | None = getattr(request.app.state, "chat", None)
    return chat if chat is not None else UnavailableChat()


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


async def get_optional_customer(
    request: Request, db: Annotated[Database, Depends(get_database)]
) -> Principal | None:
    """The signed-in customer if there is one, otherwise None.

    For routes that are open to everyone but behave better when they know who
    is calling — a farm partnership application is the case this exists for: it
    must accept an anonymous grower, yet should attribute the application to an
    account when the applicant happens to be signed in.

    Never raises. An expired, forged or staff-session cookie resolves to None
    rather than 401, because on these routes "not signed in" is a normal state,
    not a failure — and a stale cookie must not turn a public form into an
    error page.
    """
    token = request.cookies.get(get_settings().session_cookie_name)
    if not token:
        return None
    principal = await resolve_session(db, token)
    if principal is None or principal.user_type != "customer":
        return None
    return principal


def require_permission(permission: str):
    async def dependency(
        principal: Annotated[Principal, Depends(get_current_staff)],
    ) -> Principal:
        if not principal.has(permission):
            raise PermissionDeniedError()
        return principal

    return dependency


async def require_owner(db: Database, principal: Principal) -> None:
    """Hard-gate an action to the `super_admin` role itself, not a permission.

    Permissions alone are not enough here: this codebase's convention is that
    Administrator ends up holding every ordinary permission (see the blanket
    `SELECT ... FROM permissions` grants to `rol_admin` in
    `database/seeds/development.sql` and `0041_role_permission_baseline.sql`),
    so anything meant to stay owner-exclusive -- server logs, the DB browser,
    staff-messaging membership -- must check the role itself. A farm-owner
    sub-admin or any other staff member granted a matching permission through
    Scope Management must still be rejected here.
    """
    row = await db.fetch_one(
        """
        SELECT 1 AS ok
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = ? AND r.key = ?
        LIMIT 1
        """,
        (principal.user_id, _OWNER_ROLE_KEY),
    )
    if row is None:
        raise PermissionDeniedError("Only the owner can do this.")

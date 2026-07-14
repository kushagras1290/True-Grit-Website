"""Storefront customer authentication.

Two ways in, one session model:
  * email + password  — self-service registration, PBKDF2-hashed credentials.
  * Sign in with Google — a verified Google ID token, linked by subject/email.

All routes are unauthenticated entry points except `/me`, which resolves the
current customer session. Sessions and cookies are created by the shared
`auth.sessions` helpers so staff and customer sign-in behave identically.
"""

from __future__ import annotations

import re
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.google import verify_google_id_token
from truegrit_api.auth.passwords import hash_password, verify_password
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.auth.sessions import end_session, start_session
from truegrit_api.config import Settings, get_settings
from truegrit_api.errors import AuthenticationError, ConflictError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.email import send_email
from truegrit_api.services.password_reset import confirm_password_reset, request_password_reset
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["customer-auth"])

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MAX_EMAIL_LENGTH = 254
_MAX_NAME_LENGTH = 120
_MAX_PASSWORD_LENGTH = 256
# Hash of an unguessable value, used to equalise timing when an email has no
# account so login cannot be used to enumerate registered users. Computed lazily
# and cached: hashing draws entropy for its salt, which Cloudflare Workers only
# permit inside a request context — never at module import time.
_dummy_hash: str | None = None


def _dummy_password_hash() -> str:
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = hash_password(new_id("nope"), iterations=1)
    return _dummy_hash


class RegisterRequest(BaseModel):
    name: str = Field(min_length=1, max_length=_MAX_NAME_LENGTH)
    email: str = Field(min_length=3, max_length=_MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=_MAX_EMAIL_LENGTH)
    password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=1, max_length=8192)


def _normalize_email(raw: str) -> str:
    email = raw.strip().lower()
    if not _EMAIL_PATTERN.match(email) or len(email) > _MAX_EMAIL_LENGTH:
        raise ValidationAppError("Enter a valid email address.")
    return email


def _customer_payload(user: dict[str, Any]) -> dict[str, str]:
    return {"id": user["id"], "displayName": user["display_name"], "email": user["email"]}


async def _find_customer_by_email(db: Database, email: str) -> dict[str, Any] | None:
    return await db.fetch_one(
        "SELECT id, display_name, email, user_type, status FROM users WHERE email = ?",
        (email,),
    )


async def _limit_by_ip(
    db: Database,
    request: Request,
    settings: Settings,
    *,
    scope: str,
    max_attempts: int,
    window: int,
) -> None:
    if not settings.rate_limit_enabled:
        return
    key = f"{scope}:ip:{hash_identifier(client_ip(request))}"
    await enforce_rate_limit(db, key=key, rule=RateLimitRule(max_attempts, window))


async def _limit_by_account(
    db: Database, settings: Settings, email: str, *, scope: str, max_attempts: int, window: int
) -> None:
    if not settings.rate_limit_enabled:
        return
    key = f"{scope}:acct:{hash_identifier(email)}"
    await enforce_rate_limit(db, key=key, rule=RateLimitRule(max_attempts, window))


@router.post("/register")
async def register(
    payload: RegisterRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    await _limit_by_ip(
        db,
        request,
        settings,
        scope="register",
        max_attempts=settings.rate_limit_register_per_ip,
        window=settings.rate_limit_register_window_seconds,
    )
    name = payload.name.strip()
    email = _normalize_email(payload.email)
    if not name:
        raise ValidationAppError("Enter your name.")
    if len(payload.password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )

    if await _find_customer_by_email(db, email) is not None:
        raise ConflictError("An account with this email already exists.")

    user_id = new_id("usr")
    now = utc_now_iso()
    password_hash = hash_password(payload.password, iterations=settings.pbkdf2_iterations)
    await db.batch(
        [
            (
                """
                INSERT INTO users (
                  id, email, display_name, user_type, status,
                  email_verified_at, created_at, updated_at, last_sign_in_at
                ) VALUES (?, ?, ?, 'customer', 'active', NULL, ?, ?, NULL)
                """,
                (user_id, email, name, now, now),
            ),
            (
                """
                INSERT INTO customer_profiles (user_id, marketing_email_consent,
                  created_at, updated_at)
                VALUES (?, 0, ?, ?)
                """,
                (user_id, now, now),
            ),
            (
                """
                INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, password_hash, now, now),
            ),
        ]
    )
    await start_session(
        db, response, user_id=user_id, settings=settings, user_agent_summary="customer-register"
    )
    return {"ok": True, "customer": {"id": user_id, "displayName": name, "email": email}}


@router.post("/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    email = payload.email.strip().lower()
    # Limit before the expensive password hash so an attacker cannot burn CPU.
    await _limit_by_ip(
        db,
        request,
        settings,
        scope="login",
        max_attempts=settings.rate_limit_login_per_ip,
        window=settings.rate_limit_window_seconds,
    )
    await _limit_by_account(
        db,
        settings,
        email,
        scope="login",
        max_attempts=settings.rate_limit_login_per_account,
        window=settings.rate_limit_window_seconds,
    )
    row = await db.fetch_one(
        """
        SELECT u.id, u.display_name, u.email, c.password_hash
        FROM users u
        JOIN user_credentials c ON c.user_id = u.id
        WHERE u.email = ? AND u.user_type = 'customer' AND u.status = 'active'
        """,
        (email,),
    )
    stored_hash = row["password_hash"] if row is not None else _dummy_password_hash()
    if not verify_password(payload.password, stored_hash) or row is None:
        raise AuthenticationError("Invalid email or password.")

    await start_session(
        db, response, user_id=row["id"], settings=settings, user_agent_summary="customer-login"
    )
    return {"ok": True, "customer": _customer_payload(row)}


@router.post("/google")
async def google_login(
    payload: GoogleLoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    await _limit_by_ip(
        db,
        request,
        settings,
        scope="google",
        max_attempts=settings.rate_limit_google_per_ip,
        window=settings.rate_limit_window_seconds,
    )
    identity = verify_google_id_token(payload.credential, client_id=settings.google_client_id)
    email = identity.email.strip().lower()
    now = utc_now_iso()

    link = await db.fetch_one(
        "SELECT user_id FROM oauth_identities WHERE provider = 'google' AND provider_subject = ?",
        (identity.subject,),
    )
    if link is not None:
        user_id = link["user_id"]
        await db.execute(
            "UPDATE oauth_identities SET last_login_at = ?, email = ? WHERE provider = 'google'"
            " AND provider_subject = ?",
            (now, email, identity.subject),
        )
    else:
        existing = await _find_customer_by_email(db, email)
        if existing is not None and existing["user_type"] != "customer":
            raise ConflictError("This email is already registered for staff access.")
        if existing is not None:
            user_id = existing["id"]
            await db.execute(
                """
                INSERT INTO oauth_identities (id, user_id, provider, provider_subject, email,
                  created_at, last_login_at)
                VALUES (?, ?, 'google', ?, ?, ?, ?)
                """,
                (new_id("oid"), user_id, identity.subject, email, now, now),
            )
        else:
            user_id = new_id("usr")
            await db.batch(
                [
                    (
                        """
                        INSERT INTO users (
                          id, email, display_name, user_type, status,
                          email_verified_at, created_at, updated_at, last_sign_in_at
                        ) VALUES (?, ?, ?, 'customer', 'active', ?, ?, ?, NULL)
                        """,
                        (user_id, email, identity.name, now, now, now),
                    ),
                    (
                        """
                        INSERT INTO customer_profiles (user_id, marketing_email_consent,
                          created_at, updated_at)
                        VALUES (?, 0, ?, ?)
                        """,
                        (user_id, now, now),
                    ),
                    (
                        """
                        INSERT INTO oauth_identities (id, user_id, provider, provider_subject,
                          email, created_at, last_login_at)
                        VALUES (?, ?, 'google', ?, ?, ?, ?)
                        """,
                        (new_id("oid"), user_id, identity.subject, email, now, now),
                    ),
                ]
            )

    user = await db.fetch_one(
        "SELECT id, display_name, email FROM users WHERE id = ? AND status = 'active'",
        (user_id,),
    )
    if user is None:
        raise AuthenticationError("This account is not available.")

    await start_session(
        db, response, user_id=user_id, settings=settings, user_agent_summary="customer-google"
    )
    return {"ok": True, "customer": _customer_payload(user)}


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await end_session(db, request, response, settings=get_settings())
    return {"ok": True}


@router.get("/me")
async def me(principal: Annotated[Principal, Depends(get_current_customer)]) -> Any:
    return {
        "id": principal.user_id,
        "displayName": principal.display_name,
        "email": principal.email,
    }


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PasswordResetRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=_MAX_EMAIL_LENGTH)


class PasswordResetConfirm(_CamelModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=_MAX_PASSWORD_LENGTH)


@router.post("/password-reset")
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    if settings.rate_limit_enabled:
        await enforce_rate_limit(
            db,
            key=f"customer-reset:ip:{hash_identifier(client_ip(request))}",
            rule=RateLimitRule(
                settings.rate_limit_login_per_ip, settings.rate_limit_window_seconds
            ),
        )
    email = await request_password_reset(
        db,
        email=payload.email,
        user_type="customer",
        reset_base_url=f"{settings.public_storefront_url}/reset-password",
        settings=settings,
    )
    if email is not None:
        background.add_task(
            send_email,
            email.to,
            email.subject,
            email.body,
            settings,
            email.html_body,
        )
    return {"ok": True}


@router.post("/password-reset/confirm")
async def password_reset_confirm(
    payload: PasswordResetConfirm,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await confirm_password_reset(
        db,
        token=payload.token,
        new_password=payload.new_password,
        settings=get_settings(),
        request_id=getattr(request.state, "request_id", "unknown"),
        source="api",
    )

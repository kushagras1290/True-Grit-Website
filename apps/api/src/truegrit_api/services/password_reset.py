"""Self-service password reset for customer and staff portals.

Request: look up an active user of the expected type, mint a single-use token,
store only its hash, and email the reset link. The response is always success so
the endpoint can't be used to discover which emails are registered.

Confirm: validate the token (unused, unexpired), then upsert the user's password
credential and burn the token. A reset works for any user with credentials, so
the same confirm path serves every portal.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from truegrit_api.auth.passwords import hash_password
from truegrit_api.auth.sessions import hash_token
from truegrit_api.config import Settings
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.email import OutboundEmail
from truegrit_api.services.email_templates import render_password_reset, render_staff_invitation
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def _reset_email_body(reset_url: str, minutes: int) -> str:
    return (
        "We received a request to reset your True Grit password.\n\n"
        f"Reset it here (valid for {minutes} minutes):\n{reset_url}\n\n"
        "If you didn't ask for this, you can safely ignore this email."
    )


def _invite_email_body(display_name: str, setup_url: str, minutes: int) -> str:
    return (
        f"Hi {display_name},\n\n"
        "You have been invited to the True Grit admin portal.\n\n"
        f"Set your password here (valid for {minutes} minutes):\n{setup_url}\n\n"
        "If you were not expecting this invite, you can ignore this email."
    )


async def _mint_reset_url(
    db: Database,
    *,
    user_id: str,
    reset_base_url: str,
    settings: Settings,
) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    expires_at = (now + timedelta(minutes=settings.password_reset_lifetime_minutes)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    await db.execute(
        "INSERT INTO password_reset_tokens (id, user_id, token_hash, expires_at, created_at)"
        " VALUES (?, ?, ?, ?, ?)",
        (new_id("prt"), user_id, hash_token(token), expires_at, utc_now_iso()),
    )
    separator = "&" if "?" in reset_base_url else "?"
    return f"{reset_base_url}{separator}token={token}"


async def request_password_reset(
    db: Database,
    *,
    email: str,
    user_type: str,
    reset_base_url: str,
    settings: Settings,
) -> OutboundEmail | None:
    """Mint a reset token and return the email to send (or None for an unknown
    address). Kept side-effect-free of transport so the endpoint can send it in
    the background and tests can assert the token without a mail server."""
    normalized = (email or "").strip().lower()
    user = await db.fetch_one(
        "SELECT id, email FROM users WHERE email = ? AND user_type = ? AND status = 'active'",
        (normalized, user_type),
    )
    if user is None:
        return None

    reset_url = await _mint_reset_url(
        db,
        user_id=user["id"],
        reset_base_url=reset_base_url,
        settings=settings,
    )
    return OutboundEmail(
        to=user["email"],
        subject="Reset your True Grit password",
        body=_reset_email_body(reset_url, settings.password_reset_lifetime_minutes),
        html_body=render_password_reset(reset_url, settings.password_reset_lifetime_minutes),
    )


async def request_staff_invitation_email(
    db: Database,
    *,
    user_id: str,
    reset_base_url: str,
    settings: Settings,
) -> OutboundEmail | None:
    user = await db.fetch_one(
        """
        SELECT id, email, display_name
        FROM users
        WHERE id = ? AND user_type = 'staff' AND status = 'invited'
        """,
        (user_id,),
    )
    if user is None:
        return None
    setup_url = await _mint_reset_url(
        db,
        user_id=user["id"],
        reset_base_url=reset_base_url,
        settings=settings,
    )
    return OutboundEmail(
        to=user["email"],
        subject="You are invited to True Grit",
        body=_invite_email_body(
            user["display_name"], setup_url, settings.password_reset_lifetime_minutes
        ),
        html_body=render_staff_invitation(
            user["display_name"], setup_url, settings.password_reset_lifetime_minutes
        ),
    )


async def request_staff_password_reset_for_user(
    db: Database,
    *,
    user_id: str,
    reset_base_url: str,
    settings: Settings,
) -> OutboundEmail | None:
    user = await db.fetch_one(
        """
        SELECT id, email, display_name, status
        FROM users
        WHERE id = ? AND user_type = 'staff' AND deleted_at IS NULL
          AND status IN ('active', 'invited', 'disabled')
        """,
        (user_id,),
    )
    if user is None:
        return None
    if user["status"] == "invited":
        return await request_staff_invitation_email(
            db,
            user_id=user_id,
            reset_base_url=reset_base_url,
            settings=settings,
        )
    reset_url = await _mint_reset_url(
        db,
        user_id=user["id"],
        reset_base_url=reset_base_url,
        settings=settings,
    )
    return OutboundEmail(
        to=user["email"],
        subject="Reset your True Grit password",
        body=_reset_email_body(reset_url, settings.password_reset_lifetime_minutes),
        html_body=render_password_reset(reset_url, settings.password_reset_lifetime_minutes),
    )


async def confirm_password_reset(
    db: Database,
    *,
    token: str,
    new_password: str,
    settings: Settings,
    request_id: str = "unknown",
    source: str = "api",
) -> dict[str, Any]:
    if len(new_password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )
    row = await db.fetch_one(
        """
        SELECT prt.id, prt.user_id, prt.expires_at, prt.used_at,
               u.email, u.user_type, u.status
        FROM password_reset_tokens prt
        JOIN users u ON u.id = prt.user_id
        WHERE prt.token_hash = ?
        """,
        (hash_token(token or ""),),
    )
    now = utc_now_iso()
    if row is None or row["used_at"] is not None or row["expires_at"] <= now:
        raise ValidationAppError("This reset link is invalid or has expired.")

    password_hash = hash_password(new_password, iterations=settings.pbkdf2_iterations)
    await db.batch(
        [
            (
                "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash,"
                " updated_at = excluded.updated_at",
                (row["user_id"], password_hash, now, now),
            ),
            (
                "UPDATE password_reset_tokens SET used_at = ? WHERE id = ?",
                (now, row["id"]),
            ),
            # Sign out everywhere: revoke the user's live sessions on reset.
            (
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, row["user_id"]),
            ),
            (
                "UPDATE users SET status = 'active', updated_at = ?"
                " WHERE id = ? AND status = 'invited'",
                (now, row["user_id"]),
            ),
            audit_statement(
                action="password.changed",
                entity_type="user",
                entity_id=row["user_id"],
                actor_id=row["user_id"],
                request_id=request_id,
                source=source,
                created_at=now,
                after={
                    "email": row["email"],
                    "userType": row["user_type"],
                    "activatedFromInvite": row["status"] == "invited",
                    "credentialChanged": True,
                    "passwordStored": False,
                },
            ),
        ]
    )
    return {"ok": True}

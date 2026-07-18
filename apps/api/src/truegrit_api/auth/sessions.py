"""Session resolution and lifecycle.

Session cookies carry an opaque random token; only its SHA-256 hash is stored.
Disabled users and expired or revoked sessions never authenticate. The same
cookie/session machinery backs both staff (admin) and customer (storefront)
sign-in, so the creation and teardown logic lives here once.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta

from fastapi import Request, Response

from truegrit_api.auth.principal import Principal
from truegrit_api.config import Settings
from truegrit_api.platform.database import Database
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _session_expiry_iso(hours: int) -> str:
    return (datetime.now(UTC) + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")


async def start_session(
    db: Database,
    response: Response,
    *,
    user_id: str,
    settings: Settings,
    user_agent_summary: str,
) -> str:
    """Create a session for `user_id`, stamp the user's last sign-in, and set the
    session cookie on `response`. Session row insert and user update are batched
    so a partial write can never leave a session without its sign-in stamp.

    Returns the plaintext CSRF token for this session. The session cookie is
    HttpOnly (JS cannot read it) and — because the storefront/admin and API
    live on different registrable domains — is issued with SameSite=None, so
    it carries no CSRF protection of its own. The caller must hand this token
    to the client (e.g. in the login response body); the client then resends
    it as `X-CSRF-Token` on state-changing requests, and
    `verify_csrf_token` checks it against the hash stored here.
    """
    now = utc_now_iso()
    token = secrets.token_urlsafe(32)
    csrf_secret = secrets.token_urlsafe(32)
    expires_at = _session_expiry_iso(settings.session_lifetime_hours)
    await db.batch(
        [
            (
                """
                INSERT INTO sessions (
                  id, user_id, token_hash, csrf_secret_hash, expires_at,
                  last_seen_at, created_at, revoked_at, ip_hash, user_agent_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                """,
                (
                    new_id("ses"),
                    user_id,
                    hash_token(token),
                    hash_token(csrf_secret),
                    expires_at,
                    now,
                    now,
                    user_agent_summary,
                ),
            ),
            (
                "UPDATE users SET last_sign_in_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
            ),
        ]
    )
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_lifetime_hours * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )
    return csrf_secret


async def verify_csrf_token(db: Database, session_token: str, provided_token: str | None) -> bool:
    """Constant-time check that `provided_token` (the `X-CSRF-Token` header)
    matches the CSRF secret bound to the session behind `session_token` (the
    session cookie). Called on every state-changing authenticated request —
    see `truegrit_api.auth.dependencies`."""
    if not provided_token:
        return False
    row = await db.fetch_one(
        "SELECT csrf_secret_hash FROM sessions WHERE token_hash = ? AND revoked_at IS NULL"
        " AND expires_at > ?",
        (hash_token(session_token), utc_now_iso()),
    )
    if row is None or not row["csrf_secret_hash"]:
        return False
    return secrets.compare_digest(row["csrf_secret_hash"], hash_token(provided_token))


async def rotate_csrf_token(db: Database, session_token: str) -> str | None:
    """Issue a fresh CSRF secret for the session behind `session_token` and
    return it in plaintext, or None if that session is not live.

    Backs the `GET .../auth/csrf` endpoints: a page reload loses whatever
    token the client held in memory (it is deliberately never persisted to a
    cookie or storage), so the client re-establishes one against its still-
    valid session cookie. A GET so it never itself needs a CSRF token to call.
    """
    row = await db.fetch_one(
        "SELECT id FROM sessions WHERE token_hash = ? AND revoked_at IS NULL AND expires_at > ?",
        (hash_token(session_token), utc_now_iso()),
    )
    if row is None:
        return None
    csrf_secret = secrets.token_urlsafe(32)
    await db.execute(
        "UPDATE sessions SET csrf_secret_hash = ? WHERE id = ?",
        (hash_token(csrf_secret), row["id"]),
    )
    return csrf_secret


async def end_session(
    db: Database,
    request: Request,
    response: Response,
    *,
    settings: Settings,
) -> None:
    """Revoke the caller's session (if any) and clear the cookie. Idempotent:
    calling without a valid session simply clears the cookie."""
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        await db.execute(
            "UPDATE sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
            (utc_now_iso(), hash_token(token)),
        )
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        samesite=settings.session_cookie_samesite,
        secure=settings.cookie_secure,
    )


async def resolve_session(db: Database, token: str) -> Principal | None:
    row = await db.fetch_one(
        """
        SELECT u.id, u.display_name, u.email, u.user_type,
               u.phone_e164, u.phone_verified_at
        FROM sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token_hash = ?
          AND s.revoked_at IS NULL
          AND s.expires_at > ?
          AND u.status = 'active'
        """,
        (hash_token(token), utc_now_iso()),
    )
    if row is None:
        return None
    permission_rows = await db.fetch_all(
        """
        SELECT DISTINCT p.key
        FROM user_roles ur
        JOIN role_permissions rp ON rp.role_id = ur.role_id
        JOIN permissions p ON p.id = rp.permission_id
        WHERE ur.user_id = ?
        """,
        (row["id"],),
    )
    membership = await db.fetch_one(
        "SELECT farm_id FROM farm_members WHERE user_id = ?", (row["id"],)
    )
    return Principal(
        user_id=row["id"],
        display_name=row["display_name"],
        email=row["email"],
        user_type=row["user_type"],
        permissions=frozenset(entry["key"] for entry in permission_rows),
        farm_id=membership["farm_id"] if membership else None,
        # Surface the number only once it is verified: an unverified value is a
        # claim, and every consumer of Principal treats presence as proof.
        phone_e164=row["phone_e164"] if row["phone_verified_at"] else None,
    )

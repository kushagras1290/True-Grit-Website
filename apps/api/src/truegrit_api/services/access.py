"""Staff access management: invite users, toggle status, assign roles.

Roles are collections of permissions; the API always checks permissions, never
role names. Every change is audited. An actor can never disable their own
account (which would be an easy way to lock everyone out by mistake).
"""

from __future__ import annotations

import re
import secrets
import string
from typing import Any

from truegrit_api.auth.passwords import hash_password, verify_password
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ASSIGNABLE_STATUSES = frozenset({"active", "disabled", "invited"})
_TEMP_PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_"


def _temporary_password(length: int = 18) -> str:
    return "".join(secrets.choice(_TEMP_PASSWORD_ALPHABET) for _ in range(length))


async def _validate_roles(db: Database, role_ids: list[str]) -> list[str]:
    unique = list(dict.fromkeys(role_ids))
    if not unique:
        return []
    placeholders = ", ".join("?" for _ in unique)
    rows = await db.fetch_all(
        f"SELECT id FROM roles WHERE id IN ({placeholders})",
        unique,
    )
    found = {row["id"] for row in rows}
    missing = [role_id for role_id in unique if role_id not in found]
    if missing:
        raise ValidationAppError("Unknown role.", details={"roles": missing})
    return unique


async def _ensure_no_farm_owner_role(db: Database, role_ids: list[str]) -> None:
    if not role_ids:
        return
    placeholders = ", ".join("?" for _ in role_ids)
    rows = await db.fetch_all(
        f"SELECT id, key FROM roles WHERE id IN ({placeholders})",
        role_ids,
    )
    if any(row["key"] == "farm_owner" for row in rows):
        raise ValidationAppError("Use Add farm owner to assign the farm owner role.")


async def invite_user(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    email: str,
    display_name: str,
    role_ids: list[str],
) -> dict[str, Any]:
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationAppError("Enter a valid email address.")
    if len(display_name) < 2:
        raise ValidationAppError("Enter the person's name.")
    if await db.fetch_one("SELECT id FROM users WHERE email = ?", (email,)) is not None:
        raise ConflictError("A user with this email already exists.")
    roles = await _validate_roles(db, role_ids)
    await _ensure_no_farm_owner_role(db, roles)

    user_id = new_id("usr")
    now = utc_now_iso()
    statements: list[Any] = [
        (
            "INSERT INTO users (id, email, display_name, user_type, status,"
            " created_at, updated_at) VALUES (?, ?, ?, 'staff', 'invited', ?, ?)",
            (user_id, email, display_name, now, now),
        )
    ]
    for role_id in roles:
        statements.append(
            (
                "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
                " VALUES (?, ?, ?, ?)",
                (user_id, role_id, now, actor.user_id),
            )
        )
    statements.append(
        audit_statement(
            action="user.invited",
            entity_type="user",
            entity_id=user_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"email": email, "roles": roles},
        )
    )
    await db.batch(statements)
    return {"id": user_id, "email": email, "status": "invited"}


async def create_user(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    email: str,
    display_name: str,
    role_ids: list[str],
    password: str,
) -> dict[str, Any]:
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()
    settings = get_settings()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationAppError("Enter a valid email address.")
    if len(display_name) < 2:
        raise ValidationAppError("Enter the person's name.")
    if len(password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )
    if await db.fetch_one("SELECT id FROM users WHERE email = ?", (email,)) is not None:
        raise ConflictError("A user with this email already exists.")
    roles = await _validate_roles(db, role_ids)
    await _ensure_no_farm_owner_role(db, roles)

    user_id = new_id("usr")
    now = utc_now_iso()
    password_hash = hash_password(password, iterations=settings.pbkdf2_iterations)
    statements: list[Any] = [
        (
            "INSERT INTO users (id, email, display_name, user_type, status,"
            " created_at, updated_at) VALUES (?, ?, ?, 'staff', 'active', ?, ?)",
            (user_id, email, display_name, now, now),
        ),
        (
            "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
            " VALUES (?, ?, ?, ?)",
            (user_id, password_hash, now, now),
        ),
    ]
    for role_id in roles:
        statements.append(
            (
                "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
                " VALUES (?, ?, ?, ?)",
                (user_id, role_id, now, actor.user_id),
            )
        )
    statements.append(
        audit_statement(
            action="user.created",
            entity_type="user",
            entity_id=user_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"email": email, "roles": roles, "passwordStored": False},
        )
    )
    await db.batch(statements)
    return {"id": user_id, "email": email, "status": "active"}


async def set_user_status(
    db: Database,
    actor: Principal,
    request_id: str,
    user_id: str,
    *,
    status: str,
) -> dict[str, Any]:
    if status not in _ASSIGNABLE_STATUSES:
        raise ValidationAppError("Status must be active, disabled, or invited.")
    if user_id == actor.user_id and status != "active":
        raise ValidationAppError("You cannot disable your own account.")
    current = await db.fetch_one(
        "SELECT id, status FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)
    )
    if current is None:
        raise NotFoundError("User not found.")

    now = utc_now_iso()
    await db.batch(
        [
            ("UPDATE users SET status = ?, updated_at = ? WHERE id = ?", (status, now, user_id)),
            audit_statement(
                action="user.status_changed",
                entity_type="user",
                entity_id=user_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": status},
            ),
        ]
    )
    return {"id": user_id, "status": status}


async def create_farm_owner(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    email: str,
    display_name: str,
    farm_id: str,
    password: str,
) -> dict[str, Any]:
    """Create a farm-owner sub-admin: a staff user with the farm_owner role, a
    password, and a membership scoping them to one farm. Only unrestricted admins
    (no farm scope of their own) may call this — enforced at the endpoint."""
    email = (email or "").strip().lower()
    display_name = (display_name or "").strip()
    settings = get_settings()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationAppError("Enter a valid email address.")
    if len(display_name) < 2:
        raise ValidationAppError("Enter the person's name.")
    if len(password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )
    if await db.fetch_one("SELECT id FROM users WHERE email = ?", (email,)) is not None:
        raise ConflictError("A user with this email already exists.")

    farm = await db.fetch_one("SELECT id, name FROM farms WHERE id = ?", (farm_id,))
    if farm is None:
        raise NotFoundError("Farm not found.")
    role = await db.fetch_one("SELECT id FROM roles WHERE key = 'farm_owner'")
    if role is None:
        raise NotFoundError("The farm_owner role is not configured.")

    user_id = new_id("usr")
    now = utc_now_iso()
    password_hash = hash_password(password, iterations=settings.pbkdf2_iterations)
    await db.batch(
        [
            (
                "INSERT INTO users (id, email, display_name, user_type, status,"
                " created_at, updated_at) VALUES (?, ?, ?, 'staff', 'active', ?, ?)",
                (user_id, email, display_name, now, now),
            ),
            (
                "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
                " VALUES (?, ?, ?, ?)",
                (user_id, role["id"], now, actor.user_id),
            ),
            (
                "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)",
                (user_id, password_hash, now, now),
            ),
            (
                "INSERT INTO farm_members (user_id, farm_id, created_at, created_by)"
                " VALUES (?, ?, ?, ?)",
                (user_id, farm_id, now, actor.user_id),
            ),
            audit_statement(
                action="farm_owner.created",
                entity_type="user",
                entity_id=user_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"email": email, "farmId": farm_id},
            ),
        ]
    )
    return {"id": user_id, "email": email, "farmId": farm_id, "farmName": farm["name"]}


async def set_user_roles(
    db: Database,
    actor: Principal,
    request_id: str,
    user_id: str,
    *,
    role_ids: list[str],
) -> dict[str, Any]:
    current = await db.fetch_one(
        "SELECT id FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,)
    )
    if current is None:
        raise NotFoundError("User not found.")
    roles = await _validate_roles(db, role_ids)

    now = utc_now_iso()
    statements: list[Any] = [("DELETE FROM user_roles WHERE user_id = ?", (user_id,))]
    for role_id in roles:
        statements.append(
            (
                "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
                " VALUES (?, ?, ?, ?)",
                (user_id, role_id, now, actor.user_id),
            )
        )
    statements.append(
        audit_statement(
            action="user.roles_changed",
            entity_type="user",
            entity_id=user_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after={"roles": roles},
        )
    )
    await db.batch(statements)
    return {"id": user_id, "roles": roles}


async def delete_users(
    db: Database,
    actor: Principal,
    request_id: str,
    user_ids: list[str],
) -> dict[str, Any]:
    unique_ids = list(dict.fromkeys(user_ids))
    if not unique_ids:
        raise ValidationAppError("Select at least one user to delete.")
    if actor.user_id in unique_ids:
        raise ValidationAppError("You cannot delete your own owner account.")

    placeholders = ", ".join("?" for _ in unique_ids)
    rows = await db.fetch_all(
        f"""
        SELECT u.id, u.email, u.display_name,
          EXISTS (
            SELECT 1
            FROM user_roles ur
            JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = u.id AND r.key = 'super_admin'
          ) AS is_super_admin
        FROM users u
        WHERE u.id IN ({placeholders})
          AND u.user_type = 'staff'
          AND u.deleted_at IS NULL
        """,
        unique_ids,
    )
    found = {row["id"] for row in rows}
    missing = [user_id for user_id in unique_ids if user_id not in found]
    if missing:
        raise NotFoundError("One or more users were not found.")
    if any(row["is_super_admin"] for row in rows):
        raise PermissionDeniedError("Owner accounts cannot be deleted.")

    now = utc_now_iso()
    statements: list[Any] = []
    for row in rows:
        deleted_email = f"deleted-{row['id']}@truegrit.local"
        statements.extend(
            [
                (
                    """
                    UPDATE users
                    SET status = 'disabled',
                        email = ?,
                        deleted_at = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (deleted_email, now, now, row["id"]),
                ),
                (
                    "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                    (now, row["id"]),
                ),
                audit_statement(
                    action="user.deleted",
                    entity_type="user",
                    entity_id=row["id"],
                    actor_id=actor.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"email": row["email"], "displayName": row["display_name"]},
                    after={"deletedAt": now, "sessionsRevoked": True},
                ),
            ]
        )
    await db.batch(statements)
    return {"deletedIds": [row["id"] for row in rows], "count": len(rows)}


async def adopt_bootstrap_owner(
    db: Database,
    request_id: str,
    *,
    user_id: str,
    email: str,
    password: str,
) -> None:
    """Hand the owner account its identity and password from `.env`, once.

    `ADMIN_LOGIN_EMAIL`/`ADMIN_LOGIN_PASSWORD` are a bootstrap, not a spare key:
    they open the owner account only while it has no password of its own. The
    first sign-in copies both onto the account — the address so the console shows
    the real operator and reset mail reaches a live inbox, and the password as a
    hash the account owns. After this, only the stored password authenticates,
    which is what makes changing it in the console revoke the old one instead of
    leaving `.env` as a second way in.

    The password is deliberately not held to `password_min_length`: it is
    whatever the operator already has in `.env`, and rejecting it here would lock
    them out of the console that exists to fix it. `change_own_password` does
    enforce the minimum, so the next password is a strong one.
    """
    settings = get_settings()
    email = (email or "").strip().lower()
    # users.email is UNIQUE: a customer who registered with this address would
    # make the update fail mid-batch. Refuse loudly instead, leaving the account
    # unadopted and the bootstrap credential still usable.
    conflict = await db.fetch_one(
        "SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id)
    )
    if conflict is not None:
        raise ConflictError(
            "ADMIN_LOGIN_EMAIL already belongs to another account. "
            "Set a different address for the owner console login."
        )

    now = utc_now_iso()
    password_hash = hash_password(password, iterations=settings.pbkdf2_iterations)
    await db.batch(
        [
            ("UPDATE users SET email = ?, updated_at = ? WHERE id = ?", (email, now, user_id)),
            (
                "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash,"
                " updated_at = excluded.updated_at",
                (user_id, password_hash, now, now),
            ),
            audit_statement(
                action="owner.bootstrapped",
                entity_type="user",
                entity_id=user_id,
                actor_id=user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "email": email,
                    "credentialAdopted": True,
                    "passwordStored": False,
                },
            ),
        ]
    )


async def change_own_password(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    current_password: str,
    new_password: str,
    keep_session_token_hash: str | None,
) -> dict[str, Any]:
    """Rotate the signed-in user's own password.

    The current password is required even though the caller already holds a
    session: without it, a borrowed screen or a stolen cookie could lock the real
    owner out of their own console. Every other session is revoked so a rotation
    ejects whoever prompted it; the caller's own session survives, because
    signing someone out of the page they just used is noise, not security.
    """
    settings = get_settings()
    if len(new_password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )
    if new_password == current_password:
        raise ValidationAppError("The new password must differ from the current one.")

    credential = await db.fetch_one(
        "SELECT password_hash FROM user_credentials WHERE user_id = ?", (actor.user_id,)
    )
    if credential is None:
        raise ValidationAppError(
            "This account has no password yet. Use the reset link on the sign-in page to set one."
        )
    if not verify_password(current_password, credential["password_hash"]):
        raise AuthenticationError("Current password is incorrect.")

    now = utc_now_iso()
    password_hash = hash_password(new_password, iterations=settings.pbkdf2_iterations)
    await db.batch(
        [
            (
                "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash,"
                " updated_at = excluded.updated_at",
                (actor.user_id, password_hash, now, now),
            ),
            (
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL"
                " AND token_hash != ?",
                (now, actor.user_id, keep_session_token_hash or ""),
            ),
            audit_statement(
                action="password.changed",
                entity_type="user",
                entity_id=actor.user_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "email": actor.email,
                    "credentialChanged": True,
                    "passwordStored": False,
                    "otherSessionsRevoked": True,
                },
            ),
        ]
    )
    return {"ok": True}


async def reset_farm_owner_password(
    db: Database,
    actor: Principal,
    request_id: str,
    user_id: str,
) -> dict[str, Any]:
    """Generate a one-time temporary password for a farm-owner account.

    The plain password is returned to the caller once. Only its hash is stored,
    and existing sessions are revoked in the same transaction.
    """
    user = await db.fetch_one(
        """
        SELECT u.id, u.email, u.display_name, u.status, fm.farm_id
        FROM users u
        JOIN farm_members fm ON fm.user_id = u.id
        WHERE u.id = ? AND u.user_type = 'staff'
        """,
        (user_id,),
    )
    if user is None:
        raise NotFoundError("Farm owner not found.")
    if user["status"] == "disabled":
        raise ValidationAppError("Enable this farm owner before resetting their password.")

    settings = get_settings()
    temporary_password = _temporary_password(max(settings.password_min_length + 8, 18))
    password_hash = hash_password(
        temporary_password, iterations=settings.pbkdf2_iterations
    )
    now = utc_now_iso()
    await db.batch(
        [
            (
                """
                INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                  password_hash = excluded.password_hash,
                  updated_at = excluded.updated_at
                """,
                (user_id, password_hash, now, now),
            ),
            (
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, user_id),
            ),
            audit_statement(
                action="farm_owner.password_reset",
                entity_type="user",
                entity_id=user_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={
                    "email": user["email"],
                    "farmId": user["farm_id"],
                    "temporaryPasswordIssued": True,
                    "passwordStored": False,
                    "sessionsRevoked": True,
                },
            ),
        ]
    )
    return {
        "id": user_id,
        "email": user["email"],
        "temporaryPassword": temporary_password,
    }

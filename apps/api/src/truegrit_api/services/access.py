"""Staff access management: invite users, toggle status, assign roles.

Roles are collections of permissions; the API always checks permissions, never
role names. Every change is audited. An actor can never disable their own
account (which would be an easy way to lock everyone out by mistake).
"""

from __future__ import annotations

import re
from typing import Any

from truegrit_api.auth.passwords import hash_password
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_ASSIGNABLE_STATUSES = frozenset({"active", "disabled", "invited"})


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
    current = await db.fetch_one("SELECT id, status FROM users WHERE id = ?", (user_id,))
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
    current = await db.fetch_one("SELECT id FROM users WHERE id = ?", (user_id,))
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

"""Least-privilege release cockpit endpoints."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from truegrit_api.auth.dependencies import get_current_staff, get_database, require_owner
from truegrit_api.auth.passwords import hash_password
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import NotFoundError, PermissionDeniedError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.access import create_user, delete_users, set_user_status
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.deployments import DeploymentService
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["deployments"])


class VerifyStagingBody(BaseModel):
    sha: str = Field(min_length=40, max_length=40)
    notes: str = Field(min_length=3, max_length=100)


class PromoteBody(BaseModel):
    source: str
    target: str
    sha: str = Field(min_length=40, max_length=40)


class ReleaseUserBody(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=256)


class ReleaseUserStatusBody(BaseModel):
    status: Literal["active", "disabled"]


class ReleaseUserPasswordBody(BaseModel):
    password: str = Field(min_length=10, max_length=256)


async def get_deployment_service(request: Request) -> DeploymentService:
    service: DeploymentService | None = getattr(request.app.state, "deployments", None)
    if service is None:
        raise RuntimeError("Deployment service is not configured.")
    return service


async def require_release_access(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Principal:
    role = await db.fetch_one(
        """
        SELECT r.key
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = ? AND r.key IN ('super_admin', 'release_manager')
        LIMIT 1
        """,
        (principal.user_id,),
    )
    if role is None:
        raise PermissionDeniedError("Release cockpit access is required.")
    return principal


async def require_release_owner(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Principal:
    await require_owner(db, principal)
    return principal


async def require_release_manager_target(db: Database, user_id: str) -> None:
    """Keep cockpit user mutations scoped to release-manager accounts.

    The owner-facing route must not become a second, less visible way to alter
    arbitrary staff or owner accounts by supplying a hand-crafted user id.
    """
    user = await db.fetch_one(
        """
        SELECT u.id
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.id = ?
          AND u.user_type = 'staff'
          AND u.deleted_at IS NULL
          AND r.key = 'release_manager'
        LIMIT 1
        """,
        (user_id,),
    )
    if user is None:
        raise NotFoundError("Release user not found.")


@router.get("/deployments")
async def deployment_dashboard(
    _principal: Annotated[Principal, Depends(require_release_access)],
    service: Annotated[DeploymentService, Depends(get_deployment_service)],
) -> dict[str, Any]:
    return await service.dashboard()


@router.post("/deployments/verify-staging")
async def verify_staging(
    body: VerifyStagingBody,
    principal: Annotated[Principal, Depends(require_release_access)],
    service: Annotated[DeploymentService, Depends(get_deployment_service)],
) -> dict[str, Any]:
    return await service.verify_staging(body.sha, principal.display_name, body.notes)


@router.post("/deployments/promote")
async def promote(
    body: PromoteBody,
    principal: Annotated[Principal, Depends(require_release_access)],
    service: Annotated[DeploymentService, Depends(get_deployment_service)],
) -> dict[str, Any]:
    return await service.promote(body.source, body.target, body.sha, principal.display_name)


@router.get("/deployments/users")
async def release_users(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_release_owner)],
) -> dict[str, Any]:
    users = await db.fetch_all(
        """
        SELECT u.id, u.display_name, u.email, u.status, u.last_sign_in_at
        FROM users u
        JOIN user_roles ur ON ur.user_id = u.id
        JOIN roles r ON r.id = ur.role_id
        WHERE r.key = 'release_manager' AND u.deleted_at IS NULL
        ORDER BY u.display_name
        """
    )
    return {
        "items": [
            {
                "id": user["id"],
                "displayName": user["display_name"],
                "email": user["email"],
                "status": user["status"],
                "lastSignInAt": user["last_sign_in_at"],
            }
            for user in users
        ]
    }


@router.post("/deployments/users")
async def add_release_user(
    body: ReleaseUserBody,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_release_owner)],
) -> dict[str, Any]:
    result = await create_user(
        db,
        principal,
        getattr(request.state, "request_id", "unknown"),
        email=body.email,
        display_name=body.display_name,
        role_ids=["rol_release_manager"],
        password=body.password,
    )
    return {**result, "role": "release_manager"}


@router.delete("/deployments/users/{user_id}")
async def delete_release_user(
    user_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_release_owner)],
) -> dict[str, Any]:
    await require_release_manager_target(db, user_id)
    await delete_users(
        db,
        principal,
        getattr(request.state, "request_id", "unknown"),
        [user_id],
    )
    return {"ok": True}


@router.put("/deployments/users/{user_id}/status")
async def update_release_user_status(
    user_id: str,
    body: ReleaseUserStatusBody,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_release_owner)],
) -> dict[str, Any]:
    await require_release_manager_target(db, user_id)
    result = await set_user_status(
        db,
        principal,
        getattr(request.state, "request_id", "unknown"),
        user_id,
        status=body.status,
    )
    return {"ok": True, "status": result["status"]}


@router.put("/deployments/users/{user_id}/password")
async def reset_release_user_password(
    user_id: str,
    body: ReleaseUserPasswordBody,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_release_owner)],
) -> dict[str, Any]:
    await require_release_manager_target(db, user_id)
    settings = get_settings()
    if len(body.password) < settings.password_min_length:
        raise ValidationAppError(
            f"Password must be at least {settings.password_min_length} characters."
        )

    now = utc_now_iso()
    password_hash = hash_password(body.password, iterations=settings.pbkdf2_write_iterations)
    await db.batch(
        [
            (
                "INSERT INTO user_credentials (user_id, password_hash, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(user_id) DO UPDATE SET password_hash = excluded.password_hash,"
                " updated_at = excluded.updated_at",
                (user_id, password_hash, now, now),
            ),
            (
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (now, user_id),
            ),
            audit_statement(
                action="release_user.password_reset",
                entity_type="user",
                entity_id=user_id,
                actor_id=principal.user_id,
                request_id=getattr(request.state, "request_id", "unknown"),
                created_at=now,
                after={"passwordStored": False, "sessionsRevoked": True},
            ),
        ]
    )
    return {"ok": True}

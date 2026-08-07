"""Least-privilege release cockpit endpoints."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from truegrit_api.auth.dependencies import get_current_staff, get_database, require_owner
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import PermissionDeniedError
from truegrit_api.platform.database import Database
from truegrit_api.services.access import create_user
from truegrit_api.services.deployments import DeploymentService

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

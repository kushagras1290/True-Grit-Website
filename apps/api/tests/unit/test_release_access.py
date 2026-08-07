from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request

from truegrit_api.api.deployments import (
    ReleaseUserBody,
    add_release_user,
    require_release_access,
)
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import PermissionDeniedError
from truegrit_api.platform.database import build_local_database


def principal(user_id: str, email: str) -> Principal:
    return Principal(
        user_id=user_id,
        display_name="Release Test",
        email=email,
        user_type="staff",
    )


def test_owner_can_add_a_least_privilege_release_user() -> None:
    db = build_local_database()
    owner = principal("usr_admin", "admin@truegrit.test")
    request = Request({"type": "http", "headers": []})

    result = asyncio.run(
        add_release_user(
            ReleaseUserBody(
                email="release.operator@truegrit.test",
                display_name="Release Operator",
                password="safe-release-password",
            ),
            request,
            db,
            owner,
        )
    )

    role = asyncio.run(
        db.fetch_one(
            """
            SELECT r.key
            FROM user_roles ur JOIN roles r ON r.id = ur.role_id
            WHERE ur.user_id = ?
            """,
            (result["id"],),
        )
    )
    assert role == {"key": "release_manager"}
    assert (
        asyncio.run(require_release_access(db, principal(result["id"], result["email"]))).user_id
        == result["id"]
    )


def test_ordinary_staff_cannot_enter_release_cockpit() -> None:
    db = build_local_database()
    with pytest.raises(PermissionDeniedError, match="Release cockpit"):
        asyncio.run(require_release_access(db, principal("usr_editor", "editor@truegrit.test")))

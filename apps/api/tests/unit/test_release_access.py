from __future__ import annotations

import asyncio

import pytest
from starlette.requests import Request

from truegrit_api.api.deployments import (
    ReleaseUserBody,
    ReleaseUserPasswordBody,
    ReleaseUserStatusBody,
    add_release_user,
    delete_release_user,
    require_release_access,
    reset_release_user_password,
    update_release_user_status,
)
from truegrit_api.auth.passwords import verify_password_async
from truegrit_api.auth.principal import Principal
from truegrit_api.errors import NotFoundError, PermissionDeniedError
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


def test_owner_can_manage_release_user_lifecycle() -> None:
    db = build_local_database()
    owner = principal("usr_admin", "admin@truegrit.test")
    request = Request({"type": "http", "headers": []})
    created = asyncio.run(
        add_release_user(
            ReleaseUserBody(
                email="release.lifecycle@truegrit.test",
                display_name="Release Lifecycle",
                password="initial-release-password",
            ),
            request,
            db,
            owner,
        )
    )
    user_id = created["id"]

    status = asyncio.run(
        update_release_user_status(
            user_id,
            ReleaseUserStatusBody(status="disabled"),
            request,
            db,
            owner,
        )
    )
    assert status == {"ok": True, "status": "disabled"}

    asyncio.run(
        reset_release_user_password(
            user_id,
            ReleaseUserPasswordBody(password="replacement-release-password"),
            request,
            db,
            owner,
        )
    )
    credential = asyncio.run(
        db.fetch_one("SELECT password_hash FROM user_credentials WHERE user_id = ?", (user_id,))
    )
    assert credential is not None
    assert asyncio.run(
        verify_password_async("replacement-release-password", credential["password_hash"])
    )

    assert asyncio.run(delete_release_user(user_id, request, db, owner)) == {"ok": True}
    assert (
        asyncio.run(
            db.fetch_one("SELECT id FROM users WHERE id = ? AND deleted_at IS NULL", (user_id,))
        )
        is None
    )


def test_release_user_routes_reject_non_release_targets() -> None:
    db = build_local_database()
    owner = principal("usr_admin", "admin@truegrit.test")
    request = Request({"type": "http", "headers": []})

    with pytest.raises(NotFoundError, match="Release user"):
        asyncio.run(
            update_release_user_status(
                "usr_editor",
                ReleaseUserStatusBody(status="disabled"),
                request,
                db,
                owner,
            )
        )

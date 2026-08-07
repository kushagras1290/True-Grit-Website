from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def as_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def test_owner_can_manage_release_user_through_cockpit_routes(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)
    created = client.post(
        "/v1/admin/deployments/users",
        json={
            "email": "release.route@truegrit.test",
            "display_name": "Release Route",
            "password": "initial-release-password",
        },
    )
    assert created.status_code == 200, created.text
    user_id = created.json()["id"]

    reset = client.put(
        f"/v1/admin/deployments/users/{user_id}/password",
        json={"password": "replacement-release-password"},
    )
    assert reset.status_code == 200, reset.text
    assert reset.json() == {"ok": True}

    disabled = client.put(
        f"/v1/admin/deployments/users/{user_id}/status",
        json={"status": "disabled"},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json() == {"ok": True, "status": "disabled"}

    deleted = client.delete(f"/v1/admin/deployments/users/{user_id}")
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True}

    remaining = client.get("/v1/admin/deployments/users")
    assert remaining.status_code == 200, remaining.text
    assert user_id not in {item["id"] for item in remaining.json()["items"]}


def test_cockpit_user_mutations_are_owner_only_and_release_manager_scoped(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)

    ordinary_staff = client.put(
        "/v1/admin/deployments/users/usr_editor/status",
        json={"status": "disabled"},
    )
    assert ordinary_staff.status_code == 404, ordinary_staff.text

    created = client.post(
        "/v1/admin/deployments/users",
        json={
            "email": "release.owner-gate@truegrit.test",
            "display_name": "Release Owner Gate",
            "password": "initial-release-password",
        },
    )
    assert created.status_code == 200, created.text

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    forbidden = client.put(
        f"/v1/admin/deployments/users/{created.json()['id']}/status",
        json={"status": "disabled"},
    )
    assert forbidden.status_code == 403, forbidden.text

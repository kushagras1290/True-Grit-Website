"""Farm partnership applications, end to end.

The route is deliberately unauthenticated, so these tests carry most of the
weight for it: what a grower may send, what they may not, who can read the
queue afterwards, and which decisions are terminal.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

VALID_APPLICATION: dict[str, Any] = {
    "contactName": "Devika Kulkarni",
    "contactEmail": "Devika@Example.Test",
    "contactPhone": "98765 43210",
    "farmName": "Sahyadri Organics",
    "region": "Satara district",
    "state": "Maharashtra",
    "city": "Wai",
    "pincode": "412803",
    "establishedYear": 1998,
    "landAreaAcres": "14 acres",
    "certification": "India Organic, in conversion year 2",
    "primaryProduce": "Alphonso mango, turmeric, finger millet",
    "farmingPractices": "No synthetic inputs since 2016; we make our own compost.",
    "websiteUrl": "https://sahyadri.example.test",
    "message": "We supply two local co-operatives and would like to reach further.",
}


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_editor(client: TestClient, db: SQLiteDatabase) -> None:
    """Content Editor holds no farm_requests grant — the negative case."""
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))


def submit(client: TestClient, **overrides: Any):
    return client.post("/v1/public/farm-partnerships", json={**VALID_APPLICATION, **overrides})


# --- Applying ---------------------------------------------------------------


def test_anyone_can_apply_without_an_account(client: TestClient, db: SQLiteDatabase):
    """The whole point of the feature: no sign-in, no sign-up wall."""
    response = submit(client)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "submitted"

    row = db._conn.execute(
        "SELECT * FROM farm_partnership_requests WHERE id = ?", (response.json()["id"],)
    ).fetchone()
    assert row["farm_name"] == "Sahyadri Organics"
    # Normalised on the way in, both of them: the email lower-cased, the phone
    # to E.164, so a duplicate check and a call-back both work.
    assert row["contact_email"] == "devika@example.test"
    assert row["contact_phone"] == "+919876543210"
    # Anonymous application: nothing to attribute it to.
    assert row["submitter_user_id"] is None


def test_a_signed_in_customer_is_attributed(
    client: TestClient, db: SQLiteDatabase, sms_outbox: list
):
    """Signing in is not required, but when someone happens to be signed in the
    application is linked to them — useful context for whoever calls back."""
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_grower', 'grower@example.test', 'Grower', 'customer', 'active',"
        " '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')"
    )
    db._conn.commit()
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_grower"))

    response = submit(client)
    assert response.status_code == 200, response.text
    row = db._conn.execute(
        "SELECT submitter_user_id FROM farm_partnership_requests WHERE id = ?",
        (response.json()["id"],),
    ).fetchone()
    assert row["submitter_user_id"] == "usr_grower"


def test_a_stale_cookie_does_not_break_the_public_form(client: TestClient):
    """`get_optional_customer` must never raise. A junk session cookie is a
    normal state for a public form, not a 401."""
    client.cookies.set(SESSION_COOKIE, "not-a-real-session-token")
    response = submit(client)
    assert response.status_code == 200, response.text


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("contactPhone", "1234567890"),  # 10 digits, not an Indian mobile
        ("contactEmail", "not-an-email"),
        ("farmName", "S"),  # below the minimum
        ("message", "too short"),
        ("websiteUrl", "javascript:alert(1)"),  # rendered as a link in admin
        ("establishedYear", 1500),
    ],
)
def test_bad_fields_are_refused(client: TestClient, field: str, value: Any):
    assert submit(client, **{field: value}).status_code == 422


def test_applications_can_be_closed_without_a_deploy(client: TestClient, db: SQLiteDatabase):
    """Hiding the storefront form stops the honest visitor; the route has to
    refuse too."""
    db._conn.execute("UPDATE app_settings SET value = '0' WHERE key = 'farm_partnerships.enabled'")
    db._conn.commit()

    assert client.get("/v1/public/farm-partnerships/settings").json()["enabled"] is False
    assert submit(client).status_code == 403


def test_a_grower_cannot_submit_the_same_application_all_day(client: TestClient):
    """Per-contact quota, counted from the applications themselves rather than
    from an attempt bucket, so a mistyped field never locks anyone out."""
    for _ in range(3):
        assert submit(client).status_code == 200
    fourth = submit(client)
    assert fourth.status_code == 429
    assert fourth.json()["error"]["code"] == "rate_limited"

    # A different grower is unaffected — the quota is per contact, not per IP.
    assert (
        submit(client, contactEmail="other@example.test", contactPhone="9123456780").status_code
        == 200
    )


# --- Reviewing --------------------------------------------------------------


def test_admin_reviews_and_approves(client: TestClient, db: SQLiteDatabase):
    created = submit(client)
    entry_id = created.json()["id"]

    as_admin(client, db)
    listed = client.get("/v1/admin/farm-requests")
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["farmName"] == "Sahyadri Organics"

    detail = client.get(f"/v1/admin/farm-requests/{entry_id}")
    assert detail.status_code == 200
    assert detail.json()["primaryProduce"].startswith("Alphonso")

    # Walk the pipeline: an application usually spends its life at 'contacted'.
    assert (
        client.post(
            f"/v1/admin/farm-requests/{entry_id}/decide", json={"decision": "contacted"}
        ).status_code
        == 200
    )
    approved = client.post(
        f"/v1/admin/farm-requests/{entry_id}/decide",
        json={"decision": "approved", "note": "Visited on the 12th; papers in order."},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    # Terminal: re-deciding would rewrite a record the applicant was emailed.
    reversed_decision = client.post(
        f"/v1/admin/farm-requests/{entry_id}/decide",
        json={"decision": "rejected", "note": "changed our mind"},
    )
    assert reversed_decision.status_code == 409


def test_rejection_requires_a_reason(client: TestClient, db: SQLiteDatabase):
    entry_id = submit(client).json()["id"]
    as_admin(client, db)
    assert (
        client.post(
            f"/v1/admin/farm-requests/{entry_id}/decide", json={"decision": "rejected"}
        ).status_code
        == 422
    )
    assert (
        client.post(
            f"/v1/admin/farm-requests/{entry_id}/decide",
            json={"decision": "rejected", "note": "Outside our delivery range for now."},
        ).status_code
        == 200
    )


def test_only_an_approved_application_can_be_linked_to_a_farm(
    client: TestClient, db: SQLiteDatabase
):
    """Approval decides; it does not onboard. The link is recorded afterwards,
    and only once the decision supports it."""
    entry_id = submit(client).json()["id"]
    as_admin(client, db)

    too_early = client.post(
        f"/v1/admin/farm-requests/{entry_id}/link-farm", json={"farmId": "farm_devika"}
    )
    assert too_early.status_code == 409

    client.post(f"/v1/admin/farm-requests/{entry_id}/decide", json={"decision": "approved"})
    assert (
        client.post(
            f"/v1/admin/farm-requests/{entry_id}/link-farm", json={"farmId": "farm_devika"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/v1/admin/farm-requests/{entry_id}/link-farm", json={"farmId": "farm_nope"}
        ).status_code
        == 404
    )


def test_open_count_drives_the_badge(client: TestClient, db: SQLiteDatabase):
    first = submit(client).json()["id"]
    submit(client, contactEmail="two@example.test", contactPhone="9123456781")

    as_admin(client, db)
    assert client.get("/v1/admin/farm-requests/open-count").json()["count"] == 2
    client.post(
        f"/v1/admin/farm-requests/{first}/decide",
        json={"decision": "rejected", "note": "Not a fit."},
    )
    # 'contacted' still counts as open; only the terminal states clear it.
    assert client.get("/v1/admin/farm-requests/open-count").json()["count"] == 1


def test_the_queue_is_permission_gated(client: TestClient, db: SQLiteDatabase):
    submit(client)
    as_editor(client, db)
    assert client.get("/v1/admin/farm-requests").status_code == 403


def test_a_farm_owner_cannot_see_other_growers_applications(client: TestClient, db: SQLiteDatabase):
    """A farm-scoped sub-admin has no business reading who else wants in, even
    if a future role grant hands them the permission."""
    db._conn.execute(
        "INSERT OR IGNORE INTO role_permissions (role_id, permission_id)"
        " SELECT 'rol_farm_owner', id FROM permissions WHERE key = 'farm_requests.view'"
    )
    db._conn.commit()
    submit(client)

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/farm-requests").status_code == 403


def test_spam_can_be_deleted_outright(client: TestClient, db: SQLiteDatabase):
    entry_id = submit(client).json()["id"]
    as_admin(client, db)
    assert client.delete(f"/v1/admin/farm-requests/{entry_id}").status_code == 200
    assert client.get(f"/v1/admin/farm-requests/{entry_id}").status_code == 404

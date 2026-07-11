"""Authorization matrix and the publish loop: no session -> 401, wrong permission
-> 403, correct permission -> success with audit + outbox written atomically."""

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def test_admin_requires_session(client: TestClient):
    assert client.get("/v1/admin/me").status_code == 401
    assert client.get("/v1/admin/products").status_code == 401
    body = client.get("/v1/admin/products").json()
    assert body["error"]["code"] == "authentication_required"


def test_invalid_session_rejected(client: TestClient):
    client.cookies.set(SESSION_COOKIE, "forged-token")
    assert client.get("/v1/admin/me").status_code == 401


def test_permission_matrix(client: TestClient, db: SQLiteDatabase):
    editor_token = create_session(db, "usr_editor")  # content editor: no products.view
    client.cookies.set(SESSION_COOKIE, editor_token)
    assert client.get("/v1/admin/products").status_code == 403
    assert client.get("/v1/admin/categories").status_code == 200

    pm_token = create_session(db, "usr_pm")  # product manager: products.view, no publish
    client.cookies.set(SESSION_COOKIE, pm_token)
    assert client.get("/v1/admin/products").status_code == 200
    assert client.post("/v1/admin/categories/cat_fresh_fruits/publish").status_code == 403


def test_me_returns_permissions(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    body = client.get("/v1/admin/me").json()
    assert body["displayName"] == "Asha Rao"
    assert "categories.publish" in body["permissions"]


def test_product_list_shape(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    items = client.get("/v1/admin/products").json()["items"]
    assert len(items) == 5
    alphonso = next(item for item in items if item["id"] == "prd_alphonso")
    assert alphonso["sku"] == "TRG-MNG-1KG"
    assert alphonso["priceRange"] == "899-1699"
    assert alphonso["availableStock"] == 174  # (120-4) + (60-2)


def test_publish_category_writes_audit_and_outbox(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.post("/v1/admin/categories/cat_fresh_fruits/publish")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["version"] == 1

    audit_rows = db._conn.execute(
        "SELECT action FROM audit_logs WHERE entity_id = 'cat_fresh_fruits'"
    ).fetchall()
    assert [row["action"] for row in audit_rows] == ["category.published"]

    outbox_rows = db._conn.execute(
        "SELECT event_type, status FROM outbox_events WHERE aggregate_id = 'cat_fresh_fruits'"
    ).fetchall()
    assert [(row["event_type"], row["status"]) for row in outbox_rows] == [
        ("content.category.published.v1", "pending")
    ]

    version = db._conn.execute(
        "SELECT workflow_state, version_number FROM category_versions"
        " WHERE category_id = 'cat_fresh_fruits'"
    ).fetchone()
    assert version["workflow_state"] == "published"

    # Second publish creates version 2 — versions are immutable and monotonic.
    second = client.post("/v1/admin/categories/cat_fresh_fruits/publish").json()
    assert second["version"] == 2


def test_publish_unknown_category_404(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    assert client.post("/v1/admin/categories/cat_missing/publish").status_code == 404


def test_inventory_view_permission(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_ops"))
    items = client.get("/v1/admin/inventory").json()["items"]
    assert items[0]["sku"] == "TRG-RJM-500"  # closest to reorder threshold sorts first
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.get("/v1/admin/inventory").status_code == 403

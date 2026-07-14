"""Integration tests for the operations-console write endpoints:
products, categories, inventory, users, and orders."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_editor(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))


# --- Products ---------------------------------------------------------------


def test_product_create_edit_publish_archive(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)

    created = client.post(
        "/v1/admin/products",
        json={"name": "Test Turmeric", "productType": "pantry"},
    )
    assert created.status_code == 200
    product_id = created.json()["id"]
    assert created.json()["status"] == "draft"

    detail = client.get(f"/v1/admin/products/{product_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Test Turmeric"

    updated = client.patch(
        f"/v1/admin/products/{product_id}",
        json={"name": "Test Turmeric Powder", "shortDescription": "Single-origin turmeric root."},
    )
    assert updated.status_code == 200

    published = client.post(f"/v1/admin/products/{product_id}/publish", json={})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["version"] == 1

    assert client.get(f"/v1/admin/products/{product_id}").json()["name"] == "Test Turmeric Powder"

    archived = client.post(f"/v1/admin/products/{product_id}/archive")
    assert archived.status_code == 200
    assert client.get(f"/v1/admin/products/{product_id}").status_code == 404


def test_product_create_is_permission_gated(client: TestClient, db: SQLiteDatabase):
    as_editor(client, db)  # content editor has no products.create
    response = client.post("/v1/admin/products", json={"name": "Blocked", "productType": "pantry"})
    assert response.status_code == 403


def test_product_duplicate_slug_conflicts(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/products",
        json={"name": "Alphonso Twin", "productType": "fruit", "slug": "organic-alphonso-mangoes"},
    )
    assert response.status_code == 409


def test_product_publish_writes_audit(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Audited Product", "productType": "pantry"}
    ).json()["id"]
    client.post(f"/v1/admin/products/{product_id}/publish", json={})
    actions = [row["action"] for row in client.get("/v1/admin/audit").json()["items"]]
    assert "product.published" in actions
    assert "product.created" in actions


# --- Categories -------------------------------------------------------------


def test_category_create_edit_publish(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    created = client.post(
        "/v1/admin/categories",
        json={"name": "Test Superfoods", "heroTitle": "Powerful pantry"},
    )
    assert created.status_code == 200
    category_id = created.json()["id"]

    updated = client.patch(
        f"/v1/admin/categories/{category_id}",
        json={"heroDescription": "Nutrient-dense staples.", "visibility": "public"},
    )
    assert updated.status_code == 200
    assert client.get(f"/v1/admin/categories/{category_id}").json()["heroDescription"] == (
        "Nutrient-dense staples."
    )

    published = client.post(f"/v1/admin/categories/{category_id}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"


def test_category_update_rejects_bad_visibility(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    category_id = client.post("/v1/admin/categories", json={"name": "Visibility Test"}).json()["id"]
    response = client.patch(f"/v1/admin/categories/{category_id}", json={"visibility": "nonsense"})
    assert response.status_code == 422


# --- Inventory --------------------------------------------------------------


def test_inventory_adjustment_persists_and_audits(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "TRG-MNG-1KG",
            "quantityDelta": 10,
            "reasonCode": "receipt",
            "note": "Restock delivery",
        },
    )
    assert response.status_code == 200
    assert response.json()["onHand"] == 130  # seeded 120 + 10

    inventory = client.get("/v1/admin/inventory").json()["items"]
    mango = next(row for row in inventory if row["sku"] == "TRG-MNG-1KG")
    assert mango["onHand"] == 130
    assert "inventory.adjusted" in [
        row["action"] for row in client.get("/v1/admin/audit").json()["items"]
    ]


def test_inventory_adjustment_cannot_go_below_reserved(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "TRG-MNG-1KG",
            "quantityDelta": -1000,
            "reasonCode": "write_off",
            "note": "Spoilage batch",
        },
    )
    assert response.status_code == 422


# --- Users & roles ----------------------------------------------------------


def test_users_list_invite_and_status(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert client.get("/v1/admin/roles").status_code == 200

    users = client.get("/v1/admin/users").json()["items"]
    assert any(u["email"] == "admin@truegrit.test" for u in users)

    role_id = client.get("/v1/admin/roles").json()["items"][0]["id"]
    invited = client.post(
        "/v1/admin/users/invite",
        json={"email": "newstaff@truegrit.test", "displayName": "New Staff", "roleIds": [role_id]},
    )
    assert invited.status_code == 200
    new_id = invited.json()["id"]

    disabled = client.patch(f"/v1/admin/users/{new_id}/status", json={"status": "disabled"})
    assert disabled.status_code == 200


def test_user_cannot_disable_self(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.patch("/v1/admin/users/usr_admin/status", json={"status": "disabled"})
    assert response.status_code == 422


# --- Orders -----------------------------------------------------------------


def test_orders_list_detail_and_transition(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    orders = client.get("/v1/admin/orders").json()["items"]
    assert {order["publicReference"] for order in orders} >= {"TG-1001", "TG-1002"}

    detail = client.get("/v1/admin/orders/ord_1001")
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 1

    moved = client.patch("/v1/admin/orders/ord_1002/status", json={"status": "confirmed"})
    assert moved.status_code == 200
    assert moved.json()["orderStatus"] == "confirmed"


def test_order_invalid_transition_conflicts(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.patch("/v1/admin/orders/ord_1002/status", json={"status": "completed"})
    assert response.status_code == 409

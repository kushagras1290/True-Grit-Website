"""Integration tests for farm-owner sub-admins: per-user staff login and
farm-scoped catalogue/inventory access."""

from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.config import get_settings
from truegrit_api.platform.database import SQLiteDatabase


@pytest.fixture(autouse=True)
def _fast_hashing(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("pbkdf2_iterations", "1000")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def as_farm_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))


def test_farm_owner_can_sign_in_with_password(client: TestClient):
    response = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner@devika.test", "password": "devikafarm1"},
    )
    assert response.status_code == 200

    me = client.get("/v1/admin/me").json()
    assert me["farmId"] == "farm_devika"
    assert me["farmName"] == "Devika Organics"
    assert "products.view" in me["permissions"]


def test_env_owner_login_can_use_seeded_super_admin(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("ADMIN_LOGIN_EMAIL", "owner-login@truegrit.test")
    monkeypatch.setenv("ADMIN_LOGIN_PASSWORD", "owner-secret")
    get_settings.cache_clear()

    response = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner-login@truegrit.test", "password": "owner-secret"},
    )
    assert response.status_code == 200

    me = client.get("/v1/admin/me").json()
    assert me["id"] == "usr_admin"
    assert me["farmId"] is None
    assert "users.manage_roles" in me["permissions"]


def test_farm_owner_wrong_password_rejected(client: TestClient):
    response = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner@devika.test", "password": "wrong-password"},
    )
    assert response.status_code == 401


def test_farm_owner_sees_only_own_farm_products(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    names = [row["name"] for row in client.get("/v1/admin/products").json()["items"]]
    assert "Organic Alphonso Mangoes" in names  # farm_devika
    assert "Himalayan Red Rajma" not in names  # farm_himgiri


def test_farm_owner_cannot_open_foreign_product(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    assert client.get("/v1/admin/products/prd_alphonso").status_code == 200
    assert client.get("/v1/admin/products/prd_rajma").status_code == 404


def test_farm_owner_created_product_is_scoped_to_their_farm(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Devika Mango Pulp", "productType": "pantry"}
    ).json()["id"]
    farm_id = db._conn.execute(
        "SELECT farm_id FROM products WHERE id = ?", (product_id,)
    ).fetchone()[0]
    assert farm_id == "farm_devika"
    # And it now shows in their scoped list.
    names = [row["name"] for row in client.get("/v1/admin/products").json()["items"]]
    assert "Devika Mango Pulp" in names


def test_farm_owner_can_upload_product_images(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    response = client.post(
        "/v1/admin/media/images",
        json={
            "filename": "mango.png",
            "contentType": "image/png",
            "dataBase64": base64.b64encode(b"fake-png").decode("ascii"),
        },
    )
    assert response.status_code == 200
    assert response.json()["url"].endswith(".png")


def test_farm_owner_cannot_adjust_foreign_inventory(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    response = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "TRG-RJM-500",  # rajma, a foreign farm's variant
            "quantityDelta": 5,
            "reasonCode": "receipt",
            "note": "Should be blocked",
        },
    )
    assert response.status_code == 404


def test_farm_owner_inventory_is_scoped(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    skus = {row["sku"] for row in client.get("/v1/admin/inventory").json()["items"]}
    assert "TRG-MNG-1KG" in skus
    assert "TRG-RJM-500" not in skus


def test_super_admin_is_not_scoped(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    me = client.get("/v1/admin/me").json()
    assert me["farmId"] is None
    names = [row["name"] for row in client.get("/v1/admin/products").json()["items"]]
    assert "Himalayan Red Rajma" in names  # admin sees every farm

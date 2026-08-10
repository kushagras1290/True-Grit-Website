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


# `usr_farmowner` (email owner@devika.test, seeded in development.sql) used to be
# scoped to the demo catalogue's farm_devika via a `farm_members` row. Migration
# 0095 is a real, unconditional production cutover that retires the whole demo
# catalogue -- farms/articles/recipes are deleted outright, and the dev seed's
# own end-of-file cleanup pass (mirroring that cutover for fresh databases)
# cascades away that farm_members row along with farm_devika itself. So on a
# fresh test database `usr_farmowner` starts completely unscoped. These tests
# need real farm-scoping isolation (one user, two farms, never seeing the
# other's catalogue) which the live catalogue -- now a single farm, farm_vikas
# -- cannot exercise either. This fixture builds two small, obviously-synthetic
# farms of its own and points `usr_farmowner` at one of them, so every test
# below has a stable, self-contained north/south farm split to assert against.
NORTH_FARM_ID = "farm_test_north"
NORTH_FARM_NAME = "Northgate Growers Collective"
SOUTH_FARM_ID = "farm_test_south"
SOUTH_FARM_NAME = "Southbrook Family Farms"

NORTH_PRODUCT_ID = "prd_test_north_mango"
NORTH_PRODUCT_NAME = "Northgate Golden Mangoes"
NORTH_VARIANT_SKU = "TST-NORTH-MNG-1KG"

SOUTH_PRODUCT_ID = "prd_test_south_beans"
SOUTH_PRODUCT_NAME = "Southbrook Field Beans"
SOUTH_VARIANT_SKU = "TST-SOUTH-BNS-500G"


def _add_farm(db: SQLiteDatabase, farm_id: str, name: str) -> None:
    db._conn.execute(
        "INSERT INTO farms (id, name, slug, country_code, status, created_at,"
        " created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, 'IN', 'published', '2026-07-01T00:00:00Z', 'usr_admin',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (farm_id, name, farm_id.replace("_", "-")),
    )


def _add_farm_product(
    db: SQLiteDatabase,
    *,
    product_id: str,
    farm_id: str,
    name: str,
    sku: str,
    list_minor: int = 89_900,
    on_hand: int = 50,
    reserved: int = 0,
) -> None:
    slug = product_id.replace("prd_test_", "").replace("_", "-")
    variant_id = f"var_{product_id.removeprefix('prd_')}"
    price_id = f"vpr_{product_id.removeprefix('prd_')}"
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id,"
        " status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', ?, 'published',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, name, name, slug, farm_id),
    )
    db._conn.execute(
        "INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')",
        (variant_id, product_id, sku, name),
    )
    db._conn.execute(
        "INSERT INTO variant_prices (id, variant_id, market_code, currency_code,"
        " list_amount_minor, starts_at, status, created_at, created_by)"
        " VALUES (?, ?, 'IN', 'INR', ?, '2026-07-01T00:00:00Z', 'active',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (price_id, variant_id, list_minor),
    )
    db._conn.execute(
        "INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,"
        " reorder_threshold, version, updated_at)"
        " VALUES (?, 'loc_mumbai', ?, ?, 5, 1, '2026-07-01T00:00:00Z')",
        (variant_id, on_hand, reserved),
    )


@pytest.fixture(autouse=True)
def _farm_owner_baseline(db: SQLiteDatabase) -> None:
    """Two synthetic farms, each with one published product, plus
    `usr_farmowner` scoped to the north one -- the isolation scenario every
    test below relies on. See the module note above for why this cannot come
    from the seeded/live catalogue."""
    _add_farm(db, NORTH_FARM_ID, NORTH_FARM_NAME)
    _add_farm(db, SOUTH_FARM_ID, SOUTH_FARM_NAME)
    db._conn.execute(
        "INSERT OR REPLACE INTO farm_members (user_id, farm_id, created_at, created_by)"
        " VALUES ('usr_farmowner', ?, '2026-07-01T00:00:00Z', 'usr_admin')",
        (NORTH_FARM_ID,),
    )
    _add_farm_product(
        db,
        product_id=NORTH_PRODUCT_ID,
        farm_id=NORTH_FARM_ID,
        name=NORTH_PRODUCT_NAME,
        sku=NORTH_VARIANT_SKU,
        on_hand=50,
    )
    _add_farm_product(
        db,
        product_id=SOUTH_PRODUCT_ID,
        farm_id=SOUTH_FARM_ID,
        name=SOUTH_PRODUCT_NAME,
        sku=SOUTH_VARIANT_SKU,
        on_hand=30,
    )
    db._conn.commit()


def as_farm_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))


def test_farm_owner_can_sign_in_with_password(client: TestClient):
    response = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner@devika.test", "password": "devikafarm1"},
    )
    assert response.status_code == 200

    me = client.get("/v1/admin/me").json()
    assert me["farmId"] == NORTH_FARM_ID
    assert me["farmName"] == NORTH_FARM_NAME
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
    assert NORTH_PRODUCT_NAME in names  # farm_test_north
    assert SOUTH_PRODUCT_NAME not in names  # farm_test_south


def test_farm_owner_cannot_open_foreign_product(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    assert client.get(f"/v1/admin/products/{NORTH_PRODUCT_ID}").status_code == 200
    assert client.get(f"/v1/admin/products/{SOUTH_PRODUCT_ID}").status_code == 404


def test_farm_owner_created_product_is_scoped_to_their_farm(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Northgate Mango Pulp", "productType": "pantry"}
    ).json()["id"]
    farm_id = db._conn.execute(
        "SELECT farm_id FROM products WHERE id = ?", (product_id,)
    ).fetchone()[0]
    assert farm_id == NORTH_FARM_ID
    # And it now shows in their scoped list.
    names = [row["name"] for row in client.get("/v1/admin/products").json()["items"]]
    assert "Northgate Mango Pulp" in names


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
            "sku": SOUTH_VARIANT_SKU,  # a foreign farm's variant
            "quantityDelta": 5,
            "reasonCode": "receipt",
            "note": "Should be blocked",
        },
    )
    assert response.status_code == 404


def test_farm_owner_inventory_is_scoped(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    groups = client.get("/v1/admin/inventory").json()["items"]
    skus = {variant["sku"] for group in groups for variant in group["variants"]}
    assert NORTH_VARIANT_SKU in skus
    assert SOUTH_VARIANT_SKU not in skus


def test_super_admin_is_not_scoped(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    me = client.get("/v1/admin/me").json()
    assert me["farmId"] is None
    names = [
        row["name"]
        for row in client.get("/v1/admin/products", params={"search": SOUTH_PRODUCT_NAME}).json()[
            "items"
        ]
    ]
    assert SOUTH_PRODUCT_NAME in names  # admin sees every farm

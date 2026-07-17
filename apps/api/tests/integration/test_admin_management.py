"""Integration tests for the operations-console write endpoints:
products, categories, inventory, users, and orders."""

from __future__ import annotations

import base64

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}


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
        json={
            "name": "Test Turmeric Powder",
            "shortDescription": "Single-origin turmeric root.",
            "imageUrl": "https://images.example.test/turmeric.jpg",
            "imageAlt": "Fresh turmeric roots on a table",
        },
    )
    assert updated.status_code == 200

    published = client.post(f"/v1/admin/products/{product_id}/publish", json={})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["version"] == 1

    product = client.get(f"/v1/admin/products/{product_id}").json()
    assert product["name"] == "Test Turmeric Powder"
    assert product["imageUrl"] == "https://images.example.test/turmeric.jpg"
    list_items = client.get("/v1/admin/products").json()["items"]
    list_product = next(item for item in list_items if item["id"] == product_id)
    assert list_product["imageUrl"] == "https://images.example.test/turmeric.jpg"
    assert list_product["imageAlt"] == "Fresh turmeric roots on a table"
    public_product = client.get(f"/v1/public/products/{product['slug']}").json()
    assert public_product["imageUrl"] == "https://images.example.test/turmeric.jpg"

    archived = client.post(f"/v1/admin/products/{product_id}/archive")
    assert archived.status_code == 200
    assert client.get(f"/v1/admin/products/{product_id}").status_code == 404


def test_archive_lists_and_restores_products(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    archived = client.post("/v1/admin/products/prd_alphonso/archive")
    assert archived.status_code == 200

    archive = client.get("/v1/admin/archive")
    assert archive.status_code == 200
    rows = archive.json()["items"]
    product = next(row for row in rows if row["id"] == "prd_alphonso")
    assert product["kind"] == "product"
    assert product["status"] == "archived"

    restored = client.post("/v1/admin/archive/product/prd_alphonso/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    assert client.get("/v1/admin/products/prd_alphonso").status_code == 200
    assert client.get("/v1/admin/products/prd_alphonso").json()["status"] == "draft"
    actions = [row["action"] for row in client.get("/v1/admin/audit").json()["items"]]
    assert "product.restored" in actions


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
        json={
            "heroDescription": "Nutrient-dense staples.",
            "visibility": "public",
            "heroImageUrl": "https://images.example.test/superfoods.jpg",
            "heroImageAlt": "A spread of organic superfoods",
        },
    )
    assert updated.status_code == 200
    assert client.get(f"/v1/admin/categories/{category_id}").json()["heroDescription"] == (
        "Nutrient-dense staples."
    )

    published = client.post(f"/v1/admin/categories/{category_id}/publish")
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    public_category = client.get(f"/v1/public/categories/{created.json()['slug']}").json()
    assert public_category["hero"]["imageUrl"] == "https://images.example.test/superfoods.jpg"


def test_category_delete_hides_from_admin(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    category_id = client.post("/v1/admin/categories", json={"name": "Delete Me"}).json()["id"]
    deleted = client.delete(f"/v1/admin/categories/{category_id}")
    assert deleted.status_code == 200
    assert client.get(f"/v1/admin/categories/{category_id}").status_code == 404


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


# --- Media ------------------------------------------------------------------


def test_admin_image_upload_returns_public_media_url(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/media/images",
        json={
            "filename": "pixel.png",
            "contentType": "image/png",
            "dataBase64": base64.b64encode(b"fake-png").decode("ascii"),
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("http://testserver/media/images/img_")
    assert body["url"].endswith(".png")


def test_admin_raw_image_upload_returns_public_media_url(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/media/images?filename=pixel.png",
        content=b"fake-png",
        headers={"content-type": "image/png"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("http://testserver/media/images/img_")
    assert body["url"].endswith(".png")


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


def test_owner_can_delete_users_individually_and_in_bulk(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    role_id = "rol_inventory"
    first = client.post(
        "/v1/admin/users/invite",
        json={
            "email": "delete-one@truegrit.test",
            "displayName": "Delete One",
            "roleIds": [role_id],
        },
    ).json()["id"]
    second = client.post(
        "/v1/admin/users/invite",
        json={
            "email": "delete-two@truegrit.test",
            "displayName": "Delete Two",
            "roleIds": [role_id],
        },
    ).json()["id"]

    single = client.delete(f"/v1/admin/users/{first}")
    assert single.status_code == 200
    assert first not in {user["id"] for user in client.get("/v1/admin/users").json()["items"]}

    bulk = client.post("/v1/admin/users/bulk-delete", json={"userIds": [second]})
    assert bulk.status_code == 200
    assert bulk.json()["count"] == 1
    assert second not in {user["id"] for user in client.get("/v1/admin/users").json()["items"]}


def test_owner_account_cannot_be_deleted(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.delete("/v1/admin/users/usr_admin")
    assert response.status_code == 422


def test_owner_can_create_farm(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/farms",
        json={
            "name": "New Valley Farm",
            "farmerName": "Nira Shah",
            "region": "Pune, Maharashtra",
            "countryCode": "IN",
            "establishedYear": 2020,
            "summary": "A mixed organic vegetable farm.",
            "status": "published",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == "new-valley-farm"
    assert body["productCount"] == 0

    farms = client.get("/v1/admin/farms").json()["items"]
    assert any(farm["id"] == body["id"] and farm["name"] == "New Valley Farm" for farm in farms)
    audit = db._conn.execute(
        "SELECT action FROM audit_logs WHERE entity_id = ? ORDER BY created_at DESC LIMIT 1",
        (body["id"],),
    ).fetchone()
    assert audit["action"] == "farm.created"


def test_owner_can_update_and_delete_empty_farm(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    farm_id = client.post(
        "/v1/admin/farms",
        json={
            "name": "Editable Farm",
            "farmerName": "Nira Shah",
            "region": "Pune",
            "countryCode": "IN",
            "summary": "A farm ready for edits.",
            "status": "draft",
        },
    ).json()["id"]

    updated = client.patch(
        f"/v1/admin/farms/{farm_id}",
        json={
            "name": "Edited Farm",
            "slug": "edited-farm",
            "farmerName": "Nira S.",
            "region": "Nashik",
            "countryCode": "IN",
            "summary": "Updated public story.",
            "status": "published",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "Edited Farm"
    assert updated.json()["slug"] == "edited-farm"
    assert updated.json()["summary"] == "Updated public story."

    deleted = client.delete(f"/v1/admin/farms/{farm_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "archived"
    farms = client.get("/v1/admin/farms").json()["items"]
    assert farm_id not in {farm["id"] for farm in farms}


def test_owner_can_delete_farm_with_active_products(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.delete("/v1/admin/farms/farm_devika")
    assert response.status_code == 200
    assert response.json()["archivedProductCount"] == 1
    product = db._conn.execute(
        "SELECT status, archived_at FROM products WHERE id = 'prd_alphonso'"
    ).fetchone()
    assert product["status"] == "archived"
    assert product["archived_at"] is not None


def test_owner_can_issue_farm_owner_temporary_password(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    create_session(db, "usr_farmowner")

    response = client.post("/v1/admin/users/usr_farmowner/temporary-password")
    assert response.status_code == 200
    temporary_password = response.json()["temporaryPassword"]
    assert len(temporary_password) >= 18

    revoked_count = db._conn.execute(
        "SELECT COUNT(*) FROM sessions WHERE user_id = ? AND revoked_at IS NOT NULL",
        ("usr_farmowner",),
    ).fetchone()[0]
    assert revoked_count >= 1

    login = client.post(
        "/v1/admin/auth/login",
        json={"email": "owner@devika.test", "password": temporary_password},
    )
    assert login.status_code == 200

    audit = db._conn.execute(
        """
        SELECT action, actor_user_id, after_summary_json, source
        FROM audit_logs
        WHERE action = 'farm_owner.password_reset' AND entity_id = 'usr_farmowner'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert audit is not None
    assert audit["actor_user_id"] == "usr_admin"
    assert audit["source"] == "admin"
    assert '"passwordStored": false' in audit["after_summary_json"]
    assert temporary_password not in audit["after_summary_json"]


def test_farm_owner_cannot_issue_temporary_password(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post("/v1/admin/users/usr_farmowner/temporary-password")
    assert response.status_code == 403


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


def test_order_cancellation_releases_reserved_inventory(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    before = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    order = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 2}],
            "deliveryAddress": ADDRESS,
        },
    ).json()
    after_checkout = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    assert after_checkout["on_hand"] == before["on_hand"]
    assert after_checkout["reserved"] == before["reserved"] + 2

    client.cookies.clear()
    as_admin(client, db)
    cancelled = client.patch(f"/v1/admin/orders/{order['id']}/status", json={"status": "cancelled"})
    assert cancelled.status_code == 200
    after_cancel = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    assert after_cancel["on_hand"] == before["on_hand"]
    assert after_cancel["reserved"] == before["reserved"]


def test_completed_order_consumes_reserved_inventory(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    before = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    order = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    ).json()

    client.cookies.clear()
    as_admin(client, db)
    processing = client.patch(
        f"/v1/admin/orders/{order['id']}/status", json={"status": "processing"}
    )
    assert processing.status_code == 200
    completed = client.patch(f"/v1/admin/orders/{order['id']}/status", json={"status": "completed"})
    assert completed.status_code == 200
    after_complete = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    assert after_complete["on_hand"] == before["on_hand"] - 1
    assert after_complete["reserved"] == before["reserved"]


def test_owner_can_manage_site_control(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.patch(
        "/v1/admin/site-control",
        json={
            "announcementActive": True,
            "announcementMessage": "Fresh boxes ship Friday.",
            "announcementPath": "/shop",
            "heroHeading": "Owner managed homepage",
            "heroImageUrl": "/homepage-hero.png",
            "heroImageAlt": "Organic mangoes held in a sunlit orchard",
            "heroSlides": [
                {
                    "imageUrl": "/homepage-hero.png",
                    "imageAlt": "Organic mangoes held in a sunlit orchard",
                    "href": "/shop",
                    "label": "Explore the market",
                    "enabled": True,
                },
                {
                    "imageUrl": "/homepage-hero-greens.png",
                    "imageAlt": "Fresh leafy greens and herbs held in a farm field",
                    "href": "/category/organic-vegetables",
                    "label": "Shop fresh greens",
                    "enabled": False,
                },
            ],
            "seoTitle": "Owner managed SEO title",
            "seoDescription": "Owner managed SEO description.",
            "seoKeywords": "organic, farm fresh, true grit",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["heroHeading"] == "Owner managed homepage"
    assert body["heroImageUrl"] == "/homepage-hero.png"
    assert body["heroImageAlt"] == "Organic mangoes held in a sunlit orchard"
    assert body["heroSlides"][1]["enabled"] is False
    assert body["seoKeywords"] == "organic, farm fresh, true grit"

    public_home = client.get("/v1/public/home").json()
    assert public_home["seo"]["keywords"] == "organic, farm fresh, true grit"
    assert public_home["blocks"][0]["props"]["heading"] == "Owner managed homepage"
    assert public_home["blocks"][0]["props"]["imageUrl"] == "/homepage-hero.png"
    assert public_home["blocks"][0]["props"]["slides"][1]["href"] == "/category/organic-vegetables"
    assert public_home["blocks"][0]["props"]["slides"][1]["enabled"] is False


def test_farm_owner_cannot_manage_site_control(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/site-control").status_code == 403
    assert client.patch("/v1/admin/site-control", json={"seoTitle": "Nope"}).status_code == 403


def test_owner_can_manage_cms_page_seo_and_blocks(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    pages = client.get("/v1/admin/pages")
    assert pages.status_code == 200
    home = next(page for page in pages.json()["items"] if page["slug"] == "home")

    detail = client.get(f"/v1/admin/pages/{home['id']}")
    assert detail.status_code == 200
    blocks = detail.json()["blocks"]
    blocks.append(
        {
            "id": "blk_test_note",
            "type": "rich_text",
            "version": 1,
            "enabled": True,
            "props": {"paragraphs": ["Owner managed CMS block."]},
        }
    )
    response = client.patch(
        f"/v1/admin/pages/{home['id']}",
        json={
            "title": "Owner managed home",
            "slug": "home",
            "status": "published",
            "seoTitle": "Owner CMS SEO",
            "seoDescription": "Owner CMS SEO description.",
            "seoKeywords": "cms, seo",
            "indexingPolicy": "index",
            "blocks": blocks,
            "changeSummary": "Test CMS page edit.",
        },
    )
    assert response.status_code == 200
    assert response.json()["seoKeywords"] == "cms, seo"

    public_home = client.get("/v1/public/home").json()
    assert public_home["title"] == "Owner managed home"
    assert public_home["seo"]["title"] == "Owner CMS SEO"
    assert public_home["blocks"][-1]["props"]["paragraphs"] == ["Owner managed CMS block."]

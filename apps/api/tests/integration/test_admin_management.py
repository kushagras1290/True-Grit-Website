"""Integration tests for the operations-console write endpoints:
products, categories, inventory, users, and orders."""

from __future__ import annotations

import asyncio
import base64

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.log_persistence import persist_log

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


# Migration 0095 retires the old demo catalogue unconditionally -- on every
# database it touches, including a fresh test one -- archiving/deleting its
# farms, products and order/farm linkages. Several tests below used to lean on
# that catalogue's fixed ids (farm_devika, prd_alphonso, ...); they now build
# small, self-contained, obviously-synthetic fixtures of their own instead.


def _seed_farm_owner_orders(db: SQLiteDatabase) -> None:
    """Give usr_farmowner a farm and hand it ord_1001/ord_1002's line items.

    Migration 0095 nulls every seeded order_item's farm_id along with the old
    demo catalogue's farm/product links, so farm-owner order scoping needs its
    own farm rather than the retired farm_devika linkage. ord_1003-1007 keep
    their NULL farm_id, so they stay outside this farm's scope untouched.
    """
    now = "2026-07-01T00:00:00Z"
    db._conn.execute(
        "INSERT INTO farms (id, name, slug, country_code, status, created_at, created_by,"
        " updated_at, updated_by)"
        " VALUES ('farm_owner_test_scope', 'Order Scope Test Farm', 'order-scope-test-farm',"
        " 'IN', 'published', ?, 'usr_admin', ?, 'usr_admin')",
        (now, now),
    )
    db._conn.execute(
        "INSERT INTO farm_members (user_id, farm_id, created_at, created_by)"
        " VALUES ('usr_farmowner', 'farm_owner_test_scope', ?, 'usr_admin')",
        (now,),
    )
    db._conn.execute(
        "UPDATE order_items SET farm_id = 'farm_owner_test_scope'"
        " WHERE id IN ('oit_1001', 'oit_1002')"
    )
    db._conn.commit()


def _seed_checkout_product(db: SQLiteDatabase) -> None:
    """A minimal purchasable product: published, one active variant with an
    active price and starting stock -- self-contained rather than depending on
    the old demo catalogue's prd_alphonso, which migration 0095 archives."""
    db._conn.executescript(
        """
        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_checkout_test', 'Checkout Test Product', 'Checkout Test Product',
          'checkout-test-product', 'simple', 'published', 1,
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, created_at, updated_at)
        VALUES ('var_checkout_test', 'prd_checkout_test', 'CHK-TEST-1', '1 unit', 'active',
          '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_checkout_test', 'var_checkout_test', 'IN', 'INR', 89900, 'active',
          '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('var_checkout_test', 'loc_mumbai', 50, 0, 10, 1, '2026-07-01T00:00:00Z');
        """
    )
    db._conn.commit()


def _seed_price_adjustment_catalogue(db: SQLiteDatabase) -> dict[str, str]:
    """Two fresh published products with an identical, round list price -- one
    inside a fresh category, one outside it -- replacing the old demo
    catalogue's prd_alphonso/himalayan-red-rajma/fresh-fruits, which migration
    0095 archives and hides."""
    db._conn.executescript(
        """
        INSERT INTO categories (id, internal_name, name, slug, path, level, status,
          visibility, product_assignment_mode, created_at, created_by, updated_at, updated_by)
        VALUES ('cat_padj_test', 'Price Adjustment Test Category',
          'Price Adjustment Test Category', 'price-adjustment-test-category',
          '/price-adjustment-test-category', 0, 'published', 'public', 'manual',
          '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');

        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          created_at, created_by, updated_at, updated_by)
        VALUES ('prd_padj_in', 'Price Adjustment Test In-Category',
          'Price Adjustment Test In-Category', 'price-adjustment-test-in-category', 'simple',
          'published', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, created_at, updated_at)
        VALUES ('var_padj_in', 'prd_padj_in', 'PADJ-IN-1', '1 unit', 'active',
          '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_padj_in', 'var_padj_in', 'IN', 'INR', 100000, 'active',
          '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_categories (product_id, category_id, is_primary, sort_order,
          assigned_at, assigned_by)
        VALUES ('prd_padj_in', 'cat_padj_test', 1, 1, '2026-07-01T00:00:00Z', 'usr_admin');

        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          created_at, created_by, updated_at, updated_by)
        VALUES ('prd_padj_out', 'Price Adjustment Test Out-of-Category',
          'Price Adjustment Test Out-of-Category', 'price-adjustment-test-out-of-category',
          'simple', 'published', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z',
          'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, created_at, updated_at)
        VALUES ('var_padj_out', 'prd_padj_out', 'PADJ-OUT-1', '1 unit', 'active',
          '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_padj_out', 'var_padj_out', 'IN', 'INR', 100000, 'active',
          '2026-07-01T00:00:00Z', 'usr_admin');
        """
    )
    db._conn.commit()
    return {
        "category_id": "cat_padj_test",
        "in_category_product_id": "prd_padj_in",
        "in_category_slug": "price-adjustment-test-in-category",
        "out_of_category_product_id": "prd_padj_out",
        "out_of_category_slug": "price-adjustment-test-out-of-category",
    }


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
            "harvestNote": "Harvested the week of 3 March 2026",
            "growingMethod": "Rain-fed, no synthetic pesticides",
            "storageGuidance": "Store in a cool, dry place",
            # The admin form's "Unassigned" farm option has no way to submit
            # null through a native <select>, so it always resubmits "" --
            # this must not be written into a column with a foreign key to
            # farms(id) (see services/catalogue.py's update_product).
            "farmId": "",
            "dietTagIds": ["tag_vegan", "tag_gluten_free"],
            "certificationIds": ["cert_india_organic", "cert_pgs_india"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["id"] == product_id

    published = client.post(f"/v1/admin/products/{product_id}/publish", json={})
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["version"] == 1

    product = client.get(f"/v1/admin/products/{product_id}").json()
    assert product["name"] == "Test Turmeric Powder"
    assert product["imageUrl"] == "https://images.example.test/turmeric.jpg"
    assert product["harvestNote"] == "Harvested the week of 3 March 2026"
    assert product["growingMethod"] == "Rain-fed, no synthetic pesticides"
    assert product["storageGuidance"] == "Store in a cool, dry place"
    assert set(product["dietTagIds"]) == {"tag_vegan", "tag_gluten_free"}
    assert set(product["certificationIds"]) == {"cert_india_organic", "cert_pgs_india"}
    list_items = client.get("/v1/admin/products", params={"search": "Test Turmeric Powder"}).json()[
        "items"
    ]
    list_product = next(item for item in list_items if item["id"] == product_id)
    assert list_product["imageUrl"] == "https://images.example.test/turmeric.jpg"
    assert list_product["imageAlt"] == "Fresh turmeric roots on a table"
    public_product = client.get(f"/v1/public/products/{product['slug']}").json()
    assert public_product["imageUrl"] == "https://images.example.test/turmeric.jpg"
    assert public_product["harvestNote"] == "Harvested the week of 3 March 2026"
    assert public_product["growingMethod"] == "Rain-fed, no synthetic pesticides"
    assert public_product["storageGuidance"] == "Store in a cool, dry place"
    # A regular product editor's own certification assignment is authoritative
    # (an admin verifying paperwork), unlike a farmer's own claim -- written
    # straight to 'approved', so it surfaces on the public page immediately.
    assert set(public_product["certifications"]) == {"India Organic (NPOP)", "PGS-India Green"}

    archived = client.post(f"/v1/admin/products/{product_id}/archive")
    assert archived.status_code == 200
    assert client.get(f"/v1/admin/products/{product_id}").status_code == 404


def test_diet_tag_update_does_not_wipe_non_diet_tags(client: TestClient, db: SQLiteDatabase):
    """A product carrying several diet tags *and* a non-diet one (Traditional
    Indian, tag_group='intention') -- patching dietTagIds must only replace
    the diet ones, not blanket-delete every product_tags row."""
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Diet Tag Test Product", "productType": "pantry"}
    ).json()["id"]
    assert (
        client.patch(
            f"/v1/admin/products/{product_id}", json={"dietTagIds": ["tag_gluten_free"]}
        ).status_code
        == 200
    )
    db._conn.execute(
        "INSERT INTO product_tags (product_id, tag_id) VALUES (?, 'tag_traditional')", (product_id,)
    )
    db._conn.commit()
    assert (
        client.patch(
            f"/v1/admin/products/{product_id}/status", json={"status": "published"}
        ).status_code
        == 200
    )
    slug = client.get(f"/v1/admin/products/{product_id}").json()["slug"]

    before = client.get(f"/v1/admin/products/{product_id}").json()
    assert "tag_gluten_free" in before["dietTagIds"]

    updated = client.patch(
        f"/v1/admin/products/{product_id}", json={"dietTagIds": ["tag_vegan", "tag_dairy_free"]}
    )
    assert updated.status_code == 200

    after = client.get(f"/v1/admin/products/{product_id}").json()
    assert set(after["dietTagIds"]) == {"tag_vegan", "tag_dairy_free"}
    public_product = client.get(f"/v1/public/products/{slug}").json()
    assert "Traditional Indian" in public_product["tags"], "non-diet tag must survive"
    assert "Gluten Free" not in public_product["tags"], "replaced, not merged"


def test_archive_lists_and_restores_products(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Archive Flow Test Widget", "productType": "pantry"}
    ).json()["id"]

    archived = client.post(f"/v1/admin/products/{product_id}/archive")
    assert archived.status_code == 200

    # Scoped by search: the seed catalogue already carries hundreds of
    # archived filler products (a bulk-generated library), so an unfiltered
    # first page is not guaranteed to include the one this test just archived.
    archive = client.get("/v1/admin/archive", params={"search": "Archive Flow Test Widget"})
    assert archive.status_code == 200
    rows = archive.json()["items"]
    product = next(row for row in rows if row["id"] == product_id)
    assert product["kind"] == "product"
    assert product["status"] == "archived"

    restored = client.post(f"/v1/admin/archive/product/{product_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    assert client.get(f"/v1/admin/products/{product_id}").status_code == 200
    assert client.get(f"/v1/admin/products/{product_id}").json()["status"] == "draft"
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


def test_diet_tag_create_edit_delete(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    created = client.post("/v1/admin/diet-tags", json={"label": "Keto Friendly"})
    assert created.status_code == 200
    tag_id = created.json()["id"]
    assert any(item["id"] == tag_id for item in client.get("/v1/admin/diet-tags").json()["items"])

    updated = client.patch(f"/v1/admin/diet-tags/{tag_id}", json={"label": "Keto"})
    assert updated.status_code == 200
    labels = {
        item["id"]: item["label"] for item in client.get("/v1/admin/diet-tags").json()["items"]
    }
    assert labels[tag_id] == "Keto"

    duplicate = client.post("/v1/admin/diet-tags", json={"label": "Keto Friendly"})
    assert duplicate.status_code == 409

    deleted = client.delete(f"/v1/admin/diet-tags/{tag_id}")
    assert deleted.status_code == 200
    assert tag_id not in {item["id"] for item in client.get("/v1/admin/diet-tags").json()["items"]}


def test_certification_create_edit_delete(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    created = client.post("/v1/admin/certifications", json={"name": "Fair Trade Certified"})
    assert created.status_code == 200
    certification_id = created.json()["id"]

    updated = client.patch(
        f"/v1/admin/certifications/{certification_id}", json={"name": "Fair Trade"}
    )
    assert updated.status_code == 200
    names = {
        item["id"]: item["name"] for item in client.get("/v1/admin/certifications").json()["items"]
    }
    assert names[certification_id] == "Fair Trade"

    deleted = client.delete(f"/v1/admin/certifications/{certification_id}")
    assert deleted.status_code == 200
    remaining = {item["id"] for item in client.get("/v1/admin/certifications").json()["items"]}
    assert certification_id not in remaining


def test_certification_delete_blocked_while_assigned_to_a_product(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    certification_id = client.post(
        "/v1/admin/certifications", json={"name": "Organic Assigned Test"}
    ).json()["id"]
    product_id = client.post(
        "/v1/admin/products",
        json={"name": "Cert Assignment Test Product", "productType": "general"},
    ).json()["id"]
    patched = client.patch(
        f"/v1/admin/products/{product_id}", json={"certificationIds": [certification_id]}
    )
    assert patched.status_code == 200

    blocked = client.delete(f"/v1/admin/certifications/{certification_id}")
    assert blocked.status_code == 409


# --- Inventory --------------------------------------------------------------


def test_inventory_adjustment_persists_and_audits(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Inventory Audit Widget", "productType": "pantry"}
    ).json()["id"]
    created_variant = client.post(
        f"/v1/admin/products/{product_id}/variants",
        json={"name": "Default", "sku": "INV-AUDIT-1", "listMinor": 10000},
    )
    assert created_variant.status_code == 200, created_variant.text
    assert (
        client.patch(
            f"/v1/admin/products/{product_id}/status", json={"status": "published"}
        ).status_code
        == 200
    )

    response = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "INV-AUDIT-1",
            "quantityDelta": 10,
            "reasonCode": "receipt",
            "note": "Restock delivery",
        },
    )
    assert response.status_code == 200
    assert response.json()["onHand"] == 10

    # Searched, not read off page one: the inventory list is paginated and the
    # catalogue is far larger than a single page. One group per product, its
    # variants nested inside.
    inventory = client.get("/v1/admin/inventory", params={"search": "INV-AUDIT-1"}).json()["items"]
    variants = [variant for group in inventory for variant in group["variants"]]
    widget = next(row for row in variants if row["sku"] == "INV-AUDIT-1")
    assert widget["onHand"] == 10
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


def test_enabled_product_without_stock_appears_and_accepts_first_adjustment(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Inventory Starter", "productType": "general"}
    ).json()["id"]
    created_variant = client.post(
        f"/v1/admin/products/{product_id}/variants",
        json={"name": "Default", "sku": "INV-START-1", "listMinor": 10000},
    )
    assert created_variant.status_code == 200, created_variant.text
    assert (
        client.patch(
            f"/v1/admin/products/{product_id}/status", json={"status": "published"}
        ).status_code
        == 200
    )

    # Searched, not read off page one: inventory is paginated by product and
    # the catalogue is far larger than a single page.
    groups = client.get("/v1/admin/inventory", params={"search": "INV-START-1"}).json()["items"]
    row = next(
        variant
        for group in groups
        for variant in group["variants"]
        if variant["sku"] == "INV-START-1"
    )
    assert row["onHand"] == 0
    assert row["locationName"] == "Not assigned"

    adjusted = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "INV-START-1",
            "quantityDelta": 12,
            "reasonCode": "receipt",
            "note": "Initial stock receipt",
        },
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["onHand"] == 12


def test_notifications_are_role_aware(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    # A published product that has never been stocked -- 0 on hand against a 0
    # reorder threshold still counts as needing attention -- triggers the
    # "inventory" notification without depending on the old demo catalogue's
    # stock levels, which migration 0095 archives out of every query.
    product_id = client.post(
        "/v1/admin/products", json={"name": "Notification Stock Widget", "productType": "pantry"}
    ).json()["id"]
    client.post(
        f"/v1/admin/products/{product_id}/variants",
        json={"name": "Default", "sku": "NOTIF-STOCK-1", "listMinor": 5000},
    )
    assert (
        client.patch(
            f"/v1/admin/products/{product_id}/status", json={"status": "published"}
        ).status_code
        == 200
    )

    owner = client.get("/v1/admin/notifications")
    assert owner.status_code == 200, owner.text
    owner_ids = {item["id"] for item in owner.json()["items"]}
    assert "inventory" in owner_ids

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    editor = client.get("/v1/admin/notifications")
    assert editor.status_code == 200, editor.text
    editor_ids = {item["id"] for item in editor.json()["items"]}
    assert "orders" not in editor_ids
    assert "inventory" not in editor_ids


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
    assert body["url"].startswith("http://testserver/media/images/med_")
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
    assert body["url"].startswith("http://testserver/media/images/med_")
    assert body["url"].endswith(".png")


# --- Users & roles ----------------------------------------------------------


def test_user_cannot_disable_self(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.patch("/v1/admin/users/usr_admin/status", json={"status": "disabled"})
    assert response.status_code == 422


def test_owner_can_manage_role_scopes(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    create_session(db, "usr_ops")
    permissions = client.get("/v1/admin/permissions")
    assert permissions.status_code == 200
    permission_ids = {
        permission["key"]: permission["id"] for permission in permissions.json()["items"]
    }

    response = client.patch(
        "/v1/admin/roles/rol_inventory_manager/permissions",
        json={"permissionIds": [permission_ids["products.view"]]},
    )
    assert response.status_code == 200
    assert response.json()["permissionIds"] == [permission_ids["products.view"]]

    roles = client.get("/v1/admin/roles").json()["items"]
    inventory = next(role for role in roles if role["id"] == "rol_inventory_manager")
    assert inventory["permissionIds"] == [permission_ids["products.view"]]
    assert inventory["permissionKeys"] == ["products.view"]

    revoked = db._conn.execute(
        "SELECT revoked_at FROM sessions WHERE user_id = 'usr_ops' ORDER BY created_at DESC LIMIT 1"
    ).fetchone()
    assert revoked["revoked_at"] is not None

    audit = db._conn.execute(
        """
        SELECT action, actor_user_id, before_summary_json, after_summary_json
        FROM audit_logs
        WHERE action = 'role.permissions_changed' AND entity_id = 'rol_inventory_manager'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert audit is not None
    assert audit["actor_user_id"] == "usr_admin"
    assert permission_ids["products.view"] in audit["after_summary_json"]


def test_only_owner_can_manage_role_scopes(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/permissions").status_code == 403
    response = client.patch(
        "/v1/admin/roles/rol_farm_owner/permissions",
        json={"permissionIds": ["prm_products_view"]},
    )
    assert response.status_code == 403


def test_owner_cannot_edit_locked_or_unsafe_scopes(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    locked = client.patch(
        "/v1/admin/roles/rol_super_admin/permissions",
        json={"permissionIds": ["prm_products_view"]},
    )
    assert locked.status_code == 422

    unsafe = client.patch(
        "/v1/admin/roles/rol_farm_owner/permissions",
        json={"permissionIds": ["prm_users_view"]},
    )
    assert unsafe.status_code == 422


def test_owner_can_create_rename_and_delete_a_custom_role(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    permission_ids = {
        permission["key"]: permission["id"]
        for permission in client.get("/v1/admin/permissions").json()["items"]
    }

    created = client.post(
        "/v1/admin/roles",
        json={
            "name": "Warehouse Lead",
            "description": "Adjust stock and view products",
            "permissionIds": [permission_ids["inventory.view"], permission_ids["inventory.adjust"]],
        },
    )
    assert created.status_code == 200
    body = created.json()
    assert body["key"] == "warehouse-lead"
    assert body["isSystem"] is False
    assert body["locked"] is False
    assert sorted(body["permissionIds"]) == sorted(
        [permission_ids["inventory.view"], permission_ids["inventory.adjust"]]
    )
    role_id = body["id"]

    roles = client.get("/v1/admin/roles").json()["items"]
    assert any(role["id"] == role_id for role in roles)

    duplicate = client.post("/v1/admin/roles", json={"name": "Warehouse Lead", "permissionIds": []})
    assert duplicate.status_code == 409

    renamed = client.patch(
        f"/v1/admin/roles/{role_id}",
        json={"name": "Warehouse Manager", "description": "Updated"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "Warehouse Manager"
    assert renamed.json()["key"] == "warehouse-lead"  # key is immutable after creation

    assigned = client.post(
        "/v1/admin/users/invite",
        json={
            "email": "warehouse@truegrit.test",
            "displayName": "Warehouse User",
            "roleIds": [role_id],
        },
    )
    assert assigned.status_code == 200

    blocked_delete = client.delete(f"/v1/admin/roles/{role_id}")
    assert blocked_delete.status_code == 409

    unassigned = client.patch(
        f"/v1/admin/users/{assigned.json()['id']}/roles", json={"roleIds": []}
    )
    assert unassigned.status_code == 200

    deleted = client.delete(f"/v1/admin/roles/{role_id}")
    assert deleted.status_code == 200
    assert client.get("/v1/admin/roles").json()["items"]
    assert not any(role["id"] == role_id for role in client.get("/v1/admin/roles").json()["items"])


def test_system_roles_cannot_be_renamed_or_deleted(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    renamed = client.patch("/v1/admin/roles/rol_inventory_manager", json={"name": "Something else"})
    assert renamed.status_code == 422
    deleted = client.delete("/v1/admin/roles/rol_inventory_manager")
    assert deleted.status_code == 422


def test_only_owner_can_create_roles(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post("/v1/admin/roles", json={"name": "Shouldn't work", "permissionIds": []})
    assert response.status_code == 403


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
    # A fresh, self-contained farm with its own active products -- migration
    # 0095 deletes the old demo catalogue's farms outright, so this test
    # builds its own rather than depending on the retired farm_devika.
    farm_id = "farm_delete_test"
    now = "2026-07-01T00:00:00Z"
    db._conn.execute(
        "INSERT INTO farms (id, name, slug, country_code, status, created_at, created_by,"
        " updated_at, updated_by)"
        " VALUES (?, 'Delete Test Farm', 'delete-test-farm', 'IN', 'published', ?, 'usr_admin',"
        " ?, 'usr_admin')",
        (farm_id, now, now),
    )
    for suffix in ("1", "2"):
        db._conn.execute(
            "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id, status,"
            " created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, 'simple', ?, 'published', ?, 'usr_admin', ?, 'usr_admin')",
            (
                f"prd_delete_test_{suffix}",
                f"Delete Test Product {suffix}",
                f"Delete Test Product {suffix}",
                f"delete-test-product-{suffix}",
                farm_id,
                now,
                now,
            ),
        )
    db._conn.commit()

    # Counted from the fixture rather than hardcoded: how many products a farm
    # carries is fixture data, while "every one of them is archived with the
    # farm" is the behaviour under test.
    active_before = db._conn.execute(
        "SELECT COUNT(*) AS c FROM products WHERE farm_id = ? AND archived_at IS NULL", (farm_id,)
    ).fetchone()["c"]
    assert active_before > 0, "the fixture must have active products for this to mean anything"

    response = client.delete(f"/v1/admin/farms/{farm_id}")
    assert response.status_code == 200
    assert response.json()["archivedProductCount"] == active_before

    product = db._conn.execute(
        "SELECT status, archived_at FROM products WHERE id = 'prd_delete_test_1'"
    ).fetchone()
    assert product["status"] == "archived"
    assert product["archived_at"] is not None
    remaining = db._conn.execute(
        "SELECT COUNT(*) AS c FROM products WHERE farm_id = ? AND archived_at IS NULL", (farm_id,)
    ).fetchone()["c"]
    assert remaining == 0


def test_farm_owner_cannot_issue_temporary_password(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post("/v1/admin/users/usr_farmowner/temporary-password")
    assert response.status_code == 403


def test_farm_owner_cannot_email_password_reset(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post("/v1/admin/users/usr_farmowner/password-reset-email")
    assert response.status_code == 403


def test_owner_can_view_contact_attempts(client: TestClient, db: SQLiteDatabase):
    contact = client.post(
        "/v1/public/contact",
        json={
            "name": "Riya Nair",
            "email": "riya@example.test",
            "phone": "+91 98765 43210",
            "subject": "Order help",
            "message": "Can you help with my recent order?",
        },
    )
    assert contact.status_code == 200

    as_admin(client, db)
    response = client.get("/v1/admin/contact-messages")
    assert response.status_code == 200
    items = response.json()["items"]
    assert items[0]["name"] == "Riya Nair"
    assert items[0]["email"] == "riya@example.test"
    # Surfaced to the console so staff can ring back without opening the row.
    assert items[0]["phone"] == "+919876543210"
    assert items[0]["subject"] == "Order help"
    assert items[0]["status"] == "new"

    # The number is searchable: "someone rang about this" is the lookup staff
    # actually run, and it is the field they are certain of.
    found = client.get("/v1/admin/contact-messages", params={"search": "9876543210"})
    assert found.status_code == 200
    assert [item["id"] for item in found.json()["items"]] == [contact.json()["id"]]


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
    _seed_checkout_product(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    before = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_checkout_test'"
    ).fetchone()
    order = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_checkout_test", "quantity": 2}],
            "deliveryAddress": ADDRESS,
        },
    ).json()
    after_checkout = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_checkout_test'"
    ).fetchone()
    assert after_checkout["on_hand"] == before["on_hand"]
    assert after_checkout["reserved"] == before["reserved"] + 2

    client.cookies.clear()
    as_admin(client, db)
    cancelled = client.patch(f"/v1/admin/orders/{order['id']}/status", json={"status": "cancelled"})
    assert cancelled.status_code == 200
    after_cancel = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_checkout_test'"
    ).fetchone()
    assert after_cancel["on_hand"] == before["on_hand"]
    assert after_cancel["reserved"] == before["reserved"]


def test_completed_order_consumes_reserved_inventory(client: TestClient, db: SQLiteDatabase):
    _seed_checkout_product(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))
    before = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_checkout_test'"
    ).fetchone()
    order = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_checkout_test", "quantity": 1}],
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
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_checkout_test'"
    ).fetchone()
    assert after_complete["on_hand"] == before["on_hand"] - 1
    assert after_complete["reserved"] == before["reserved"]


def test_farm_owner_sees_only_own_farm_orders_in_list(client: TestClient, db: SQLiteDatabase):
    # ord_1001/ord_1002 are assigned to usr_farmowner's farm by the fixture
    # below; ord_1003-1007 keep no farm and must never appear.
    _seed_farm_owner_orders(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    items = client.get("/v1/admin/orders").json()["items"]
    references = {item["publicReference"] for item in items}
    assert references == {"TG-1001", "TG-1002"}
    by_reference = {item["publicReference"]: item for item in items}
    assert by_reference["TG-1001"]["totalMinor"] == 89900
    assert by_reference["TG-1002"]["totalMinor"] == 149900


def test_farm_owner_gets_full_detail_for_own_farm_order(client: TestClient, db: SQLiteDatabase):
    _seed_farm_owner_orders(db)
    _seed_paid_razorpay_payment(db, "ord_1001", 94800)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    detail = client.get("/v1/admin/orders/ord_1001")
    assert detail.status_code == 200
    body = detail.json()
    assert len(body["items"]) == 1
    assert body["totalMinor"] == 89900
    assert body["subtotalMinor"] == 89900
    # Whole-order payment figures are hidden from a farm-scoped read (94800
    # includes delivery, which isn't this farm's revenue) -- provider/status
    # stay visible since fulfilment needs to know "is this paid".
    assert body["payment"]["provider"] == "razorpay"
    assert body["payment"]["amountMinor"] is None
    assert body["payment"]["refundedMinor"] is None


def test_farm_owner_gets_404_for_another_farms_order(client: TestClient, db: SQLiteDatabase):
    _seed_farm_owner_orders(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/orders/ord_1003").status_code == 404


def test_farm_owner_can_transition_own_farm_order(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    moved = client.patch("/v1/admin/orders/ord_1002/status", json={"status": "confirmed"})
    assert moved.status_code == 200
    assert moved.json()["orderStatus"] == "confirmed"


def test_farm_owner_cannot_transition_another_farms_order(client: TestClient, db: SQLiteDatabase):
    _seed_farm_owner_orders(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.patch("/v1/admin/orders/ord_1003/status", json={"status": "cancelled"})
    assert response.status_code == 403


def test_regular_admin_still_sees_every_farms_orders(client: TestClient, db: SQLiteDatabase):
    # farm scoping must not affect a global staff member (farm_id is None).
    as_admin(client, db)
    items = client.get("/v1/admin/orders").json()["items"]
    references = {item["publicReference"] for item in items}
    assert {"TG-1001", "TG-1002", "TG-1003", "TG-1007"} <= references
    detail = client.get("/v1/admin/orders/ord_1003")
    assert detail.status_code == 200
    assert detail.json()["totalMinor"] == 18700  # the real, whole-order total


def test_farm_owner_search_results_scoped_to_own_farm(client: TestClient, db: SQLiteDatabase):
    _seed_farm_owner_orders(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    results = client.get("/v1/admin/search", params={"q": "TG-10"}).json()
    references = {row["publicReference"] for row in results["orders"]}
    assert "TG-1001" in references
    assert "TG-1003" not in references


def test_farm_owner_with_refund_permission_cannot_refund_anothers_order(
    client: TestClient, db: SQLiteDatabase
):
    # orders.refund is not normally farm-holdable (Scope Management blocks
    # granting it), but the ownership guard in `issue_refund` must hold even
    # if that ever changes -- exercised here via a direct grant, matching how
    # `test_farm_owner_cannot_manage_appearance`'s sibling tests isolate a
    # single check from the broader "can this role even hold this permission"
    # rule.
    as_admin(client, db)
    _seed_farm_owner_orders(db)
    permission_ids = {
        permission["key"]: permission["id"]
        for permission in client.get("/v1/admin/permissions").json()["items"]
    }
    db._conn.execute(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES ('rol_farm_owner', ?)",
        (permission_ids["orders.refund"],),
    )
    db._conn.commit()

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post(
        "/v1/admin/orders/ord_1003/refund", json={"reason": "Testing the ownership guard"}
    )
    assert response.status_code == 403


def _seed_paid_razorpay_payment(db: SQLiteDatabase, order_id: str, amount_minor: int) -> None:
    now = "2026-07-15T00:00:00Z"
    db._conn.execute(
        "INSERT INTO payments"
        " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
        "  status, created_at, updated_at)"
        " VALUES (?, ?, 'razorpay', 'pay_test123', ?, 'INR', 'paid', ?, ?)",
        (f"pay_{order_id}", order_id, amount_minor, now, now),
    )
    db._conn.commit()


def test_owner_can_issue_and_oversee_refund(client: TestClient, db: SQLiteDatabase, monkeypatch):
    as_admin(client, db)
    _seed_paid_razorpay_payment(db, "ord_1001", 94800)

    async def fake_refund(settings, *, payment_id, amount_minor, idempotency_key):
        assert payment_id == "pay_test123"
        return "rfnd_test123"

    monkeypatch.setattr("truegrit_api.services.orders.refund_razorpay_payment", fake_refund)

    response = client.post(
        "/v1/admin/orders/ord_1001/refund",
        json={"reason": "Customer requested cancellation"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paymentStatus"] == "refunded"
    assert body["refundedMinor"] == 94800

    detail = client.get("/v1/admin/orders/ord_1001").json()
    assert detail["paymentStatus"] == "refunded"
    assert detail["payment"]["status"] == "refunded"
    assert detail["payment"]["refundedMinor"] == 94800

    refunds = client.get("/v1/admin/refunds").json()["items"]
    match = next(r for r in refunds if r["orderReference"] == "TG-1001")
    assert match["reason"] == "Customer requested cancellation"
    assert match["refundedMinor"] == 94800
    assert match["providerRefundId"] == "rfnd_test123"


def test_refund_cannot_exceed_remaining_balance_or_double_refund(
    client: TestClient, db: SQLiteDatabase, monkeypatch
):
    as_admin(client, db)
    _seed_paid_razorpay_payment(db, "ord_1001", 94800)

    async def fake_refund(settings, *, payment_id, amount_minor, idempotency_key):
        return "rfnd_test123"

    monkeypatch.setattr("truegrit_api.services.orders.refund_razorpay_payment", fake_refund)

    too_much = client.post(
        "/v1/admin/orders/ord_1001/refund",
        json={"amountMinor": 200_000, "reason": "Too much"},
    )
    assert too_much.status_code == 422

    full = client.post("/v1/admin/orders/ord_1001/refund", json={"reason": "Full refund"})
    assert full.status_code == 200

    again = client.post("/v1/admin/orders/ord_1001/refund", json={"reason": "Second attempt"})
    assert again.status_code == 409


def test_refund_blocked_for_cod_orders(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    now = "2026-07-15T00:00:00Z"
    db._conn.execute(
        "INSERT INTO payments"
        " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
        "  status, created_at, updated_at)"
        " VALUES ('pay_cod_1001', 'ord_1001', 'cod', NULL, 94800, 'INR', 'paid', ?, ?)",
        (now, now),
    )
    db._conn.commit()

    response = client.post("/v1/admin/orders/ord_1001/refund", json={"reason": "test"})
    assert response.status_code == 422


def test_owner_can_refund_a_stripe_payment(client: TestClient, db: SQLiteDatabase, monkeypatch):
    """Stripe checkout doesn't exist yet, but the refund side is ready for it --
    seeds a Stripe payment row directly (the same way a future checkout
    implementation would) and proves `issue_refund` routes it through
    `refund_stripe_payment` correctly."""
    as_admin(client, db)
    now = "2026-07-15T00:00:00Z"
    db._conn.execute(
        "INSERT INTO payments"
        " (id, order_id, provider, provider_intent_id, amount_minor, currency_code,"
        "  status, created_at, updated_at)"
        " VALUES ('pay_stripe_1001', 'ord_1001', 'stripe', 'pi_test123', 94800, 'INR',"
        "  'paid', ?, ?)",
        (now, now),
    )
    db._conn.commit()

    async def fake_stripe_refund(settings, *, payment_intent_id, amount_minor, idempotency_key):
        assert payment_intent_id == "pi_test123"
        assert amount_minor == 94800
        return "re_test123"

    monkeypatch.setattr("truegrit_api.services.orders.refund_stripe_payment", fake_stripe_refund)

    response = client.post(
        "/v1/admin/orders/ord_1001/refund", json={"reason": "Customer requested cancellation"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["paymentStatus"] == "refunded"
    assert body["refundedMinor"] == 94800

    detail = client.get("/v1/admin/orders/ord_1001").json()
    assert detail["payment"]["status"] == "refunded"

    refunds = client.get("/v1/admin/refunds").json()["items"]
    match = next(item for item in refunds if item["orderId"] == "ord_1001")
    assert match["providerRefundId"] == "re_test123"


def test_refund_requires_orders_refund_permission_even_with_orders_view(
    client: TestClient, db: SQLiteDatabase
):
    # rol_inventory holds orders.view but not orders.cancel/orders.refund --
    # the route's own dependency only demands orders.view, so this proves the
    # *inner* orders.refund check in issue_refund() is actually enforced.
    db._conn.execute(
        "INSERT INTO user_roles (user_id, role_id, assigned_at, assigned_by)"
        " VALUES ('usr_editor', 'rol_inventory', '2026-07-15T00:00:00Z', 'usr_admin')"
    )
    db._conn.commit()
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))

    me = client.get("/v1/admin/me").json()
    assert "orders.view" in me["permissions"]
    assert "orders.refund" not in me["permissions"]

    response = client.post("/v1/admin/orders/ord_1001/refund", json={"reason": "test"})
    assert response.status_code == 403


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
            "featuredCategories": ["fruits", "vegetables", "staple-grains"],
            "freshFavourites": [
                "organic-kesar-mango",
                "organic-mature-spinach",
                "organic-brown-basmati-rice",
            ],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["heroHeading"] == "Owner managed homepage"
    assert body["heroImageUrl"] == "/homepage-hero.png"
    assert body["heroImageAlt"] == "Organic mangoes held in a sunlit orchard"
    assert body["heroSlides"][1]["enabled"] is False
    assert body["seoKeywords"] == "organic, farm fresh, true grit"
    assert body["featuredCategories"] == ["fruits", "vegetables", "staple-grains"]
    assert body["freshFavourites"] == [
        "organic-kesar-mango",
        "organic-mature-spinach",
        "organic-brown-basmati-rice",
    ]

    public_home = client.get("/v1/public/home").json()
    assert public_home["seo"]["keywords"] == "organic, farm fresh, true grit"
    assert public_home["blocks"][0]["props"]["heading"] == "Owner managed homepage"
    assert public_home["blocks"][0]["props"]["imageUrl"] == "/homepage-hero.png"
    assert public_home["blocks"][0]["props"]["slides"][1]["href"] == "/category/organic-vegetables"
    assert public_home["blocks"][0]["props"]["slides"][1]["enabled"] is False
    # blocks[1] is the promotions banner (migration 0060, seeded directly under
    # the hero) -- categories and products sit one slot further out than before.
    assert public_home["blocks"][2]["props"]["categorySlugs"] == [
        "fruits",
        "vegetables",
        "staple-grains",
    ]
    assert public_home["blocks"][3]["props"]["productSlugs"] == [
        "organic-kesar-mango",
        "organic-mature-spinach",
        "organic-brown-basmati-rice",
    ]
    assert public_home["blocks"][3]["props"]["limit"] == 3


def test_farm_owner_cannot_manage_site_control(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/site-control").status_code == 403
    assert client.patch("/v1/admin/site-control", json={"seoTitle": "Nope"}).status_code == 403


def test_hero_slide_limit_is_a_setting_not_a_constant(client: TestClient, db: SQLiteDatabase):
    """Growing the carousel past the shipped twelve is an admin change.

    The cap is stored in `app_settings`, so raising it and adding the extra
    slides can happen in one save — no deploy in between.
    """
    as_admin(client, db)

    def slide(index: int) -> dict[str, object]:
        return {
            "imageUrl": f"/homepage-hero-{index}.png",
            "imageAlt": f"Banner {index}",
            "href": "/shop",
            "label": f"Banner {index}",
            "enabled": True,
        }

    assert client.get("/v1/admin/site-control").json()["heroMaxSlides"] == 12

    over_the_cap = client.patch(
        "/v1/admin/site-control", json={"heroSlides": [slide(i) for i in range(13)]}
    )
    assert over_the_cap.status_code == 422
    assert "12" in over_the_cap.json()["error"]["message"]

    raised = client.patch(
        "/v1/admin/site-control",
        json={"heroMaxSlides": 15, "heroSlides": [slide(i) for i in range(13)]},
    )
    assert raised.status_code == 200
    assert raised.json()["heroMaxSlides"] == 15
    assert len(raised.json()["heroSlides"]) == 13

    # The structural ceiling still binds whatever the setting says.
    assert client.patch("/v1/admin/site-control", json={"heroMaxSlides": 500}).status_code == 422


def test_lowering_the_slide_limit_does_not_delete_saved_slides(
    client: TestClient, db: SQLiteDatabase
):
    """A cap is a rule for the next save, never a silent truncation of the last."""
    as_admin(client, db)

    def slide(index: int) -> dict[str, object]:
        return {
            "imageUrl": f"/homepage-hero-{index}.png",
            "imageAlt": f"Banner {index}",
            "href": "/shop",
            "label": f"Banner {index}",
            "enabled": True,
        }

    # Self-contained: save its own five slides first rather than assuming a
    # seeded count, then prove lowering the cap doesn't truncate them.
    seeded = client.patch(
        "/v1/admin/site-control", json={"heroSlides": [slide(i) for i in range(5)]}
    )
    assert seeded.status_code == 200
    before = len(seeded.json()["heroSlides"])
    assert before == 5

    lowered = client.patch("/v1/admin/site-control", json={"heroMaxSlides": 3})
    assert lowered.status_code == 200
    assert lowered.json()["heroMaxSlides"] == 3
    assert len(lowered.json()["heroSlides"]) == before


def test_owner_can_manage_homepage_sections(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)

    listed = client.get("/v1/admin/homepage/sections")
    assert listed.status_code == 200
    body = listed.json()
    types = [section["type"] for section in body["sections"]]
    assert types[0] == "hero"
    assert "page_links" in types
    assert {entry["type"] for entry in body["addableTypes"]} == {
        "page_links",
        "rich_text",
        "faq",
        "farmer_story",
        "newsletter",
        "reviews_showcase",
        "promotion_banner",
        "recommendations",
        "image_banner",
    }

    # The three sections Site Control's own editors bind to are undeletable but
    # switchable; everything else can go.
    by_type = {section["type"]: section for section in body["sections"]}
    assert by_type["hero"]["removable"] is False
    assert by_type["category_collection"]["removable"] is False
    assert by_type["product_collection"]["removable"] is False
    assert by_type["page_links"]["removable"] is True

    snippets = by_type["page_links"]
    hidden = client.patch(f"/v1/admin/homepage/sections/{snippets['id']}", json={"enabled": False})
    assert hidden.status_code == 200

    # A hidden section is filtered out server-side, not merely unrendered.
    public_types = [block["type"] for block in client.get("/v1/public/home").json()["blocks"]]
    assert "page_links" not in public_types

    shown = client.patch(f"/v1/admin/homepage/sections/{snippets['id']}", json={"enabled": True})
    assert shown.status_code == 200
    assert "page_links" in [
        block["type"] for block in client.get("/v1/public/home").json()["blocks"]
    ]


def test_homepage_section_props_are_validated_before_they_are_stored(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    sections = client.get("/v1/admin/homepage/sections").json()["sections"]
    snippets = next(section for section in sections if section["type"] == "page_links")

    unsafe = client.patch(
        f"/v1/admin/homepage/sections/{snippets['id']}",
        json={
            "props": {
                "heading": "Explore",
                "intro": "",
                "items": [{"label": "Anywhere", "description": "", "href": "javascript:alert(1)"}],
            }
        },
    )
    assert unsafe.status_code == 422

    saved = client.patch(
        f"/v1/admin/homepage/sections/{snippets['id']}",
        json={
            "props": {
                "heading": "Find your way around",
                "intro": "Short tour.",
                "items": [
                    {
                        "label": "Recipes",
                        "description": "Cooking for what is in your basket.",
                        "href": "/recipes",
                        "enabled": True,
                    }
                ],
            }
        },
    )
    assert saved.status_code == 200
    stored = next(
        section for section in saved.json()["sections"] if section["type"] == "page_links"
    )
    assert stored["heading"] == "Find your way around"
    assert stored["summary"] == "1 page snippet"


def test_owner_can_add_reorder_and_delete_a_custom_homepage_section(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    added = client.post("/v1/admin/homepage/sections", json={"type": "rich_text"})
    assert added.status_code == 200
    sections = added.json()["sections"]
    new_section = sections[-1]
    assert new_section["type"] == "rich_text"
    # New sections arrive switched off so placeholder copy never reaches a
    # customer between adding the section and writing it.
    assert new_section["enabled"] is False
    assert new_section["removable"] is True

    ids = [section["id"] for section in sections]
    reordered = client.post("/v1/admin/homepage/sections/order", json={"ids": [ids[-1], *ids[:-1]]})
    assert reordered.status_code == 200
    assert reordered.json()["sections"][0]["id"] == new_section["id"]

    # A partial list would delete everything left out, so it is refused.
    assert (
        client.post(
            "/v1/admin/homepage/sections/order", json={"ids": [new_section["id"]]}
        ).status_code
        == 422
    )

    removed = client.delete(f"/v1/admin/homepage/sections/{new_section['id']}")
    assert removed.status_code == 200
    assert new_section["id"] not in [section["id"] for section in removed.json()["sections"]]


def test_curated_homepage_sections_cannot_be_deleted(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    sections = client.get("/v1/admin/homepage/sections").json()["sections"]
    hero = next(section for section in sections if section["type"] == "hero")
    refused = client.delete(f"/v1/admin/homepage/sections/{hero['id']}")
    assert refused.status_code == 422
    assert "untick" in refused.json()["error"]["message"].lower()


def test_unknown_homepage_section_type_is_refused(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert (
        client.post("/v1/admin/homepage/sections", json={"type": "custom_html"}).status_code == 422
    )


def test_image_banner_section_add_edit_and_reject_unsafe_href(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    added = client.post("/v1/admin/homepage/sections", json={"type": "image_banner"})
    assert added.status_code == 200
    new_section = added.json()["sections"][-1]
    assert new_section["type"] == "image_banner"
    assert new_section["enabled"] is False

    unsafe = client.patch(
        f"/v1/admin/homepage/sections/{new_section['id']}",
        json={
            "props": {
                "imageUrl": "/motto.png",
                "imageAlt": "Pure by nature, true by choice",
                "href": "javascript:alert(1)",
            }
        },
    )
    assert unsafe.status_code == 422

    saved = client.patch(
        f"/v1/admin/homepage/sections/{new_section['id']}",
        json={
            "props": {
                "imageUrl": "/motto.png",
                "imageAlt": "Pure by nature, true by choice",
                "href": "/shop",
            }
        },
    )
    assert saved.status_code == 200
    stored = next(
        section for section in saved.json()["sections"] if section["id"] == new_section["id"]
    )
    assert stored["summary"] == "Pure by nature, true by choice"
    assert client.post("/v1/admin/homepage/sections", json={"type": "hero"}).status_code == 422


def test_farm_owner_cannot_manage_homepage_sections(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/homepage/sections").status_code == 403
    assert client.post("/v1/admin/homepage/sections", json={"type": "faq"}).status_code == 403
    assert client.delete("/v1/admin/homepage/sections/blk_hero").status_code == 403


# --- Homepage sections: per-country overrides -------------------------------


def test_owner_can_set_and_clear_a_homepage_country_override(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    sections = client.get("/v1/admin/homepage/sections").json()["sections"]
    snippets = next(section for section in sections if section["type"] == "page_links")

    empty = client.get("/v1/admin/homepage/country-overrides")
    assert empty.status_code == 200
    assert empty.json()["overrides"] == {}

    # Force the section off for IN, even though it stays on globally. Lower
    # case in the URL proves the country is normalised the same way the
    # theme/announcement scopes are.
    forced_off = client.put(
        f"/v1/admin/homepage/country-overrides/in/{snippets['id']}", json={"enabled": False}
    )
    assert forced_off.status_code == 200
    assert forced_off.json()["overrides"]["IN"][snippets["id"]] is False

    public_in = client.get("/v1/public/home", params={"country": "IN"}).json()
    assert "page_links" not in [block["type"] for block in public_in["blocks"]]
    public_global = client.get("/v1/public/home").json()
    assert "page_links" in [block["type"] for block in public_global["blocks"]]

    cleared = client.delete(f"/v1/admin/homepage/country-overrides/IN/{snippets['id']}")
    assert cleared.status_code == 200
    assert cleared.json()["overrides"] == {}
    public_in_after_clear = client.get("/v1/public/home", params={"country": "IN"}).json()
    assert "page_links" in [block["type"] for block in public_in_after_clear["blocks"]]


def test_homepage_country_override_can_force_a_disabled_section_on(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    sections = client.get("/v1/admin/homepage/sections").json()["sections"]
    snippets = next(section for section in sections if section["type"] == "page_links")
    client.patch(f"/v1/admin/homepage/sections/{snippets['id']}", json={"enabled": False})
    assert "page_links" not in [
        block["type"] for block in client.get("/v1/public/home").json()["blocks"]
    ]

    client.put(f"/v1/admin/homepage/country-overrides/US/{snippets['id']}", json={"enabled": True})
    forced_on = client.get("/v1/public/home", params={"country": "US"}).json()
    assert "page_links" in [block["type"] for block in forced_on["blocks"]]
    # Every other visitor still gets the section's own (disabled) default.
    still_off = client.get("/v1/public/home", params={"country": "IN"}).json()
    assert "page_links" not in [block["type"] for block in still_off["blocks"]]


def test_homepage_country_override_rejects_bad_country_and_unknown_section(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    # XX (Cloudflare "unknown") and T1 (Tor) are sentinels, never real markets.
    assert (
        client.put(
            "/v1/admin/homepage/country-overrides/XX/blk_hero", json={"enabled": True}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/v1/admin/homepage/country-overrides/USA/blk_hero", json={"enabled": True}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/v1/admin/homepage/country-overrides/IN/blk_not_real", json={"enabled": True}
        ).status_code
        == 404
    )


def test_farm_owner_cannot_manage_homepage_country_overrides(
    client: TestClient, db: SQLiteDatabase
):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/homepage/country-overrides").status_code == 403
    assert (
        client.put(
            "/v1/admin/homepage/country-overrides/IN/blk_hero", json={"enabled": True}
        ).status_code
        == 403
    )
    assert client.delete("/v1/admin/homepage/country-overrides/IN/blk_hero").status_code == 403


# --- Announcement banner ------------------------------------------------------


def test_owner_can_manage_the_global_announcement(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    seeded = client.get("/v1/admin/announcements")
    assert seeded.status_code == 200
    global_row = next(row for row in seeded.json()["scopes"] if row["scope"] == "global")
    assert global_row["active"] is True
    assert global_row["message"]  # seeded with real copy, not asserting its exact text

    saved = client.put(
        "/v1/admin/announcements",
        json={
            "scope": "global",
            "active": False,
            "message": "Back soon.",
            "path": "",
        },
    )
    assert saved.status_code == 200
    updated = next(row for row in saved.json()["scopes"] if row["scope"] == "global")
    assert updated["active"] is False
    assert updated["message"] == "Back soon."

    # Switched off, so the storefront shows nothing.
    assert client.get("/v1/public/bootstrap").json()["announcement"] is None


def test_owner_can_add_and_remove_a_country_announcement(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    # Captured rather than hardcoded: the seeded global message's exact text
    # is catalogue copy, while "falls back to the global message" is the
    # behaviour under test.
    global_message = next(
        row
        for row in client.get("/v1/admin/announcements").json()["scopes"]
        if row["scope"] == "global"
    )["message"]

    added = client.put(
        "/v1/admin/announcements",
        json={
            "scope": "in",
            "active": True,
            "message": "Diwali boxes open now.",
            "path": "/diwali",
        },
    )
    assert added.status_code == 200
    scopes = {row["scope"]: row for row in added.json()["scopes"]}
    assert scopes["IN"]["message"] == "Diwali boxes open now."

    # A country's active banner replaces the global one for its visitors.
    india = client.get("/v1/public/bootstrap", params={"country": "IN"}).json()
    assert india["announcement"] == {"message": "Diwali boxes open now.", "path": "/diwali"}
    elsewhere = client.get("/v1/public/bootstrap", params={"country": "FR"}).json()
    assert elsewhere["announcement"]["message"] == global_message

    removed = client.delete("/v1/admin/announcements/IN")
    assert removed.status_code == 200
    assert "IN" not in {row["scope"] for row in removed.json()["scopes"]}
    india_after_removal = client.get("/v1/public/bootstrap", params={"country": "IN"}).json()
    assert india_after_removal["announcement"]["message"] == global_message


def test_switching_off_a_country_announcement_does_not_fall_back_to_global(
    client: TestClient, db: SQLiteDatabase
):
    """A country row that exists but is inactive is a deliberate silence, not
    a gap that should be filled by the site-wide banner underneath it."""
    as_admin(client, db)
    client.put(
        "/v1/admin/announcements",
        json={"scope": "DE", "active": False, "message": "placeholder", "path": ""},
    )
    germany = client.get("/v1/public/bootstrap", params={"country": "DE"}).json()
    assert germany["announcement"] is None


def test_the_global_announcement_cannot_be_deleted(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    refused = client.delete("/v1/admin/announcements/global")
    assert refused.status_code == 422


def test_announcement_scope_is_validated(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    for bad_scope in ("XX", "T1", "USA", ""):
        response = client.put(
            "/v1/admin/announcements",
            json={"scope": bad_scope, "active": True, "message": "x", "path": ""},
        )
        assert response.status_code == 422, bad_scope
    empty_message = client.put(
        "/v1/admin/announcements",
        json={"scope": "global", "active": True, "message": "   ", "path": ""},
    )
    assert empty_message.status_code == 422


def test_deleting_an_announcement_scope_that_was_never_saved_is_404(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    assert client.delete("/v1/admin/announcements/JP").status_code == 404


def test_farm_owner_cannot_manage_announcements(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/announcements").status_code == 403
    assert (
        client.put(
            "/v1/admin/announcements",
            json={"scope": "global", "active": True, "message": "x", "path": ""},
        ).status_code
        == 403
    )
    assert client.delete("/v1/admin/announcements/IN").status_code == 403


# --- Price adjustments -------------------------------------------------------


def test_owner_can_save_update_and_delete_a_global_price_adjustment(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    empty = client.get("/v1/admin/price-adjustments")
    assert empty.status_code == 200
    assert empty.json()["rules"] == []

    created = client.put(
        "/v1/admin/price-adjustments", json={"scope": "global", "percent": -20, "active": True}
    )
    assert created.status_code == 200
    rules = created.json()["rules"]
    assert len(rules) == 1
    assert rules[0]["scope"] == "global"
    assert rules[0]["productId"] is None
    assert rules[0]["categoryId"] is None
    assert rules[0]["percent"] == -20
    rule_id = rules[0]["id"]

    # A second PUT for the same (scope, product, category) updates in place
    # rather than creating a duplicate row.
    updated = client.put(
        "/v1/admin/price-adjustments", json={"scope": "global", "percent": -30, "active": True}
    )
    assert updated.status_code == 200
    assert len(updated.json()["rules"]) == 1
    assert updated.json()["rules"][0]["id"] == rule_id
    assert updated.json()["rules"][0]["percent"] == -30

    removed = client.delete(f"/v1/admin/price-adjustments/{rule_id}")
    assert removed.status_code == 200
    assert removed.json()["rules"] == []


def test_price_adjustment_product_and_category_are_mutually_exclusive(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    response = client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "productId": "prd_alphonso",
            "categoryId": "cat_market_fruits",
            "percent": -10,
            "active": True,
        },
    )
    assert response.status_code == 422


def test_price_adjustment_percent_bounds_are_enforced(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert (
        client.put(
            "/v1/admin/price-adjustments", json={"scope": "global", "percent": -91, "active": True}
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/v1/admin/price-adjustments", json={"scope": "global", "percent": 501, "active": True}
        ).status_code
        == 422
    )


def test_price_adjustment_rejects_unknown_product_and_category(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    assert (
        client.put(
            "/v1/admin/price-adjustments",
            json={"scope": "global", "productId": "prd_not_real", "percent": -10, "active": True},
        ).status_code
        == 404
    )
    assert (
        client.put(
            "/v1/admin/price-adjustments",
            json={"scope": "global", "categoryId": "cat_not_real", "percent": -10, "active": True},
        ).status_code
        == 404
    )


def test_deleting_an_unknown_price_adjustment_is_404(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert client.delete("/v1/admin/price-adjustments/padj_not_real").status_code == 404


def test_farm_owner_cannot_manage_price_adjustments(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/price-adjustments").status_code == 403
    assert (
        client.put(
            "/v1/admin/price-adjustments", json={"scope": "global", "percent": -10, "active": True}
        ).status_code
        == 403
    )
    assert client.delete("/v1/admin/price-adjustments/padj_x").status_code == 403


# --- Price adjustments: public resolution ------------------------------------


def test_price_adjustment_product_rule_beats_a_global_rule(client: TestClient, db: SQLiteDatabase):
    products = _seed_price_adjustment_catalogue(db)
    as_admin(client, db)
    client.put(
        "/v1/admin/price-adjustments", json={"scope": "global", "percent": -10, "active": True}
    )
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "productId": products["in_category_product_id"],
            "percent": -50,
            "active": True,
        },
    )

    targeted = client.get(f"/v1/public/products/{products['in_category_slug']}").json()
    assert targeted["adjustedMinor"] == round(targeted["priceMinor"] * 0.5)

    other = client.get(f"/v1/public/products/{products['out_of_category_slug']}").json()
    assert other["adjustedMinor"] == round(other["priceMinor"] * 0.9)


def test_price_adjustment_country_scope_beats_global_for_its_visitors(
    client: TestClient, db: SQLiteDatabase
):
    products = _seed_price_adjustment_catalogue(db)
    as_admin(client, db)
    client.put(
        "/v1/admin/price-adjustments", json={"scope": "global", "percent": 20, "active": True}
    )
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "in",
            "productId": products["in_category_product_id"],
            "percent": -25,
            "active": True,
        },
    )

    india = client.get(
        f"/v1/public/products/{products['in_category_slug']}", params={"country": "IN"}
    ).json()
    assert india["adjustedMinor"] == round(india["priceMinor"] * 0.75)

    elsewhere = client.get(
        f"/v1/public/products/{products['in_category_slug']}", params={"country": "FR"}
    ).json()
    assert elsewhere["adjustedMinor"] == round(elsewhere["priceMinor"] * 1.2)


def test_price_adjustment_category_rule_applies_to_products_in_that_category(
    client: TestClient, db: SQLiteDatabase
):
    products = _seed_price_adjustment_catalogue(db)
    as_admin(client, db)
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "categoryId": products["category_id"],
            "percent": -15,
            "active": True,
        },
    )

    in_category = client.get(f"/v1/public/products/{products['in_category_slug']}").json()
    assert in_category["adjustedMinor"] == round(in_category["priceMinor"] * 0.85)

    out_of_category = client.get(f"/v1/public/products/{products['out_of_category_slug']}").json()
    assert out_of_category["adjustedMinor"] is None


def test_price_adjustment_product_rule_beats_a_category_rule(
    client: TestClient, db: SQLiteDatabase
):
    products = _seed_price_adjustment_catalogue(db)
    as_admin(client, db)
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "categoryId": products["category_id"],
            "percent": -15,
            "active": True,
        },
    )
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "productId": products["in_category_product_id"],
            "percent": -60,
            "active": True,
        },
    )

    in_category = client.get(f"/v1/public/products/{products['in_category_slug']}").json()
    assert in_category["adjustedMinor"] == round(in_category["priceMinor"] * 0.4)


def test_inactive_price_adjustment_does_not_apply(client: TestClient, db: SQLiteDatabase):
    products = _seed_price_adjustment_catalogue(db)
    as_admin(client, db)
    client.put(
        "/v1/admin/price-adjustments",
        json={
            "scope": "global",
            "productId": products["in_category_product_id"],
            "percent": -50,
            "active": False,
        },
    )
    in_category = client.get(f"/v1/public/products/{products['in_category_slug']}").json()
    assert in_category["adjustedMinor"] is None


# --- Appearance: colours and effects ----------------------------------------


def test_owner_can_save_and_clear_theme_colours(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)

    empty = client.get("/v1/admin/appearance")
    assert empty.status_code == 200
    body = empty.json()
    assert body["theme"] == {"global": {}, "countries": {}, "pages": {}}
    assert body["countryEffects"] == {}
    assert body["scopes"] == [
        {
            "scope": "global",
            "tokens": {},
            "hasEffectsOverride": False,
            "updatedAt": "2026-08-01T00:00:00Z",
        }
    ]
    assert "brandPrimary" in body["tokenKeys"]
    assert "snow" in body["ambientEffects"]
    assert "ribbon" in body["cursorTrails"]

    saved = client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "global", "tokens": {"brandPrimary": "#112233", "textPrimary": ""}},
    )
    assert saved.status_code == 200
    assert saved.json()["theme"]["global"] == {"brandPrimary": "#112233"}

    # The public payload -- what the storefront actually renders from -- must
    # agree with what the console just saved, or the preview would lie.
    public = client.get("/v1/public/settings").json()
    assert public["theme"]["global"] == {"brandPrimary": "#112233"}

    cleared = client.put(
        "/v1/admin/appearance/theme", json={"scope": "global", "tokens": {"brandPrimary": ""}}
    )
    assert cleared.status_code == 200
    assert cleared.json()["theme"]["global"] == {}


def test_owner_can_theme_a_single_page_without_touching_the_site_wide_palette(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "global", "tokens": {"brandPrimary": "#111111"}},
    )
    page = client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "/shop/", "tokens": {"brandAccent": "#ff8800"}},
    )
    assert page.status_code == 200
    # Trailing slash normalised away: "/shop/" and "/shop" are the same page.
    assert page.json()["theme"]["pages"] == {"/shop": {"brandAccent": "#ff8800"}}
    assert page.json()["theme"]["global"] == {"brandPrimary": "#111111"}

    removed = client.delete("/v1/admin/appearance/theme/shop")
    assert removed.status_code == 200
    assert removed.json()["theme"]["pages"] == {}
    # The site-wide colour survives deleting a page override.
    assert removed.json()["theme"]["global"] == {"brandPrimary": "#111111"}


def test_theme_rejects_unsafe_values_and_unknown_scopes(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    unsafe = client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "global", "tokens": {"brandPrimary": "url(javascript:alert(1))"}},
    )
    assert unsafe.status_code == 422

    unknown_token = client.put(
        "/v1/admin/appearance/theme", json={"scope": "global", "tokens": {"notAToken": "#fff"}}
    )
    assert unknown_token.status_code == 422

    bad_scope = client.put("/v1/admin/appearance/theme", json={"scope": "not-a-path", "tokens": {}})
    assert bad_scope.status_code == 422

    # The global palette is a clear-only surface -- it cannot be deleted, only
    # emptied, so the console always has somewhere to load the site-wide form.
    assert client.delete("/v1/admin/appearance/theme/global").status_code == 422


def test_owner_can_save_ambient_effect_and_cursor_trail(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    saved = client.put(
        "/v1/admin/appearance/effects",
        json={
            "ambient": {"effect": "snow", "color": "#ffffff", "intensity": 4},
            "cursor": {"trail": "sparkle", "color": "#24483a", "hideNativeCursor": True},
        },
    )
    assert saved.status_code == 200
    effects = saved.json()["effects"]
    assert effects["ambient"] == {"effect": "snow", "color": "#ffffff", "intensity": 4}
    assert effects["cursor"] == {
        "trail": "sparkle",
        "color": "#24483a",
        "hideNativeCursor": True,
    }

    public = client.get("/v1/public/settings").json()
    assert public["effects"] == effects


def test_effects_reject_unknown_keys_and_out_of_range_intensity(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    assert (
        client.put(
            "/v1/admin/appearance/effects",
            json={"ambient": {"effect": "blizzard"}, "cursor": {}},
        ).status_code
        == 422
    )
    assert (
        client.put(
            "/v1/admin/appearance/effects",
            json={"ambient": {"effect": "snow", "intensity": 9}, "cursor": {}},
        ).status_code
        == 422
    )


def test_public_settings_default_to_no_theme_and_no_effects(client: TestClient, db: SQLiteDatabase):
    """A storefront nobody has ever customised must render the stock palette
    and stay perfectly still -- decoration is opt-in, never a surprise."""
    body = client.get("/v1/public/settings").json()
    assert body["theme"] == {"global": {}, "pages": {}}
    assert body["effects"]["ambient"]["effect"] == "none"
    assert body["effects"]["cursor"]["trail"] == "none"


def test_country_colours_override_global_but_lose_to_a_page(client: TestClient, db: SQLiteDatabase):
    """Global < country < page, key by key -- see `load_public_appearance`."""
    as_admin(client, db)
    client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "global", "tokens": {"brandPrimary": "#111111", "brandAccent": "#222222"}},
    )
    saved = client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "country:IN", "tokens": {"brandPrimary": "#e64545"}},
    )
    assert saved.status_code == 200
    assert saved.json()["theme"]["countries"] == {"country:IN": {"brandPrimary": "#e64545"}}

    # A visitor from India: country overrides brandPrimary, global still
    # supplies brandAccent (the country row never mentioned it).
    india = client.get("/v1/public/settings?country=IN").json()
    assert india["theme"]["global"] == {"brandPrimary": "#e64545", "brandAccent": "#222222"}

    # A visitor from anywhere else sees the untouched global palette.
    elsewhere = client.get("/v1/public/settings?country=FR").json()
    assert elsewhere["theme"]["global"] == {"brandPrimary": "#111111", "brandAccent": "#222222"}
    assert (
        client.get("/v1/public/settings").json()["theme"]["global"] == elsewhere["theme"]["global"]
    )

    # A page override still wins over the country override for the same key.
    client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "/shop", "tokens": {"brandPrimary": "#0000ff"}},
    )
    india_shop = client.get("/v1/public/settings?country=IN").json()
    # The public payload's `theme.pages` is unresolved by design -- the
    # storefront itself picks the right page by pathname (`resolveThemeTokens`)
    # from whatever is already the visitor's global layer.
    assert india_shop["theme"]["pages"] == {"/shop": {"brandPrimary": "#0000ff"}}
    assert india_shop["theme"]["global"] == {"brandPrimary": "#e64545", "brandAccent": "#222222"}


def test_country_code_is_validated_and_normalised(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    lowercase = client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "country:in", "tokens": {"brandPrimary": "#111"}},
    )
    assert lowercase.status_code == 200
    assert lowercase.json()["theme"]["countries"] == {"country:IN": {"brandPrimary": "#111"}}

    too_long = client.put("/v1/admin/appearance/theme", json={"scope": "country:IND", "tokens": {}})
    assert too_long.status_code == 422

    # Cloudflare's own sentinels for "unknown"/"Tor" are not real countries --
    # a theme saved under one would never resolve for an actual visitor.
    sentinel = client.put("/v1/admin/appearance/theme", json={"scope": "country:XX", "tokens": {}})
    assert sentinel.status_code == 422


def test_country_effects_override_replaces_rather_than_merges(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    client.put(
        "/v1/admin/appearance/effects",
        json={"ambient": {"effect": "none", "color": "#ffffff", "intensity": 3}, "cursor": {}},
    )
    saved = client.put(
        "/v1/admin/appearance/effects",
        json={
            "ambient": {"effect": "snow", "color": "#ffffff", "intensity": 5},
            "cursor": {"trail": "snow", "color": "#ffffff", "hideNativeCursor": False},
            "scope": "country:CA",
        },
    )
    assert saved.status_code == 200
    assert saved.json()["countryEffects"]["country:CA"]["ambient"]["effect"] == "snow"
    # The global default is untouched by a country-scoped save.
    assert saved.json()["effects"]["ambient"]["effect"] == "none"

    canada = client.get("/v1/public/settings?country=CA").json()
    assert canada["effects"]["ambient"]["effect"] == "snow"
    india = client.get("/v1/public/settings?country=IN").json()
    assert india["effects"]["ambient"]["effect"] == "none"


def test_clearing_a_country_effects_override_keeps_its_colours(
    client: TestClient, db: SQLiteDatabase
):
    """Effects and colours are independently clearable on the same country row."""
    as_admin(client, db)
    client.put(
        "/v1/admin/appearance/theme",
        json={"scope": "country:DE", "tokens": {"brandPrimary": "#ffcc00"}},
    )
    client.put(
        "/v1/admin/appearance/effects",
        json={"ambient": {"effect": "leaves"}, "cursor": {}, "scope": "country:DE"},
    )

    cleared = client.delete("/v1/admin/appearance/effects/country:DE")
    assert cleared.status_code == 200
    assert "country:DE" not in cleared.json()["countryEffects"]
    # The colours saved on the same scope survive clearing its effects.
    assert cleared.json()["theme"]["countries"] == {"country:DE": {"brandPrimary": "#ffcc00"}}

    germany = client.get("/v1/public/settings?country=DE").json()
    assert germany["effects"]["ambient"]["effect"] == "none"
    assert germany["theme"]["global"]["brandPrimary"] == "#ffcc00"

    # Clearing again is a no-op, not an error: the country:DE row still exists
    # (it holds colours), it simply has no effects override to remove.
    again = client.delete("/v1/admin/appearance/effects/country:DE")
    assert again.status_code == 200
    assert again.json()["theme"]["countries"] == {"country:DE": {"brandPrimary": "#ffcc00"}}

    # A country with no row at all -- no colours, no effects ever saved -- has
    # truly nothing to clear, which is the genuine 404 case.
    assert client.delete("/v1/admin/appearance/effects/country:JP").status_code == 404


def test_effects_scope_rejects_a_page_path(client: TestClient, db: SQLiteDatabase):
    """Effects are global-or-country only -- never page-scoped, unlike colours."""
    as_admin(client, db)
    response = client.put(
        "/v1/admin/appearance/effects",
        json={"ambient": {}, "cursor": {}, "scope": "/shop"},
    )
    assert response.status_code == 422


def test_farm_owner_cannot_manage_appearance(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    assert client.get("/v1/admin/appearance").status_code == 403
    assert (
        client.put("/v1/admin/appearance/theme", json={"scope": "global", "tokens": {}}).status_code
        == 403
    )
    assert (
        client.put("/v1/admin/appearance/effects", json={"ambient": {}, "cursor": {}}).status_code
        == 403
    )


def test_owner_can_manage_cms_page_seo_and_blocks(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    pages = client.get("/v1/admin/pages")
    assert pages.status_code == 200
    slugs = {page["slug"] for page in pages.json()["items"]}
    assert {"about", "delivery", "returns", "privacy", "terms", "help", "standards"} <= slugs
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


# --- Owner-only: server logs & DB browser ------------------------------------


def test_owner_can_view_server_logs(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    asyncio.run(persist_log(db, "error", "app_error", requestId="req_test_1", code="boom"))

    response = client.get("/v1/admin/server-logs")
    assert response.status_code == 200
    body = response.json()
    assert body["limit"] == 50
    assert body["offset"] == 0
    entry = next(item for item in body["items"] if item["event"] == "app_error")
    assert entry["level"] == "error"
    assert entry["fields"]["code"] == "boom"
    assert entry["fields"]["requestId"] == "req_test_1"


def test_server_logs_pagination_is_capped_and_parameterized(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert client.get("/v1/admin/server-logs?limit=101").status_code == 422
    assert client.get("/v1/admin/server-logs?limit=0").status_code == 422
    assert client.get("/v1/admin/server-logs?offset=-1").status_code == 422
    ok = client.get("/v1/admin/server-logs?limit=5&offset=0")
    assert ok.status_code == 200
    assert ok.json()["limit"] == 5


def test_owner_can_browse_db_tables(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    tables = client.get("/v1/admin/db-browser/tables")
    assert tables.status_code == 200
    names = tables.json()["items"]
    assert "products" in names
    assert "user_credentials" not in names
    assert "sessions" not in names
    assert "auth_rate_limits" not in names

    detail = client.get("/v1/admin/db-browser/tables/products?limit=5")
    assert detail.status_code == 200
    body = detail.json()
    assert "id" in body["columns"]
    assert "name" in body["columns"]
    assert isinstance(body["rows"], list)
    assert len(body["rows"]) <= 5


def test_db_browser_rejects_unknown_table(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert client.get("/v1/admin/db-browser/tables/not_a_real_table").status_code == 404


def test_db_browser_rejects_blocklisted_table_by_direct_name(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    assert client.get("/v1/admin/db-browser/tables/user_credentials").status_code == 404
    assert client.get("/v1/admin/db-browser/tables/sessions").status_code == 404


def test_db_browser_rejects_sql_injection_attempt_in_table_name(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    response = client.get(
        "/v1/admin/db-browser/tables/products%3B%20DROP%20TABLE%20products%3B%20--"
    )
    assert response.status_code == 404
    still_there = db._conn.execute("SELECT COUNT(*) FROM products").fetchone()[0]
    assert still_there > 0


def test_only_owner_can_view_server_logs_or_db_browser_even_with_audit_view_granted(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    permission_ids = {
        permission["key"]: permission["id"]
        for permission in client.get("/v1/admin/permissions").json()["items"]
    }
    # The PATCH endpoint enforces a business rule that farm-owner sub-admins
    # can only ever hold products/inventory/media permissions, so it refuses
    # to grant audit.view through the API (422) -- insert directly to isolate
    # what this test actually checks: the owner-hard-gate, not that rule.
    db._conn.execute(
        "INSERT INTO role_permissions (role_id, permission_id) VALUES ('rol_farm_owner', ?)",
        (permission_ids["audit.view"],),
    )
    db._conn.commit()

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    me = client.get("/v1/admin/me").json()
    assert "audit.view" in me["permissions"]  # confirms the grant took effect

    # The permission alone is not authorization: _require_owner still blocks a
    # non-super_admin principal from every route in both feature groups.
    assert client.get("/v1/admin/server-logs").status_code == 403
    assert client.get("/v1/admin/db-browser/tables").status_code == 403
    assert client.get("/v1/admin/db-browser/tables/products").status_code == 403


# --- Articles / Recipes: delete, bulk-delete, archive, restore, purge -------


def test_article_delete_and_bulk_delete_archive_instead_of_removing_the_row(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    first_id = client.post("/v1/admin/articles", json={"title": "Delete-me post one"}).json()["id"]
    second_id = client.post("/v1/admin/articles", json={"title": "Delete-me post two"}).json()["id"]

    deleted = client.delete(f"/v1/admin/articles/{first_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "archived"

    bulk = client.post("/v1/admin/articles/bulk-delete", json={"articleIds": [second_id]})
    assert bulk.status_code == 200
    assert bulk.json() == {"deletedIds": [second_id], "count": 1}

    # Archived posts drop out of the normal admin list...
    list_ids = {row["id"] for row in client.get("/v1/admin/articles").json()["items"]}
    assert first_id not in list_ids
    assert second_id not in list_ids

    # ...but the row survives (soft-delete) and shows up in the Archive.
    archive_rows = client.get("/v1/admin/archive", params={"search": "Delete-me"}).json()["items"]
    archived_ids = {row["id"]: row for row in archive_rows}
    assert archived_ids[first_id]["kind"] == "article"
    assert archived_ids[first_id]["status"] == "archived"
    assert archived_ids[second_id]["kind"] == "article"

    restored = client.post(f"/v1/admin/archive/article/{first_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    restored_list_ids = {row["id"] for row in client.get("/v1/admin/articles").json()["items"]}
    assert first_id in restored_list_ids

    actions = [row["action"] for row in client.get("/v1/admin/audit").json()["items"]]
    assert "article.archived" in actions
    assert "article.restored" in actions


def test_recipe_delete_and_bulk_delete_archive_instead_of_removing_the_row(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    first_id = client.post("/v1/admin/recipes", json={"title": "Delete-me recipe one"}).json()["id"]
    second_id = client.post("/v1/admin/recipes", json={"title": "Delete-me recipe two"}).json()[
        "id"
    ]

    deleted = client.delete(f"/v1/admin/recipes/{first_id}")
    assert deleted.status_code == 200
    assert deleted.json()["status"] == "archived"

    bulk = client.post("/v1/admin/recipes/bulk-delete", json={"recipeIds": [second_id]})
    assert bulk.status_code == 200
    assert bulk.json() == {"deletedIds": [second_id], "count": 1}

    list_ids = {row["id"] for row in client.get("/v1/admin/recipes").json()["items"]}
    assert first_id not in list_ids
    assert second_id not in list_ids

    archive_rows = client.get("/v1/admin/archive", params={"search": "Delete-me"}).json()["items"]
    archived_ids = {row["id"]: row for row in archive_rows}
    assert archived_ids[first_id]["kind"] == "recipe"
    assert archived_ids[second_id]["kind"] == "recipe"

    restored = client.post(f"/v1/admin/archive/recipe/{first_id}/restore")
    assert restored.status_code == 200
    assert restored.json()["status"] == "draft"
    restored_list_ids = {row["id"] for row in client.get("/v1/admin/recipes").json()["items"]}
    assert first_id in restored_list_ids


def test_article_delete_requires_articles_edit_permission(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    article_id = client.post("/v1/admin/articles", json={"title": "Permission check post"}).json()[
        "id"
    ]

    client.cookies.set(
        SESSION_COOKIE, create_session(db, "usr_pm")
    )  # product manager, no articles.*
    response = client.delete(f"/v1/admin/articles/{article_id}")
    assert response.status_code == 403


# --- Discussions: bulk-delete (hard delete, matches single-delete semantics) -


def test_discussion_bulk_delete_removes_threads_permanently(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    seeded = client.get("/v1/admin/discussions", params={"limit": 2}).json()["items"]
    assert len(seeded) == 2
    target_ids = [row["id"] for row in seeded]

    bulk = client.post("/v1/admin/discussions/bulk-delete", json={"discussionIds": target_ids})
    assert bulk.status_code == 200
    assert bulk.json() == {"deletedIds": target_ids, "count": 2}

    for discussion_id in target_ids:
        assert client.get(f"/v1/admin/discussions/{discussion_id}").status_code == 404

    actions = [row["action"] for row in client.get("/v1/admin/audit").json()["items"]]
    assert "discussion.deleted" in actions


# --- Archive: bulk purge (permanent delete of already-archived rows) --------


def test_archive_bulk_purge_permanently_removes_archived_rows(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    article_id = client.post("/v1/admin/articles", json={"title": "Purge-me post"}).json()["id"]
    assert client.delete(f"/v1/admin/articles/{article_id}").status_code == 200

    purge = client.post(
        "/v1/admin/archive/bulk-delete", json={"items": [{"kind": "article", "id": article_id}]}
    )
    assert purge.status_code == 200
    assert purge.json() == {"deleted": [{"kind": "article", "id": article_id}], "count": 1}

    # Gone for good: not editable, and no longer even in the Archive list.
    assert client.get(f"/v1/admin/articles/{article_id}").status_code == 404
    archive_rows = client.get("/v1/admin/archive", params={"search": "Purge-me"}).json()["items"]
    assert article_id not in {row["id"] for row in archive_rows}

    actions = [row["action"] for row in client.get("/v1/admin/audit").json()["items"]]
    assert "article.purged" in actions


def test_archive_bulk_purge_of_unarchived_item_is_404(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    # A fresh product, never archived in this test's own DB state.
    product_id = client.post(
        "/v1/admin/products", json={"name": "Never Archived Widget", "productType": "pantry"}
    ).json()["id"]
    response = client.post(
        "/v1/admin/archive/bulk-delete",
        json={"items": [{"kind": "product", "id": product_id}]},
    )
    assert response.status_code == 404


def test_archive_bulk_purge_blocked_by_order_history_returns_conflict(
    client: TestClient, db: SQLiteDatabase
):
    """A product whose variant carries inventory movement history (e.g. a
    stock receipt) is referenced by `inventory_movements` (ON DELETE
    RESTRICT) -- purging it must fail loudly with a clear, safe error instead
    of corrupting that history or leaking a raw database error."""
    as_admin(client, db)
    product_id = client.post(
        "/v1/admin/products", json={"name": "Purge Conflict Widget", "productType": "pantry"}
    ).json()["id"]
    created_variant = client.post(
        f"/v1/admin/products/{product_id}/variants",
        json={"name": "Default", "sku": "PURGE-CONFLICT-1", "listMinor": 5000},
    )
    assert created_variant.status_code == 200, created_variant.text
    adjusted = client.post(
        "/v1/admin/inventory/adjustments",
        json={
            "sku": "PURGE-CONFLICT-1",
            "quantityDelta": 5,
            "reasonCode": "receipt",
            "note": "Initial stock",
        },
    )
    assert adjusted.status_code == 200, adjusted.text
    assert client.post(f"/v1/admin/products/{product_id}/archive").status_code == 200

    purge = client.post(
        "/v1/admin/archive/bulk-delete",
        json={"items": [{"kind": "product", "id": product_id}]},
    )
    assert purge.status_code == 409
    assert "still depend on it" in purge.json()["error"]["message"]

    # The product must still exist, untouched, after the failed purge.
    assert client.get(f"/v1/admin/products/{product_id}").status_code == 404  # archived, not gone
    archive_rows = client.get(
        "/v1/admin/archive", params={"search": "Purge Conflict Widget"}
    ).json()["items"]
    assert any(row["id"] == product_id for row in archive_rows)

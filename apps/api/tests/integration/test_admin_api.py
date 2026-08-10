"""Authorization matrix and the publish loop: no session -> 401, wrong permission
-> 403, correct permission -> success with audit + outbox written atomically."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

# Several tests below used to read/write specific rows from the demo catalogue
# seeded by migration 0059 (prd_alphonso, prd_spinach, prd_rajma, prd_ragi,
# cat_fresh_fruits, ...). Migration 0095 is a real, unconditional production
# cutover: it archives every pre-existing product/category on every database
# it touches, including fresh test ones, so those rows are excluded from every
# admin/public catalogue query from here on (products/categories are archived,
# not deleted, so their ids still physically exist -- reusing one of those ids
# for a fresh INSERT would collide). This module builds its own small,
# obviously-synthetic products/categories instead of depending on catalogue
# content that keeps moving out from under it.
FARM_ID = "farm_ta_orchard"

CATEGORY_ID = "cat_ta_shelf"
PUBLISH_CATEGORY_ID = "cat_ta_publish"

MANGO_ID = "prd_ta_mango"
MANGO_NAME = "Zephyr Orchard Mangoes"
MANGO_SLUG = "zephyr-orchard-mangoes"
MANGO_VARIANT_1_SKU = "TST-MNG-1KG"

GREENS_ID = "prd_ta_greens"
GREENS_NAME = "Testbed Baby Greens"
GREENS_SLUG = "testbed-baby-greens"

PULSES_ID = "prd_ta_pulses"
PULSES_NAME = "Testbed Field Lentils"
PULSES_SLUG = "testbed-field-lentils"

GRAIN_ID = "prd_ta_grain"
GRAIN_NAME = "Testbed Sprouted Ragi"
GRAIN_SLUG = "testbed-sprouted-ragi"


def _add_product(
    db: SQLiteDatabase,
    *,
    product_id: str,
    name: str,
    slug: str,
    farm_id: str | None = None,
    category_ids: list[str] = (),
    variants: list[tuple[str, str, int, int, int]] = (),
    # variants: (variant_id, sku, list_minor, on_hand, reserved), sort order = list order
) -> None:
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id,"
        " status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', ?, 'published',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, name, name, slug, farm_id),
    )
    for index, category_id in enumerate(category_ids):
        db._conn.execute(
            "INSERT INTO product_categories (product_id, category_id, is_primary,"
            " sort_order, assigned_at, assigned_by)"
            " VALUES (?, ?, ?, ?, '2026-07-01T00:00:00Z', 'usr_admin')",
            (product_id, category_id, 1 if index == 0 else 0, index),
        )
    for index, (variant_id, sku, list_minor, on_hand, reserved) in enumerate(variants):
        db._conn.execute(
            "INSERT INTO product_variants (id, product_id, sku, name, status,"
            " sort_order, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'active', ?, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')",
            (variant_id, product_id, sku, sku, index + 1),
        )
        db._conn.execute(
            "INSERT INTO variant_prices (id, variant_id, market_code, currency_code,"
            " list_amount_minor, starts_at, status, created_at, created_by)"
            " VALUES (?, ?, 'IN', 'INR', ?, '2026-07-01T00:00:00Z', 'active',"
            " '2026-07-01T00:00:00Z', 'usr_admin')",
            (f"vpr_{variant_id.removeprefix('var_')}", variant_id, list_minor),
        )
        db._conn.execute(
            "INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,"
            " reorder_threshold, version, updated_at)"
            " VALUES (?, 'loc_mumbai', ?, ?, 5, 1, '2026-07-01T00:00:00Z')",
            (variant_id, on_hand, reserved),
        )


@pytest.fixture(autouse=True)
def _admin_baseline(db: SQLiteDatabase) -> None:
    """A small, self-contained synthetic catalogue: one farm, one published
    shelf category, one draft category (for the publish-flow test), and four
    published products covering every shape these tests touch (multi-variant
    pricing/stock, an editable image+farm+categories payload, a bare product
    to attach a new variant to, and two products to link/highlight together).
    See the module note above for why this can't be the retired demo
    catalogue or today's live one."""
    db._conn.execute(
        "INSERT INTO farms (id, name, slug, country_code, status, created_at,"
        " created_by, updated_at, updated_by)"
        " VALUES (?, 'Testbed Orchard Collective', 'testbed-orchard-collective', 'IN',"
        " 'published', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (FARM_ID,),
    )
    db._conn.execute(
        "INSERT INTO categories (id, internal_name, name, slug, path, level, sort_order,"
        " status, visibility, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, 'Test Shelf Staples', 'Test Shelf Staples', 'ta-shelf-staples',"
        " 'ta-shelf-staples', 0, 1, 'published', 'public',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (CATEGORY_ID,),
    )
    db._conn.execute(
        "INSERT INTO categories (id, internal_name, name, slug, path, level, sort_order,"
        " status, visibility, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, 'Test Publish Category', 'Test Publish Category', 'ta-publish-category',"
        " 'ta-publish-category', 0, 2, 'draft', 'public',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (PUBLISH_CATEGORY_ID,),
    )
    _add_product(
        db,
        product_id=MANGO_ID,
        name=MANGO_NAME,
        slug=MANGO_SLUG,
        farm_id=FARM_ID,
        category_ids=[CATEGORY_ID],
        variants=[
            ("var_ta_mango_1", MANGO_VARIANT_1_SKU, 89_900, 120, 4),
            ("var_ta_mango_2", "TST-MNG-2KG", 199_900, 60, 2),
            ("var_ta_mango_3", "TST-MNG-5KG", 399_900, 24, 0),
        ],
    )
    _add_product(db, product_id=GREENS_ID, name=GREENS_NAME, slug=GREENS_SLUG)
    _add_product(
        db,
        product_id=PULSES_ID,
        name=PULSES_NAME,
        slug=PULSES_SLUG,
        variants=[("var_ta_pulses_1", "TST-PLS-500G", 19_900, 8, 0)],
    )
    _add_product(
        db,
        product_id=GRAIN_ID,
        name=GRAIN_NAME,
        slug=GRAIN_SLUG,
        variants=[("var_ta_grain_1", "TST-GRN-500G", 14_500, 340, 0)],
    )
    db._conn.commit()


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
    assert client.post("/v1/admin/categories/cat_ta_publish/publish").status_code == 403


def test_me_returns_permissions(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    body = client.get("/v1/admin/me").json()
    assert body["displayName"] == "Asha Rao"
    assert "categories.publish" in body["permissions"]
    assert body["isSuperAdmin"] is True


def test_me_identifies_non_super_admin(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_pm"))
    assert client.get("/v1/admin/me").json()["isSuperAdmin"] is False


def test_site_documents_are_owner_only(client: TestClient, db: SQLiteDatabase):
    db._conn.executescript(
        """
        INSERT OR IGNORE INTO role_permissions (role_id, permission_id) VALUES
          ('rol_content_editor', 'prm_settings_view'),
          ('rol_content_editor', 'prm_settings_edit');
        """
    )
    db._conn.commit()

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.get("/v1/admin/site-documents").status_code == 403

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    current = client.get("/v1/admin/site-documents")
    assert current.status_code == 200
    assert "Sitemap:" in current.json()["robotsTxt"]

    updated = client.patch(
        "/v1/admin/site-documents",
        json={"robotsTxt": "User-agent: *\nDisallow:\n"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["robotsTxt"] == "User-agent: *\nDisallow:\n"
    public = client.get("/v1/public/site-documents/robots_txt").json()
    assert public["content"] == "User-agent: *\nDisallow:\n"


def test_product_list_shape(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    # Pinned with `search` rather than reading a fixed row off page one: the
    # catalogue holds hundreds of products, and this asserts row shape, not
    # catalogue size.
    items = client.get("/v1/admin/products", params={"search": "Zephyr"}).json()["items"]
    alphonso = next(item for item in items if item["id"] == "prd_ta_mango")
    assert alphonso["sku"] == "TST-MNG-1KG"
    assert "imageUrl" in alphonso
    assert "imageAlt" in alphonso
    assert alphonso["priceRange"] == "899-3999"
    assert alphonso["availableStock"] == 198  # (120-4) + (60-2) + (24-0)


def test_product_list_pages_rather_than_returning_everything(
    client: TestClient, db: SQLiteDatabase
):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    first = client.get("/v1/admin/products", params={"limit": 10}).json()["items"]
    second = client.get("/v1/admin/products", params={"limit": 10, "offset": 10}).json()["items"]
    assert len(first) == len(second) == 10
    assert not {row["id"] for row in first} & {row["id"] for row in second}


def test_product_image_replacement_with_full_editor_payload(client: TestClient, db: SQLiteDatabase):
    """Replacing an image must tolerate the unchanged farm/categories that
    the general editor submits alongside the new URL."""
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    detail = client.get("/v1/admin/products/prd_ta_mango").json()

    response = client.patch(
        "/v1/admin/products/prd_ta_mango",
        json={
            "name": detail["name"],
            "slug": detail["slug"],
            "shortDescription": detail["shortDescription"],
            "imageUrl": "/media/images/med_replacement.jpg",
            "imageAlt": "Replacement Alphonso mango image",
            "farmId": detail["farmId"],
            "categoryIds": detail["categoryIds"],
        },
    )

    assert response.status_code == 200, response.text
    updated = client.get("/v1/admin/products/prd_ta_mango").json()
    assert updated["imageUrl"] == "/media/images/med_replacement.jpg"
    assert updated["imageAlt"] == "Replacement Alphonso mango image"
    assert updated["farmId"] == detail["farmId"]
    assert updated["categoryIds"] == detail["categoryIds"]


def test_primary_variant_create_and_update(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    created = client.post(
        "/v1/admin/products/prd_ta_greens/variants",
        json={"name": "Family pack", "sku": "TRG-SPINACH-FAMILY", "listMinor": 49900},
    )
    assert created.status_code == 200, created.text
    variant_id = created.json()["id"]

    updated = client.patch(
        f"/v1/admin/products/prd_ta_greens/variants/{variant_id}",
        json={
            "name": "Family pack",
            "sku": "TRG-SPINACH-FAMILY-2",
            "listMinor": 45900,
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["changed"] is True

    detail = client.get("/v1/admin/products/prd_ta_greens").json()
    variant = next(item for item in detail["variants"] if item["id"] == variant_id)
    assert variant["sku"] == "TRG-SPINACH-FAMILY-2"
    assert variant["listMinor"] == 45900


def test_publish_category_writes_audit_and_outbox(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.post("/v1/admin/categories/cat_ta_publish/publish")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "published"
    assert body["version"] == 1

    audit_rows = db._conn.execute(
        "SELECT action FROM audit_logs WHERE entity_id = 'cat_ta_publish'"
    ).fetchall()
    assert [row["action"] for row in audit_rows] == ["category.published"]

    outbox_rows = db._conn.execute(
        "SELECT event_type, status FROM outbox_events WHERE aggregate_id = 'cat_ta_publish'"
    ).fetchall()
    assert [(row["event_type"], row["status"]) for row in outbox_rows] == [
        ("content.category.published.v1", "pending")
    ]

    version = db._conn.execute(
        "SELECT workflow_state, version_number FROM category_versions"
        " WHERE category_id = 'cat_ta_publish'"
    ).fetchone()
    assert version["workflow_state"] == "published"

    # Second publish creates version 2 — versions are immutable and monotonic.
    second = client.post("/v1/admin/categories/cat_ta_publish/publish").json()
    assert second["version"] == 2


def test_publish_unknown_category_404(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    assert client.post("/v1/admin/categories/cat_missing/publish").status_code == 404


def test_product_release_roundtrip(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.patch(
        "/v1/admin/products/prd_ta_pulses",
        json={"releaseScope": "selected", "releaseCountries": ["us", "AE"]},
    )
    assert response.status_code == 200, response.text

    detail = client.get("/v1/admin/products/prd_ta_pulses").json()
    assert detail["releaseScope"] == "selected"
    assert detail["releaseCountries"] == ["AE", "US"]

    # The storefront in India no longer sees it; the UAE does.
    india = client.get(
        "/v1/public/products",
        params={"country": "IN", "slugs": "testbed-field-lentils"},
    ).json()
    assert "testbed-field-lentils" not in {p["slug"] for p in india["items"]}
    uae = client.get(
        "/v1/public/products",
        params={"country": "AE", "slugs": "testbed-field-lentils"},
    ).json()
    assert "testbed-field-lentils" in {p["slug"] for p in uae["items"]}

    # Back to global: the country list is cleared.
    client.patch("/v1/admin/products/prd_ta_pulses", json={"releaseScope": "global"})
    detail = client.get("/v1/admin/products/prd_ta_pulses").json()
    assert detail["releaseScope"] == "global"
    assert detail["releaseCountries"] == []


def test_product_release_validation(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    empty = client.patch(
        "/v1/admin/products/prd_ta_pulses",
        json={"releaseScope": "selected", "releaseCountries": []},
    )
    assert empty.status_code == 422
    bad_code = client.patch(
        "/v1/admin/products/prd_ta_pulses",
        json={"releaseScope": "selected", "releaseCountries": ["USA"]},
    )
    assert bad_code.status_code == 422
    bad_scope = client.patch(
        "/v1/admin/products/prd_ta_pulses", json={"releaseScope": "everywhere"}
    )
    assert bad_scope.status_code == 422


def test_product_links_roundtrip(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.patch(
        "/v1/admin/products/prd_ta_pulses",
        # Self-links are ignored rather than rejected.
        json={"linkedProductIds": ["prd_ta_greens", "prd_ta_pulses", "prd_ta_grain"]},
    )
    assert response.status_code == 200, response.text

    detail = client.get("/v1/admin/products/prd_ta_pulses").json()
    assert [entry["id"] for entry in detail["linkedProducts"]] == ["prd_ta_greens", "prd_ta_grain"]

    # The public product page serves the curated slots in order.
    public = client.get("/v1/public/products/testbed-field-lentils").json()
    assert public["relatedSlugs"] == ["testbed-baby-greens", "testbed-sprouted-ragi"]

    # Swapping is a plain re-save with a different list.
    client.patch("/v1/admin/products/prd_ta_pulses", json={"linkedProductIds": ["prd_ta_grain"]})
    public = client.get("/v1/public/products/testbed-field-lentils").json()
    assert public["relatedSlugs"] == ["testbed-sprouted-ragi"]

    unknown = client.patch(
        "/v1/admin/products/prd_ta_pulses", json={"linkedProductIds": ["prd_missing"]}
    )
    assert unknown.status_code == 422


def test_highlights_admin_roundtrip(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))

    response = client.put(
        "/v1/admin/highlights", json={"productIds": ["prd_ta_grain", "prd_ta_mango"]}
    )
    assert response.status_code == 200, response.text
    assert [entry["id"] for entry in response.json()["items"]] == ["prd_ta_grain", "prd_ta_mango"]

    public = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in public["items"]] == [
        "testbed-sprouted-ragi",
        "zephyr-orchard-mangoes",
    ]

    # Replacing the list swaps the slots.
    client.put("/v1/admin/highlights", json={"productIds": ["prd_ta_mango"]})
    public = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in public["items"]] == ["zephyr-orchard-mangoes"]


def test_highlights_require_settings_permission(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.put("/v1/admin/highlights", json={"productIds": []}).status_code == 403


def test_inventory_view_permission(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_ops"))
    items = client.get("/v1/admin/inventory").json()["items"]
    # One entry per product (variants nested inside), alphabetical by product
    # name -- the same grouping and order as the admin Products list.
    names = [group["productName"] for group in items]
    assert names == sorted(names)
    assert all(len(group["variants"]) > 0 for group in items)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.get("/v1/admin/inventory").status_code == 403


def test_inventory_bulk_clear_keeps_reserved_and_audits(client: TestClient, db: SQLiteDatabase):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_ops"))
    response = client.post(
        "/v1/admin/inventory/bulk-clear",
        json={
            "variantIds": ["var_alphonso_1kg", "var_spinach_250g"],
            "note": "Clear selected stock from admin.",
        },
    )
    assert response.status_code == 200
    assert response.json()["count"] == 2
    row = db._conn.execute(
        "SELECT on_hand, reserved FROM inventory_levels WHERE variant_id = 'var_alphonso_1kg'"
    ).fetchone()
    assert row["on_hand"] == row["reserved"]
    movement = db._conn.execute(
        """
        SELECT movement_type, reason_code
        FROM inventory_movements
        WHERE variant_id = 'var_alphonso_1kg'
        ORDER BY created_at DESC
        LIMIT 1
        """
    ).fetchone()
    assert movement["movement_type"] == "write_off"
    assert movement["reason_code"] == "bulk_clear"

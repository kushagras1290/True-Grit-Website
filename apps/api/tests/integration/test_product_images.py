"""Product gallery images (migration 0066): additive to the optional main
image, never touching `products.image_url`/`primary_media_id`.

Seeds its own published product (`prd_gallery_test`) with an explicit main
image rather than depending on the demo catalogue: migration 0095 retires
that catalogue from every database it touches (the live site must not keep
any trace of it), so tests cannot rely on it surviving either. It also
archives the old demo products outright and leaves new-catalogue products
with a `NULL` main image by default, so a test asserting against a
*published* product's main image needs a fixture product that sets one
explicitly.
"""

from __future__ import annotations

import pytest

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

PRODUCT_ID = "prd_gallery_test"
PRODUCT_SLUG = "gallery-test-product"


def as_admin(client, db) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


@pytest.fixture(autouse=True)
def _gallery_product(db: SQLiteDatabase) -> None:
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, status,"
        " image_url, image_alt, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, 'Gallery Test Product', 'Gallery Test Product', ?, 'simple',"
        " 'published', '/products/gallery-test-main.jpg', 'Gallery test product main image',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (PRODUCT_ID, PRODUCT_SLUG),
    )
    db._conn.commit()


def test_admin_can_replace_a_products_gallery_images(client, db):
    as_admin(client, db)
    original_main_image = client.get(f"/v1/admin/products/{PRODUCT_ID}").json()["imageUrl"]
    response = client.put(
        f"/v1/admin/products/{PRODUCT_ID}/images",
        json={
            "images": [
                {"imageUrl": "/media/mango-side.jpg", "imageAlt": "Side view"},
                {"imageUrl": "/media/mango-crate.jpg", "imageAlt": "In a crate"},
            ]
        },
    )
    assert response.status_code == 200, response.text
    images = response.json()["images"]
    assert [image["imageUrl"] for image in images] == [
        "/media/mango-side.jpg",
        "/media/mango-crate.jpg",
    ]

    detail = client.get(f"/v1/admin/products/{PRODUCT_ID}")
    assert detail.status_code == 200
    assert len(detail.json()["images"]) == 2
    # The main image field is untouched by a gallery save.
    assert detail.json()["imageUrl"] == original_main_image


def test_gallery_images_are_capped_at_eight(client, db):
    as_admin(client, db)
    response = client.put(
        f"/v1/admin/products/{PRODUCT_ID}/images",
        json={"images": [{"imageUrl": f"/media/x{i}.jpg"} for i in range(9)]},
    )
    assert response.status_code == 422


def test_replacing_gallery_images_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.put(
        f"/v1/admin/products/{PRODUCT_ID}/images",
        json={"images": [{"imageUrl": "/media/x.jpg"}]},
    )
    assert response.status_code == 403


def test_public_product_detail_includes_the_gallery(client, db):
    as_admin(client, db)
    client.put(
        f"/v1/admin/products/{PRODUCT_ID}/images",
        json={"images": [{"imageUrl": "/media/mango-side.jpg", "imageAlt": "Side view"}]},
    )

    response = client.get(f"/v1/public/products/{PRODUCT_SLUG}")
    assert response.status_code == 200, response.text
    images = response.json()["images"]
    assert len(images) == 1
    assert images[0]["imageUrl"] == "/media/mango-side.jpg"
    assert images[0]["imageAlt"] == "Side view"

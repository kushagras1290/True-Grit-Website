"""Product gallery images (migration 0066): additive to the required main
image, never touching `products.image_url`/`primary_media_id`.
"""

from __future__ import annotations

from tests.integration.conftest import SESSION_COOKIE, create_session


def as_admin(client, db) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def test_admin_can_replace_a_products_gallery_images(client, db):
    as_admin(client, db)
    response = client.put(
        "/v1/admin/products/prd_alphonso/images",
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

    detail = client.get("/v1/admin/products/prd_alphonso")
    assert detail.status_code == 200
    assert len(detail.json()["images"]) == 2
    # The main image field is untouched by a gallery save.
    assert detail.json()["imageUrl"]


def test_gallery_images_are_capped_at_eight(client, db):
    as_admin(client, db)
    response = client.put(
        "/v1/admin/products/prd_alphonso/images",
        json={"images": [{"imageUrl": f"/media/x{i}.jpg"} for i in range(9)]},
    )
    assert response.status_code == 422


def test_replacing_gallery_images_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.put(
        "/v1/admin/products/prd_alphonso/images",
        json={"images": [{"imageUrl": "/media/x.jpg"}]},
    )
    assert response.status_code == 403


def test_public_product_detail_includes_the_gallery(client, db):
    as_admin(client, db)
    client.put(
        "/v1/admin/products/prd_alphonso/images",
        json={"images": [{"imageUrl": "/media/mango-side.jpg", "imageAlt": "Side view"}]},
    )

    response = client.get("/v1/public/products/organic-alphonso-mangoes")
    assert response.status_code == 200, response.text
    images = response.json()["images"]
    assert len(images) == 1
    assert images[0]["imageUrl"] == "/media/mango-side.jpg"
    assert images[0]["imageAlt"] == "Side view"

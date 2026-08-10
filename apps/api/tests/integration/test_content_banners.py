"""Integration tests for content banner images and one-click visibility.

Banner images: articles and recipes store a URL + alt pair (migration 0036)
that the admin editor sets and the public API serves — metadata on the entity
row, so changing it takes effect on the live post without a republish cycle.

Visibility: the category status toggle mirrors the product one — the public
API stops listing an unpublished category immediately, which is what empties
it out of homepage category collections.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

# Migration 0095 deliberately replaces the former editorial library with the
# owner-supplied True Grit topic catalogue.
ARTICLE_SLUG = "what-is-kathiya-wheat-origin-taste-texture-and-uses"
RECIPE_SLUG = "vegetable-daliya"
BANNER_URL = "/media/images/img_banner_test.webp"
BANNER_ALT = "Millet fields at harvest"


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def _admin_id_by_slug(client: TestClient, resource: str, slug: str) -> str:
    # The development seed holds hundreds of articles/recipes, so search by
    # slug instead of paging through the whole listing.
    items = client.get(f"/v1/admin/{resource}", params={"search": slug, "limit": 100}).json()[
        "items"
    ]
    return next(item["id"] for item in items if item["slug"] == slug)


def _find_in_public_listing(client: TestClient, resource: str, slug: str) -> dict:
    # The public listing has no search param and caps at 100 rows per page
    # (unlike the admin one above); the curated library is larger than that,
    # so finding a specific pinned slug means walking pages rather than
    # trusting it to land on page one.
    offset = 0
    page_size = 100
    while True:
        page = client.get(f"/v1/public/{resource}", params={"limit": page_size, "offset": offset})
        body = page.json()
        items = body["items"]
        found = next((item for item in items if item["slug"] == slug), None)
        if found is not None:
            return found
        if len(items) < page_size or offset >= body["total"]:
            raise AssertionError(f"{slug!r} not found in /v1/public/{resource} listing")
        offset += page_size


# --- Article banners ---------------------------------------------------------


def test_article_banner_roundtrip(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    article_id = _admin_id_by_slug(client, "articles", ARTICLE_SLUG)

    updated = client.patch(
        f"/v1/admin/articles/{article_id}",
        json={"heroImageUrl": BANNER_URL, "heroImageAlt": BANNER_ALT},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["heroImageUrl"] == BANNER_URL
    assert updated.json()["heroImageAlt"] == BANNER_ALT

    # The banner is entity metadata, not versioned content: the already
    # published article carries it immediately, on the detail and the listing.
    detail = client.get(f"/v1/public/articles/{ARTICLE_SLUG}").json()
    assert detail["heroImageUrl"] == BANNER_URL
    assert detail["heroImageAlt"] == BANNER_ALT

    listed = _find_in_public_listing(client, "articles", ARTICLE_SLUG)
    assert listed["heroImageUrl"] == BANNER_URL


def test_article_banner_clears_to_null(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    article_id = _admin_id_by_slug(client, "articles", ARTICLE_SLUG)
    client.patch(f"/v1/admin/articles/{article_id}", json={"heroImageUrl": BANNER_URL})
    cleared = client.patch(f"/v1/admin/articles/{article_id}", json={"heroImageUrl": ""})
    assert cleared.status_code == 200
    assert client.get(f"/v1/public/articles/{ARTICLE_SLUG}").json()["heroImageUrl"] is None


def test_article_banner_rejects_unsafe_url(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    article_id = _admin_id_by_slug(client, "articles", ARTICLE_SLUG)
    for unsafe in ("javascript:alert(1)", "//evil.example/x.png", "data:image/png;base64,AAAA"):
        response = client.patch(f"/v1/admin/articles/{article_id}", json={"heroImageUrl": unsafe})
        assert response.status_code == 422, unsafe


# --- Recipe banners ----------------------------------------------------------


def test_recipe_banner_roundtrip(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    recipe_id = _admin_id_by_slug(client, "recipes", RECIPE_SLUG)

    updated = client.patch(
        f"/v1/admin/recipes/{recipe_id}",
        json={"heroImageUrl": BANNER_URL, "heroImageAlt": BANNER_ALT},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["heroImageUrl"] == BANNER_URL
    assert updated.json()["heroImageAlt"] == BANNER_ALT

    detail = client.get(f"/v1/public/recipes/{RECIPE_SLUG}").json()
    assert detail["heroImageUrl"] == BANNER_URL
    assert detail["heroImageAlt"] == BANNER_ALT

    listed = _find_in_public_listing(client, "recipes", RECIPE_SLUG)
    assert listed["heroImageUrl"] == BANNER_URL


def test_recipe_banner_rejects_unsafe_url(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    recipe_id = _admin_id_by_slug(client, "recipes", RECIPE_SLUG)
    response = client.patch(
        f"/v1/admin/recipes/{recipe_id}", json={"heroImageUrl": "javascript:alert(1)"}
    )
    assert response.status_code == 422


# --- Category visibility toggle ----------------------------------------------


def test_category_status_toggle_hides_from_public(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)

    def public_slugs() -> set[str]:
        items = client.get("/v1/public/categories").json()["items"]
        return {item["slug"] for item in items}

    assert "wheat-flour" in public_slugs()

    disabled = client.patch(
        "/v1/admin/categories/cat_catalogue_01/status", json={"status": "unpublished"}
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json() == {
        "id": "cat_catalogue_01",
        "status": "unpublished",
        "changed": True,
    }
    assert "wheat-flour" not in public_slugs()

    enabled = client.patch(
        "/v1/admin/categories/cat_catalogue_01/status", json={"status": "published"}
    )
    assert enabled.status_code == 200
    assert "wheat-flour" in public_slugs()

    # Toggling to the current status is a no-op, not an error.
    repeat = client.patch(
        "/v1/admin/categories/cat_catalogue_01/status", json={"status": "published"}
    )
    assert repeat.status_code == 200
    assert repeat.json()["changed"] is False


def test_category_thumbnail_is_distinct_from_page_banner(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    banner = "/catalogue/categories/banners/wheat-flour.webp"
    thumbnail = "/catalogue/categories/thumbnails/wheat-flour.webp"

    updated = client.patch(
        "/v1/admin/categories/cat_catalogue_01",
        json={
            "heroImageUrl": banner,
            "heroImageAlt": "Wide wheat flour banner",
            "thumbnailImageUrl": thumbnail,
            "thumbnailImageAlt": "Square wheat flour thumbnail",
        },
    )
    assert updated.status_code == 200, updated.text

    admin_detail = client.get("/v1/admin/categories/cat_catalogue_01").json()
    assert admin_detail["heroImageUrl"] == banner
    assert admin_detail["thumbnailImageUrl"] == thumbnail

    public_detail = client.get("/v1/public/categories/wheat-flour").json()
    assert public_detail["hero"]["imageUrl"] == banner
    public_list = client.get("/v1/public/categories").json()["items"]
    listed = next(item for item in public_list if item["slug"] == "wheat-flour")
    assert listed["imageUrl"] == thumbnail

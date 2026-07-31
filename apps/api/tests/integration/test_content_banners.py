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

ARTICLE_SLUG = "quiet-revival-of-indian-millets"
RECIPE_SLUG = "crisp-sprouted-ragi-dosa"
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

    listing = client.get("/v1/public/articles", params={"limit": 100}).json()["items"]
    listed = next(item for item in listing if item["slug"] == ARTICLE_SLUG)
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

    listing = client.get("/v1/public/recipes", params={"limit": 100}).json()["items"]
    listed = next(item for item in listing if item["slug"] == RECIPE_SLUG)
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

    assert "fresh-fruits" in public_slugs()

    disabled = client.patch(
        "/v1/admin/categories/cat_fresh_fruits/status", json={"status": "unpublished"}
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json() == {"id": "cat_fresh_fruits", "status": "unpublished", "changed": True}
    assert "fresh-fruits" not in public_slugs()

    enabled = client.patch(
        "/v1/admin/categories/cat_fresh_fruits/status", json={"status": "published"}
    )
    assert enabled.status_code == 200
    assert "fresh-fruits" in public_slugs()

    # Toggling to the current status is a no-op, not an error.
    repeat = client.patch(
        "/v1/admin/categories/cat_fresh_fruits/status", json={"status": "published"}
    )
    assert repeat.status_code == 200
    assert repeat.json()["changed"] is False

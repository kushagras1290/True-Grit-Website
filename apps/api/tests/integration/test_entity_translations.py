"""Per-locale field overrides for database-sourced content (migration 0068):
navigation labels, category names/descriptions, product names/descriptions,
article/recipe titles/excerpts. One generic admin route group and one public
read-path fallback per entity type -- proven here for navigation (labels
shown on `/v1/public/bootstrap`) and category (shown on `/v1/public/categories`
and `/v1/public/categories/{slug}`), which stand in for the same mechanism
`services.entity_translation.TRANSLATABLE_FIELDS` applies to product, article
and recipe too.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


class FakeTranslator:
    """Deterministic stand-in for Workers AI, matching
    `test_page_translations.FakeTranslator`."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        self.calls.append((text, target_lang))
        return f"[{target_lang}] {text.upper()}"


def test_unknown_entity_type_is_rejected(client, db):
    as_admin(client, db)
    response = client.get("/v1/admin/translations/farm/anything/hi")
    assert response.status_code == 404


def test_a_nav_item_with_no_translation_falls_back_to_english_fields(client, db):
    as_admin(client, db)
    response = client.get("/v1/admin/translations/navigation_item/nit_shop/hi")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["autoTranslated"] is False
    assert body["updatedAt"] is None
    assert body["fields"]["label"] == "Shop"


def test_admin_can_save_and_read_back_a_manual_nav_translation(client, db):
    as_admin(client, db)
    saved = client.put(
        "/v1/admin/translations/navigation_item/nit_shop/hi",
        json={"fields": {"label": "दुकान"}},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["autoTranslated"] is False
    assert saved.json()["fields"]["label"] == "दुकान"

    listed = client.get("/v1/admin/translations/navigation_item/nit_shop").json()["items"]
    assert {k: v for k, v in listed[0].items() if k in {"locale", "autoTranslated"}} == {
        "locale": "hi",
        "autoTranslated": False,
    }

    deleted = client.delete("/v1/admin/translations/navigation_item/nit_shop/hi")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get("/v1/admin/translations/navigation_item/nit_shop").json()["items"] == []


def test_saving_an_unsupported_field_for_the_entity_type_is_rejected(client, db):
    as_admin(client, db)
    response = client.put(
        "/v1/admin/translations/navigation_item/nit_shop/hi",
        # `navigation_item` only supports `label` (services.entity_translation
        # .TRANSLATABLE_FIELDS) -- a category-only field must not silently
        # store on the wrong entity type.
        json={"fields": {"heroTitle": "x"}},
    )
    assert response.status_code == 422


def test_nav_translations_are_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.put(
        "/v1/admin/translations/navigation_item/nit_shop/hi", json={"fields": {"label": "x"}}
    )
    assert response.status_code == 403


def test_auto_translate_is_unavailable_without_a_configured_translator(client, db):
    as_admin(client, db)
    response = client.post("/v1/admin/translations/navigation_item/nit_shop/hi/auto-translate")
    assert response.status_code == 422
    assert "not available in local development" in response.json()["error"]["message"]


def test_auto_translate_populates_every_supported_field_and_flags_the_result(db):
    fake = FakeTranslator()
    app = create_app(db=db, translator=fake)
    client = TestClient(app, raise_server_exceptions=False)
    as_admin(client, db)

    response = client.post("/v1/admin/translations/category/cat_fresh_fruits/hi/auto-translate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["autoTranslated"] is True
    # `category` supports name + short_description + three hero fields
    # (TRANSLATABLE_FIELDS) -- every non-empty one on the seeded row was sent
    # through the translator, nothing more.
    assert body["fields"]["name"].startswith("[hi] ")
    assert len(fake.calls) > 0
    assert all(target == "hi" for _text, target in fake.calls)

    # A second run overwrites the same locale rather than duplicating
    # (PRIMARY KEY (entity_type, entity_id, locale) upsert).
    again = client.post("/v1/admin/translations/category/cat_fresh_fruits/hi/auto-translate")
    assert again.status_code == 200
    listed = client.get("/v1/admin/translations/category/cat_fresh_fruits").json()["items"]
    assert len(listed) == 1


def test_bootstrap_serves_translated_nav_labels_with_english_fallback(client, db):
    as_admin(client, db)
    client.put(
        "/v1/admin/translations/navigation_item/nit_shop/hi", json={"fields": {"label": "दुकान"}}
    )

    hindi = client.get("/v1/public/bootstrap?locale=hi").json()
    shop_item = next(item for item in hindi["navigation"] if item["path"] == "/shop")
    assert shop_item["label"] == "दुकान"
    # A sibling item with no saved translation falls back to English rather
    # than disappearing or rendering blank.
    seasonal_item = next(item for item in hindi["navigation"] if item["path"] == "/seasonal")
    assert seasonal_item["label"] == "Seasonal"

    english = client.get("/v1/public/bootstrap").json()
    english_shop = next(item for item in english["navigation"] if item["path"] == "/shop")
    assert english_shop["label"] == "Shop"


def test_category_endpoints_serve_translated_fields_with_english_fallback(client, db):
    category_id = "cat_catalogue_01"
    as_admin(client, db)
    client.put(
        f"/v1/admin/translations/category/{category_id}/hi",
        json={"fields": {"name": "ताज़े फल", "shortDescription": "मौसमी फल"}},
    )

    listed = client.get("/v1/public/categories?locale=hi").json()["items"]
    translated = next(item for item in listed if item["id"] == category_id)
    assert translated["name"] == "ताज़े फल"
    assert translated["shortDescription"] == "मौसमी फल"

    listed_en = client.get("/v1/public/categories").json()["items"]
    original = next(item for item in listed_en if item["id"] == category_id)
    assert original["name"] != "ताज़े फल"

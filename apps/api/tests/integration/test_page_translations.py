"""Per-locale CMS page content (migration 0067): manual save/get/list/delete
against the shared `client` fixture (no translator configured, matching a
real local/test environment), plus auto-translate against a fake
`Translator` that proves the block-tree walk and the graceful
"not available locally" degradation both work.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.platform.translation import Translator


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


class FakeTranslator:
    """Deterministic stand-in for Workers AI: uppercases the text and tags
    the target language, so a test can assert translation actually ran
    without a real model call."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        self.calls.append((text, target_lang))
        return f"[{target_lang}] {text.upper()}"


def home_page_id(db: SQLiteDatabase) -> str:
    row = db._conn.execute("SELECT id FROM pages WHERE slug = 'home'").fetchone()
    return row["id"]


def test_a_page_with_no_translation_falls_back_to_english(client, db):
    as_admin(client, db)
    page_id = home_page_id(db)
    response = client.get(f"/v1/admin/pages/{page_id}/translations/hi")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["locale"] == "hi"
    assert body["autoTranslated"] is False
    assert body["updatedAt"] is None
    assert len(body["content"]["blocks"]) > 0


def test_admin_can_save_and_read_back_a_manual_translation(client, db):
    as_admin(client, db)
    page_id = home_page_id(db)
    blocks = [
        {
            "id": "blk_hero",
            "type": "hero",
            "version": 1,
            "enabled": True,
            "props": {
                "layout": "editorial-split",
                "eyebrow": "प्रमाणित जैविक",
                "heading": "प्रकृति के अनुसार उगाया गया भोजन।",
                "text": "ताज़ी जैविक उपज।",
                "imageUrl": "/homepage-hero.png",
                "imageAlt": "धूप में जैविक आम",
                "slides": [],
                "primaryAction": {"label": "देखें", "href": "/shop"},
            },
        }
    ]
    saved = client.put(f"/v1/admin/pages/{page_id}/translations/hi", json={"blocks": blocks})
    assert saved.status_code == 200, saved.text
    assert saved.json()["autoTranslated"] is False

    fetched = client.get(f"/v1/admin/pages/{page_id}/translations/hi")
    assert fetched.status_code == 200
    assert fetched.json()["content"]["blocks"][0]["props"]["heading"] == "प्रकृति के अनुसार उगाया गया भोजन।"

    listed = client.get(f"/v1/admin/pages/{page_id}/translations")
    assert listed.status_code == 200
    assert {"locale": "hi", "autoTranslated": False} == {
        k: v for k, v in listed.json()["items"][0].items() if k in {"locale", "autoTranslated"}
    }

    deleted = client.delete(f"/v1/admin/pages/{page_id}/translations/hi")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/v1/admin/pages/{page_id}/translations").json()["items"] == []


def test_saving_a_translation_rejects_an_unknown_block_type(client, db):
    as_admin(client, db)
    page_id = home_page_id(db)
    response = client.put(
        f"/v1/admin/pages/{page_id}/translations/hi",
        json={"blocks": [{"id": "blk_x", "type": "not_a_real_block", "version": 1, "props": {}}]},
    )
    assert response.status_code == 422


def test_translations_are_permission_gated(client, db):
    page_id = home_page_id(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.put(
        f"/v1/admin/pages/{page_id}/translations/hi", json={"blocks": []}
    )
    assert response.status_code == 403


def test_auto_translate_is_unavailable_without_a_configured_translator(client, db):
    """The shared `client` fixture builds the app with no Workers AI
    binding, exactly like local dev -- proving the fallback explains itself
    rather than 500ing."""
    as_admin(client, db)
    page_id = home_page_id(db)
    response = client.post(f"/v1/admin/pages/{page_id}/translations/hi/auto-translate")
    assert response.status_code == 422
    assert "not available in local development" in response.json()["error"]["message"]


def test_auto_translate_walks_the_block_tree_and_flags_the_result(db):
    fake = FakeTranslator()
    app = create_app(db=db, translator=fake)
    client = TestClient(app, raise_server_exceptions=False)
    as_admin(client, db)
    page_id = home_page_id(db)

    response = client.post(f"/v1/admin/pages/{page_id}/translations/hi/auto-translate")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["autoTranslated"] is True

    hero = next(block for block in body["content"]["blocks"] if block["type"] == "hero")
    # Every string under a translatable key (heading, text, a slide's own
    # imageAlt...) went through the translator; ids/types/hrefs did not.
    assert hero["props"]["heading"].startswith("[hi] ")
    assert hero["id"] == "blk_hero"
    assert hero["type"] == "hero"
    assert len(fake.calls) > 0
    assert all(target == "hi" for _text, target in fake.calls)

    # A second run overwrites the same locale rather than erroring or
    # duplicating (PRIMARY KEY (page_id, locale) upsert).
    again = client.post(f"/v1/admin/pages/{page_id}/translations/hi/auto-translate")
    assert again.status_code == 200
    listed = client.get(f"/v1/admin/pages/{page_id}/translations").json()["items"]
    assert len(listed) == 1


def test_auto_translate_is_permission_gated(db):
    app = create_app(db=db, translator=FakeTranslator())
    client = TestClient(app, raise_server_exceptions=False)
    page_id = home_page_id(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))
    response = client.post(f"/v1/admin/pages/{page_id}/translations/hi/auto-translate")
    assert response.status_code == 403

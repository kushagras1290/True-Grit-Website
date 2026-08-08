"""Translation operations and geo-currency controls use the real schema/API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


def as_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def test_currency_rates_are_public_and_admin_edits_are_audited(
    client: TestClient, db: SQLiteDatabase
) -> None:
    public = client.get("/v1/public/currency-rates")
    assert public.status_code == 200, public.text
    usd = next(rate for rate in public.json()["rates"] if rate["currencyCode"] == "USD")
    assert usd["ratePerInr"] == "0.0115"

    as_owner(client, db)
    saved = client.put(
        "/v1/admin/currency-rates/USD",
        json={
            "currencyCode": "USD",
            "locale": "en-US",
            "ratePerInr": "0.012345",
            "active": True,
        },
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["rate"]["ratePerInr"] == "0.012345"

    refreshed = client.get("/v1/public/currency-rates").json()["rates"]
    assert next(rate for rate in refreshed if rate["currencyCode"] == "USD")["ratePerInr"] == (
        "0.012345"
    )
    audit = db._conn.execute(  # test-only inspection
        "SELECT action, actor_user_id FROM audit_logs"
        " WHERE entity_type = 'currency_exchange_rate' AND entity_id = 'USD'"
    ).fetchone()
    assert tuple(audit) == ("currency_rate.updated", "usr_admin")


def test_inr_base_rate_cannot_be_disabled(client: TestClient, db: SQLiteDatabase) -> None:
    as_owner(client, db)
    response = client.put(
        "/v1/admin/currency-rates/INR",
        json={
            "currencyCode": "INR",
            "locale": "en-IN",
            "ratePerInr": "1",
            "active": False,
        },
    )
    assert response.status_code == 422


def test_hub_translation_is_applied_to_public_discussion(
    client: TestClient, db: SQLiteDatabase
) -> None:
    discussion = db._conn.execute(
        "SELECT id, title, body FROM discussions WHERE status = 'visible' LIMIT 1"
    ).fetchone()
    assert discussion is not None
    discussion_id = str(discussion["id"])
    as_owner(client, db)

    detail = client.get(
        f"/v1/admin/translation-hub/resources/discussion/{discussion_id}?locale=hi"
    )
    assert detail.status_code == 200, detail.text
    assert {field["key"] for field in detail.json()["fields"]} >= {"title", "body"}

    translated_title = "अनुवादित चर्चा"
    translated_body = "यह चर्चा अब हिन्दी में उपलब्ध है।"
    saved = client.put(
        f"/v1/admin/translation-hub/resources/discussion/{discussion_id}?locale=hi",
        json={"translations": {"title": translated_title, "body": translated_body}},
    )
    assert saved.status_code == 200, saved.text

    public = client.get(f"/v1/public/community/discussions/{discussion_id}?locale=hi")
    assert public.status_code == 200, public.text
    assert public.json()["title"] == translated_title
    assert public.json()["body"] == translated_body


def test_custom_language_can_be_added_without_a_deployment(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)
    saved = client.put(
        "/v1/admin/translation-hub/locales/eo",
        json={
            "code": "eo",
            "nativeName": "Esperanto",
            "englishName": "Esperanto",
            "direction": "ltr",
            "groupName": "world",
            "active": True,
        },
    )
    assert saved.status_code == 200, saved.text
    public = client.get("/v1/public/locales/custom")
    assert public.status_code == 200
    assert any(locale["code"] == "eo" for locale in public.json()["items"])


def test_announcement_translation_reaches_bootstrap(
    client: TestClient, db: SQLiteDatabase
) -> None:
    announcement = db._conn.execute(
        "SELECT id FROM announcements WHERE country = 'global' LIMIT 1"
    ).fetchone()
    assert announcement is not None
    announcement_id = str(announcement["id"])
    db._conn.execute("UPDATE announcements SET active = 1 WHERE id = ?", (announcement_id,))
    db._conn.commit()
    as_owner(client, db)
    saved = client.put(
        f"/v1/admin/translation-hub/resources/announcement/{announcement_id}?locale=hi",
        json={"translations": {"message": "आज खेत से ताज़ा उपज उपलब्ध है।"}},
    )
    assert saved.status_code == 200, saved.text

    bootstrap = client.get("/v1/public/bootstrap?country=ZZ&locale=hi")
    assert bootstrap.status_code == 200, bootstrap.text
    assert bootstrap.json()["announcement"]["message"] == "आज खेत से ताज़ा उपज उपलब्ध है।"

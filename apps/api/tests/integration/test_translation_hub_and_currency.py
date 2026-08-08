"""Translation operations and geo-currency controls use the real schema/API."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.jobs import dispatch_pending_outbox, process_queue_job
from truegrit_api.services.translation_batches import enqueue_pending_tasks, process_task


class _RecordingPublisher:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, message: dict[str, object]) -> None:
        self.messages.append(message)


class _PrefixTranslator:
    async def translate(self, text: str, *, target_lang: str, source_lang: str = "en") -> str:
        return f"{target_lang}:{text}"


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

    detail = client.get(f"/v1/admin/translation-hub/resources/discussion/{discussion_id}?locale=hi")
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


def test_announcement_translation_reaches_bootstrap(client: TestClient, db: SQLiteDatabase) -> None:
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


def test_new_recipes_discussions_and_farms_appear_without_a_sync_job(
    client: TestClient, db: SQLiteDatabase
) -> None:
    now = "2099-01-01T00:00:00Z"
    db._conn.execute(
        "INSERT INTO farms"
        " (id, name, slug, farmer_name, region, country_code, story_json, methods_json,"
        " seasonal_calendar_json, status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, ?, 'IN', ?, ?, ?, 'published', ?, 'usr_admin', ?, 'usr_admin')",
        (
            "farm_language_live",
            "Live language farm",
            "live-language-farm",
            "Mira Rao",
            "Karnataka",
            '{"headline":"A farm story added today"}',
            '{"soil":"Regenerative soil care"}',
            '{"monsoon":"Greens and herbs"}',
            now,
            now,
        ),
    )
    db._conn.execute(
        "INSERT INTO recipes"
        " (id, internal_name, title, slug, excerpt, status, created_at, created_by, updated_at,"
        " updated_by) VALUES (?, ?, ?, ?, ?, 'published', ?, 'usr_admin', ?, 'usr_admin')",
        (
            "recipe_language_live",
            "live-language-recipe",
            "A newly published recipe",
            "newly-published-language-recipe",
            "New recipe copy should be visible immediately.",
            now,
            now,
        ),
    )
    db._conn.execute(
        "INSERT INTO discussions"
        " (id, author_user_id, title, body, status, last_activity_at, created_at, updated_at)"
        " VALUES (?, 'usr_admin', ?, ?, 'visible', ?, ?, ?)",
        (
            "discussion_language_live",
            "A newly opened discussion",
            "New community content should be visible immediately.",
            now,
            now,
            now,
        ),
    )
    db._conn.commit()
    as_owner(client, db)

    expected = {
        "farm": "farm_language_live",
        "recipe": "recipe_language_live",
        "discussion": "discussion_language_live",
    }
    for resource_type, resource_id in expected.items():
        listing = client.get(
            f"/v1/admin/translation-hub/resources?type={resource_type}&locale=hi&limit=50"
        )
        assert listing.status_code == 200, listing.text
        assert resource_id in {item["id"] for item in listing.json()["items"]}

    farm = client.get("/v1/admin/translation-hub/resources/farm/farm_language_live?locale=hi")
    assert farm.status_code == 200, farm.text
    assert {field["key"] for field in farm.json()["fields"]} >= {
        "farmer_name",
        "story/headline",
        "methods/soil",
        "seasonal_calendar/monsoon",
    }


def test_bulk_batch_translates_selected_text_to_every_requested_language(
    client: TestClient, db: SQLiteDatabase
) -> None:
    discussion = db._conn.execute(
        "SELECT id, title FROM discussions WHERE status = 'visible' LIMIT 1"
    ).fetchone()
    assert discussion is not None
    as_owner(client, db)
    created = client.post(
        "/v1/admin/translation-hub/batches/content",
        json={
            "resourceType": "discussion",
            "resources": [{"resourceId": discussion["id"], "fieldKeys": ["title"]}],
            "locales": ["hi", "fr"],
            "overwriteExisting": False,
        },
    )
    assert created.status_code == 202, created.text
    batch = created.json()
    assert batch["totalTasks"] == 2

    async def run_queue() -> None:
        publisher = _RecordingPublisher()
        assert await enqueue_pending_tasks(db) == 2
        dispatched = await dispatch_pending_outbox(db, publisher)
        assert dispatched["published"] == 2
        translator = _PrefixTranslator()
        for message in publisher.messages:
            await process_queue_job(
                db,
                message,
                translate_task=lambda task_id: process_task(db, translator, task_id),
            )

    asyncio.run(run_queue())
    finished = client.get(f"/v1/admin/translation-hub/batches/{batch['id']}")
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["translatedStrings"] == 2
    for locale in ("hi", "fr"):
        public = client.get(f"/v1/public/community/discussions/{discussion['id']}?locale={locale}")
        assert public.status_code == 200, public.text
        assert public.json()["title"] == f"{locale}:{discussion['title']}"


def test_bulk_batch_translates_selected_interface_text_to_every_requested_language(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)
    entries = {
        "nav.shop": {"source": "Shop", "translation": ""},
        "nav.blog": {"source": "Blog", "translation": ""},
    }
    created = client.post(
        "/v1/admin/translation-hub/batches/interface",
        json={
            "target": "storefront",
            "entries": entries,
            "locales": ["hi", "fr"],
            "overwriteExisting": False,
        },
    )
    assert created.status_code == 202, created.text
    batch = created.json()
    assert batch["totalTasks"] == 2

    async def run_queue() -> None:
        publisher = _RecordingPublisher()
        assert await enqueue_pending_tasks(db) == 2
        dispatched = await dispatch_pending_outbox(db, publisher)
        assert dispatched["published"] == 2
        translator = _PrefixTranslator()
        for message in publisher.messages:
            await process_queue_job(
                db,
                message,
                translate_task=lambda task_id: process_task(db, translator, task_id),
            )

    asyncio.run(run_queue())
    finished = client.get(f"/v1/admin/translation-hub/batches/{batch['id']}")
    assert finished.status_code == 200, finished.text
    assert finished.json()["status"] == "completed"
    assert finished.json()["translatedStrings"] == 4
    for locale in ("hi", "fr"):
        public = client.get(f"/v1/public/translations/interface?locale={locale}&target=storefront")
        assert public.status_code == 200, public.text
        assert public.json()["messages"] == {
            key: f"{locale}:{entry['source']}" for key, entry in entries.items()
        }


def test_select_all_interface_batch_is_materialized_with_backpressure(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)
    entries = {
        f"literal.select_all_{index:04d}": {
            "source": f"Interface source string {index}",
            "translation": "",
        }
        for index in range(926)
    }
    locales = [f"qaa-{index:02d}" for index in range(99)]
    created = client.post(
        "/v1/admin/translation-hub/batches/interface",
        json={
            "target": "storefront",
            "entries": entries,
            "locales": locales,
            "overwriteExisting": False,
        },
    )
    assert created.status_code == 202, created.text
    batch = created.json()
    assert batch["totalTasks"] == 9_207
    assert batch["pendingTasks"] == 9_207
    assert (
        db._conn.execute(
            "SELECT COUNT(*) FROM translation_batch_tasks WHERE batch_id = ?", (batch["id"],)
        ).fetchone()[0]
        == 0
    )

    assert asyncio.run(enqueue_pending_tasks(db)) == 40
    state = db._conn.execute(
        "SELECT generation_cursor, generation_complete FROM translation_batches WHERE id = ?",
        (batch["id"],),
    ).fetchone()
    assert tuple(state) == (40, 0)
    assert (
        db._conn.execute(
            "SELECT COUNT(*) FROM translation_batch_tasks WHERE batch_id = ?", (batch["id"],)
        ).fetchone()[0]
        == 40
    )
    assert (
        db._conn.execute(
            "SELECT COUNT(*) FROM outbox_events WHERE aggregate_id = ?", (batch["id"],)
        ).fetchone()[0]
        == 40
    )

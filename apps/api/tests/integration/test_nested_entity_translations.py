from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from truegrit_api.platform.database import SQLiteDatabase


def save_generated_fields(
    db: SQLiteDatabase, entity_type: str, entity_id: str, fields: dict[str, object]
) -> None:
    asyncio.run(
        db.execute(
            "INSERT OR REPLACE INTO entity_translations"
            " (entity_type, entity_id, locale, fields_json, auto_translated,"
            " updated_at, updated_by)"
            " VALUES (?, ?, 'hi', ?, 1, '2026-01-01T00:00:00Z', 'usr_admin')",
            (entity_type, entity_id, json.dumps(fields)),
        )
    )


def test_public_details_use_generated_nested_content_translations(
    client: TestClient, db: SQLiteDatabase
) -> None:
    article = asyncio.run(
        db.fetch_one("SELECT id, slug FROM articles WHERE status = 'published' LIMIT 1")
    )
    assert article is not None
    save_generated_fields(
        db,
        "article",
        article["id"],
        {
            "title": "हिन्दी लेख",
            "content": {
                "blocks": [
                    {
                        "id": "translated",
                        "type": "rich_text",
                        "version": 1,
                        "enabled": True,
                        "props": {"heading": "उपयोगी मार्गदर्शिका", "paragraphs": ["पूरा अनुवाद"]},
                    }
                ]
            },
        },
    )
    article_response = client.get(f"/v1/public/articles/{article['slug']}?locale=hi")
    assert article_response.status_code == 200
    assert article_response.json()["title"] == "हिन्दी लेख"
    assert article_response.json()["blocks"][0]["props"]["paragraphs"] == ["पूरा अनुवाद"]

    farm = asyncio.run(
        db.fetch_one("SELECT id, slug FROM farms WHERE status = 'published' LIMIT 1")
    )
    assert farm is not None
    save_generated_fields(
        db,
        "farm",
        farm["id"],
        {
            "story_content": {"summary": "हिन्दी सार", "body": "हिन्दी कहानी"},
            "methods": ["जैविक खेती"],
        },
    )
    farm_response = client.get(f"/v1/public/farms/{farm['slug']}?locale=hi")
    assert farm_response.status_code == 200
    assert farm_response.json()["story"] == "हिन्दी कहानी"
    assert farm_response.json()["methods"] == ["जैविक खेती"]

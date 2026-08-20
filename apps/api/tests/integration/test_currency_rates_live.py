"""Live currency-rate refresh and the Google Sheets manual-tuning round trip.

Both talk to the outside world (a live rate API, Google's OAuth/Sheets
endpoints), so every test here monkeypatches the outbound call at the module
boundary (`platform.http`/`platform.google_sheets`) rather than reaching a
real network -- the same approach `test_paypal.py` uses for PayPal's API.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.config import get_settings
from truegrit_api.platform.database import SQLiteDatabase


def as_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def test_refresh_now_updates_only_currencies_already_in_the_table(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_get_json(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
        assert "open.er-api.com" in url
        return {
            "result": "success",
            "base_code": "INR",
            "rates": {
                "INR": 1,
                "USD": 0.0117,  # known currency -- should update
                "XYZ": 0.5,  # unknown currency -- must never be auto-created
            },
        }

    monkeypatch.setattr("truegrit_api.services.currency_rates.get_json_async", fake_get_json)
    as_owner(client, db)

    response = client.post("/v1/admin/currency-rates/refresh")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["updatedCount"] == 1
    assert body["result"]["currencies"] == ["USD"]

    usd = next(rate for rate in body["rates"] if rate["currencyCode"] == "USD")
    assert usd["ratePerInr"] == "0.0117"
    inr = next(rate for rate in body["rates"] if rate["currencyCode"] == "INR")
    assert inr["ratePerInr"] == "1"  # INR the base currency is never touched
    assert not any(rate["currencyCode"] == "XYZ" for rate in body["rates"])

    audit = db._conn.execute(  # test-only inspection
        "SELECT action, actor_user_id FROM audit_logs WHERE action = 'currency_rates.live_synced'"
    ).fetchone()
    assert tuple(audit) == ("currency_rates.live_synced", "usr_admin")


def test_refresh_now_requires_a_session(client: TestClient) -> None:
    response = client.post("/v1/admin/currency-rates/refresh")
    assert response.status_code == 401


def test_refresh_now_reports_a_clean_error_when_the_source_is_unreachable(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    from truegrit_api.platform.http import HttpError

    async def fake_get_json(url: str, *, headers: dict[str, str] | None = None) -> Any:
        raise HttpError("boom")

    monkeypatch.setattr("truegrit_api.services.currency_rates.get_json_async", fake_get_json)
    as_owner(client, db)

    response = client.post("/v1/admin/currency-rates/refresh")
    assert response.status_code == 422


def test_sheet_routes_refuse_when_google_sheets_is_not_configured(
    client: TestClient, db: SQLiteDatabase
) -> None:
    as_owner(client, db)

    push = client.post("/v1/admin/currency-rates/push-to-sheet")
    assert push.status_code == 422, push.text

    sync = client.post("/v1/admin/currency-rates/sync-from-sheet")
    assert sync.status_code == 422, sync.text


def test_push_to_sheet_writes_header_and_data_blocks(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    writes: list[dict[str, Any]] = []

    async def fake_write_values(settings: Any, *, cell_range: str, values: list[list[Any]]) -> None:
        writes.append({"range": cell_range, "values": values})

    monkeypatch.setattr(
        "truegrit_api.services.currency_rates.google_sheets.write_values", fake_write_values
    )
    monkeypatch.setattr(
        "truegrit_api.api.currency_rates.get_settings",
        lambda: _configured_settings(),
    )
    as_owner(client, db)

    response = client.post("/v1/admin/currency-rates/push-to-sheet")
    assert response.status_code == 200, response.text
    assert response.json()["result"]["pushedCount"] > 0

    header_write = next(w for w in writes if w["range"] == "A1:D4")
    assert header_write["values"][0][0] == "Source:"
    assert "open.er-api.com" in header_write["values"][0][1]
    assert header_write["values"][3] == ["Currency Code", "Locale", "Rate per INR", "Active"]

    data_write = next(w for w in writes if w["range"] != "A1:D4")
    codes = [row[0] for row in data_write["values"]]
    assert "INR" in codes
    assert "USD" in codes


def test_sync_from_sheet_updates_known_currencies_and_skips_the_rest(
    client: TestClient, db: SQLiteDatabase, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_read_values(settings: Any, *, cell_range: str) -> list[list[str]]:
        assert cell_range == "A5:D500"
        return [
            ["USD", "en-US", "0.0130", "TRUE"],
            ["INR", "en-IN", "1", "TRUE"],  # must be skipped -- INR is the fixed base
            ["ZZZ", "en-ZZ", "2.5", "TRUE"],  # unknown currency -- must be skipped
            ["", "", "", ""],  # blank row -- must be skipped without failing the sync
            ["GBP", "en-GB", "not-a-number", "TRUE"],  # malformed rate -- must be skipped
        ]

    monkeypatch.setattr(
        "truegrit_api.services.currency_rates.google_sheets.read_values", fake_read_values
    )
    monkeypatch.setattr(
        "truegrit_api.api.currency_rates.get_settings",
        lambda: _configured_settings(),
    )
    as_owner(client, db)

    response = client.post("/v1/admin/currency-rates/sync-from-sheet")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["result"]["updatedCount"] == 1
    assert body["result"]["skippedCount"] == 3

    usd = next(rate for rate in body["rates"] if rate["currencyCode"] == "USD")
    assert usd["ratePerInr"] == "0.013"
    inr = next(rate for rate in body["rates"] if rate["currencyCode"] == "INR")
    assert inr["ratePerInr"] == "1"


def _configured_settings() -> Any:
    settings = get_settings()
    fake_pem = "-----BEGIN PRIVATE KEY-----\ntest\n-----END PRIVATE KEY-----"
    return settings.model_copy(
        update={
            "google_sheets_client_email": "svc@example.test",
            "google_sheets_private_key": fake_pem,
            "google_sheets_spreadsheet_id": "sheet_test_123",
        }
    )

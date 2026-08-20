"""Integration tests for the SEO agent's operator API.

The crawler itself is a separate TypeScript Worker and is not exercised here
(`apps/seo/worker/*.test.ts` covers it against fixtures). What this file
exercises is the Python side: reading what a crawl would have written, and
applying proposals against the real, migrated schema.

The apply/revert path is the one worth the most attention, because it is a
direct UPDATE against live catalogue rows. The properties under test are
security properties before they are feature properties: a proposal can never
target a column its table lacks, a revert restores what was actually there
rather than a stale snapshot, and a bulk apply reports partial failure rather
than losing it silently.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase

NOW = "2026-08-19T00:00:00Z"


def _client(db: SQLiteDatabase) -> TestClient:
    return TestClient(create_app(db=db), raise_server_exceptions=False)


def _staff(db: SQLiteDatabase, user_id: str = "usr_admin") -> TestClient:
    client = _client(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))
    return client


def _seed_run(db: SQLiteDatabase, run_id: str = "seorun_1", status: str = "completed") -> None:
    # A test may seed more than one finding/proposal against the same run, so
    # this has to be idempotent rather than assume it is the first call.
    db._conn.execute(
        "INSERT OR IGNORE INTO seo_crawl_runs (id, status, trigger, base_url, queued_at,"
        " finished_at, pages_discovered, pages_crawled) VALUES (?, ?, 'cron',"
        " 'https://test.truegritin.com', ?, ?, 10, 10)",
        (run_id, status, NOW, NOW),
    )
    db._conn.commit()


def _seed_finding(db: SQLiteDatabase, **overrides: Any) -> str:
    _seed_run(db)
    values = {
        "id": "seofnd_1",
        "fingerprint": "missing_product_schema::/product/x",
        "rule": "missing_product_schema",
        "category": "schema",
        "severity": "high",
        "path": "/product/x",
        "page_type": "product",
        "summary": "No Product structured data",
        "detail": "detail",
        "fix_hint": "add schema",
        "status": "open",
        "first_seen_run_id": "seorun_1",
        "last_seen_run_id": "seorun_1",
        "first_seen_at": NOW,
        "last_seen_at": NOW,
        **overrides,
    }
    db._conn.execute(
        "INSERT INTO seo_findings (id, fingerprint, rule, category, severity, path, page_type,"
        " summary, detail, fix_hint, status, first_seen_run_id, last_seen_run_id,"
        " first_seen_at, last_seen_at) VALUES (:id, :fingerprint, :rule, :category, :severity,"
        " :path, :page_type, :summary, :detail, :fix_hint, :status, :first_seen_run_id,"
        " :last_seen_run_id, :first_seen_at, :last_seen_at)",
        values,
    )
    db._conn.commit()
    return str(values["id"])


def _seed_proposal(db: SQLiteDatabase, *, reset_entity: bool = True, **overrides: Any) -> str:
    """A pending proposal against a real seed product.

    The seed catalogue already ships a non-blank `seo_title` for this product
    (`database/seeds/development.sql`), so by default the target field is
    cleared first -- the test's starting state is then a fact this file
    asserts, not an accident of the fixtures. Pass `reset_entity=False` when a
    test needs to control the field's value itself before calling this (see
    the revert test, which edits it *between* proposal creation and apply).
    """
    _seed_run(db)
    if reset_entity and overrides.get("entity_id", "prd_catalogue_01") == "prd_catalogue_01":
        db._conn.execute("UPDATE products SET seo_title = '' WHERE id = 'prd_catalogue_01'")
        db._conn.commit()
    values = {
        "id": "seoprp_1",
        "run_id": "seorun_1",
        "entity_type": "product",
        "entity_id": "prd_catalogue_01",
        "entity_label": "Kathiya Wheat Flour",
        "path": "/product/kathiya-wheat-flour",
        "field": "seo_title",
        "current_value": "",
        "proposed_value": "Kathiya Wheat Flour | stone ground | True Grit",
        "rationale": "No SEO title is set.",
        "source": "gap",
        "source_ref": "stone ground",
        "confidence": 0.9,
        "status": "pending",
        "created_at": NOW,
        **overrides,
    }
    db._conn.execute(
        "INSERT INTO seo_proposals (id, run_id, entity_type, entity_id, entity_label, path,"
        " field, current_value, proposed_value, rationale, source, source_ref, confidence,"
        " status, created_at) VALUES (:id, :run_id, :entity_type, :entity_id, :entity_label,"
        " :path, :field, :current_value, :proposed_value, :rationale, :source, :source_ref,"
        " :confidence, :status, :created_at)",
        values,
    )
    db._conn.commit()
    return str(values["id"])


def _enable(db: SQLiteDatabase) -> None:
    db._conn.execute("UPDATE app_settings SET value = 'true' WHERE key = 'seo.enabled'")
    db._conn.commit()


# --- Authorisation -----------------------------------------------------------


def test_summary_requires_seo_manage(db: SQLiteDatabase):
    assert _client(db).get("/v1/admin/seo/summary").status_code == 401


def test_summary_is_reachable_by_a_staff_member_with_the_permission(db: SQLiteDatabase):
    response = _staff(db).get("/v1/admin/seo/summary")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["settings"]["enabled"] is False
    assert body["counts"]["pendingProposals"] == 0


# --- Runs ---------------------------------------------------------------------


def test_queueing_a_run_requires_the_feature_to_be_enabled(db: SQLiteDatabase):
    response = _staff(db).post("/v1/admin/seo/runs")
    assert response.status_code == 422
    assert "switched off" in response.json()["error"]["message"]


def test_queueing_a_run_when_enabled(db: SQLiteDatabase):
    _enable(db)
    response = _staff(db).post("/v1/admin/seo/runs")
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "queued"


def test_a_second_run_cannot_be_queued_while_one_is_pending(db: SQLiteDatabase):
    _enable(db)
    staff = _staff(db)
    first = staff.post("/v1/admin/seo/runs")
    assert first.status_code == 200
    second = staff.post("/v1/admin/seo/runs")
    assert second.status_code == 409


# --- Settings -------------------------------------------------------------------


def test_schedule_days_defaults_to_daily(db: SQLiteDatabase):
    response = _staff(db).get("/v1/admin/seo/summary")
    assert response.status_code == 200
    assert response.json()["settings"]["scheduleDays"] == 1


def test_updating_schedule_days_leaves_enabled_switch_untouched(db: SQLiteDatabase):
    _enable(db)
    staff = _staff(db)
    response = staff.patch("/v1/admin/seo/settings", json={"scheduleDays": 7})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["scheduleDays"] == 7
    assert body["enabled"] is True  # untouched by a schedule-only PATCH

    summary = staff.get("/v1/admin/seo/summary").json()
    assert summary["settings"]["scheduleDays"] == 7
    assert summary["settings"]["enabled"] is True


def test_updating_enabled_leaves_schedule_days_untouched(db: SQLiteDatabase):
    staff = _staff(db)
    staff.patch("/v1/admin/seo/settings", json={"scheduleDays": 3})
    response = staff.patch("/v1/admin/seo/settings", json={"enabled": True})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["enabled"] is True
    assert body["scheduleDays"] == 3  # untouched by an enabled-only PATCH


def test_schedule_days_rejects_an_arbitrary_value(db: SQLiteDatabase):
    response = _staff(db).patch("/v1/admin/seo/settings", json={"scheduleDays": 2})
    assert response.status_code == 422


# --- Findings -----------------------------------------------------------------


def test_findings_default_to_open_worst_first(db: SQLiteDatabase):
    _seed_finding(db, id="seofnd_low", rule="h1_multiple", severity="low", fingerprint="a")
    _seed_finding(
        db, id="seofnd_critical", rule="noindex_in_sitemap", severity="critical", fingerprint="b"
    )

    response = _staff(db).get("/v1/admin/seo/findings")
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert items[0]["severity"] == "critical"
    assert items[1]["severity"] == "low"


def test_marking_a_finding_ignored_removes_it_from_the_open_queue(db: SQLiteDatabase):
    finding_id = _seed_finding(db)
    staff = _staff(db)

    updated = staff.patch(f"/v1/admin/seo/findings/{finding_id}", json={"status": "ignored"})
    assert updated.status_code == 200, updated.text

    assert staff.get("/v1/admin/seo/findings").json()["total"] == 0
    ignored = staff.get("/v1/admin/seo/findings?status=ignored").json()
    assert ignored["total"] == 1


# --- Competitors ----------------------------------------------------------


def test_adding_a_competitor_normalises_to_its_origin(db: SQLiteDatabase):
    response = _staff(db).post(
        "/v1/admin/seo/competitors",
        json={"label": "Rival Foods", "origin": "https://rival.example.com/some/deep/page"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["origin"] == "https://rival.example.com"


def test_adding_a_competitor_twice_conflicts(db: SQLiteDatabase):
    staff = _staff(db)
    staff.post(
        "/v1/admin/seo/competitors", json={"label": "Rival", "origin": "https://rival.example.com"}
    )
    second = staff.post(
        "/v1/admin/seo/competitors",
        json={"label": "Rival Again", "origin": "https://rival.example.com"},
    )
    assert second.status_code == 409


def test_rejects_a_non_http_origin(db: SQLiteDatabase):
    response = _staff(db).post(
        "/v1/admin/seo/competitors", json={"label": "Bad", "origin": "not-a-url"}
    )
    assert response.status_code == 422


# --- Proposals: the security-critical path ------------------------------------


def test_applying_a_proposal_writes_the_field_and_records_the_prior_value(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db)
    staff = _staff(db)

    response = staff.post(f"/v1/admin/seo/proposals/{proposal_id}/apply")
    assert response.status_code == 200, response.text
    assert response.json()["previousValue"] == ""

    row = db._conn.execute(
        "SELECT seo_title FROM products WHERE id = 'prd_catalogue_01'"
    ).fetchone()
    assert row["seo_title"] == "Kathiya Wheat Flour | stone ground | True Grit"


def test_a_proposal_cannot_be_applied_twice(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db)
    staff = _staff(db)
    staff.post(f"/v1/admin/seo/proposals/{proposal_id}/apply")

    second = staff.post(f"/v1/admin/seo/proposals/{proposal_id}/apply")
    assert second.status_code == 409


def test_a_proposal_naming_a_column_its_table_does_not_have_is_refused(db: SQLiteDatabase):
    """products has no seo_keywords column. A proposal claiming otherwise --
    whatever produced it -- must be refused rather than reaching raw SQL."""
    proposal_id = _seed_proposal(db, id="seoprp_bad", field="seo_keywords", proposed_value="x")
    response = _staff(db).post(f"/v1/admin/seo/proposals/{proposal_id}/apply")
    assert response.status_code == 422
    assert "no seo_keywords field" in response.json()["error"]["message"]

    # Nothing was written and the proposal is still pending.
    pending = db._conn.execute(
        "SELECT status FROM seo_proposals WHERE id = 'seoprp_bad'"
    ).fetchone()
    assert pending["status"] == "pending"


def test_applying_a_proposal_for_a_deleted_entity_fails_cleanly(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db, entity_id="prd_does_not_exist")
    response = _staff(db).post(f"/v1/admin/seo/proposals/{proposal_id}/apply")
    assert response.status_code == 404


def test_revert_restores_what_was_actually_there_not_a_stale_snapshot(db: SQLiteDatabase):
    """The field changes again after the proposal was generated but before it
    is applied. A revert must restore the real prior value, not whatever
    `current_value` said when the crawl ran."""
    proposal_id = _seed_proposal(db, current_value="")  # stale: crawl saw it blank

    db._conn.execute(
        "UPDATE products SET seo_title = 'Edited after the crawl' WHERE id = 'prd_catalogue_01'"
    )
    db._conn.commit()

    staff = _staff(db)
    staff.post(f"/v1/admin/seo/proposals/{proposal_id}/apply")

    reverted = staff.post(f"/v1/admin/seo/proposals/{proposal_id}/revert")
    assert reverted.status_code == 200, reverted.text

    row = db._conn.execute(
        "SELECT seo_title FROM products WHERE id = 'prd_catalogue_01'"
    ).fetchone()
    assert row["seo_title"] == "Edited after the crawl"


def test_only_an_applied_proposal_can_be_reverted(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db)
    response = _staff(db).post(f"/v1/admin/seo/proposals/{proposal_id}/revert")
    assert response.status_code == 409


def test_rejecting_a_proposal_leaves_the_entity_untouched(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db)
    staff = _staff(db)

    response = staff.post(f"/v1/admin/seo/proposals/{proposal_id}/reject")
    assert response.status_code == 200, response.text

    row = db._conn.execute(
        "SELECT seo_title FROM products WHERE id = 'prd_catalogue_01'"
    ).fetchone()
    assert row["seo_title"] == ""


def test_bulk_apply_reports_partial_failure_without_losing_the_good_ones(db: SQLiteDatabase):
    good = _seed_proposal(db, id="seoprp_good")
    bad = _seed_proposal(
        db,
        id="seoprp_bad",
        entity_id="prd_does_not_exist",
        field="seo_description",
        proposed_value="x",
    )

    response = _staff(db).post("/v1/admin/seo/proposals/apply", json={})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["applied"] == 1
    assert body["failed"][0]["id"] == bad

    row = db._conn.execute(
        "SELECT seo_title FROM products WHERE id = 'prd_catalogue_01'"
    ).fetchone()
    assert row["seo_title"] != ""
    assert good  # applied; asserted via the row above


def test_indexing_policy_proposal_is_applied_and_visible_to_the_storefront(db: SQLiteDatabase):
    """The point of this whole feature: an indexing contradiction the crawl
    found becomes a real change the storefront serves, with no deploy."""
    proposal_id = _seed_proposal(
        db,
        field="indexing_policy",
        current_value="noindex",
        proposed_value="index",
        source="finding",
        source_ref="noindex_in_sitemap",
    )
    db._conn.execute(
        "UPDATE products SET indexing_policy = 'noindex' WHERE id = 'prd_catalogue_01'"
    )
    db._conn.commit()

    response = _staff(db).post(f"/v1/admin/seo/proposals/{proposal_id}/apply")
    assert response.status_code == 200, response.text

    row = db._conn.execute(
        "SELECT indexing_policy FROM products WHERE id = 'prd_catalogue_01'"
    ).fetchone()
    assert row["indexing_policy"] == "index"


def test_applying_a_proposal_is_audited(db: SQLiteDatabase):
    proposal_id = _seed_proposal(db)
    _staff(db).post(f"/v1/admin/seo/proposals/{proposal_id}/apply")

    entry = db._conn.execute(
        "SELECT action, entity_id FROM audit_logs WHERE action = 'seo.proposal_applied'"
    ).fetchone()
    assert entry is not None
    assert entry["entity_id"] == "prd_catalogue_01"

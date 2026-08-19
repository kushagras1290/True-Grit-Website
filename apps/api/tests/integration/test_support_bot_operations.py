"""Operator surface for the deterministic bot: policy facts and the escalation
queue.

The behaviour worth pinning here is the loop that makes the bot improvable: a
customer asks something it cannot place, that becomes a row, and an operator
can see both the message and what the classifier nearly matched. Without the
`alternatives` payload the queue would say only that something failed, which
tells nobody what to change.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.main import create_app
from truegrit_api.platform.database import SQLiteDatabase


def _client(db: SQLiteDatabase) -> TestClient:
    return TestClient(create_app(db=db), raise_server_exceptions=False)


def _staff(db: SQLiteDatabase) -> TestClient:
    client = _client(db)
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))
    return client


def _ask(client: TestClient, message: str) -> dict[str, Any]:
    response = client.post("/v1/public/support-bot/chat", json={"message": message})
    assert response.status_code == 200, response.text
    return response.json()


# --- Policy facts -----------------------------------------------------------


def test_policy_facts_are_seeded_blank_and_flagged_unconfigured(db: SQLiteDatabase):
    response = _staff(db).get("/v1/admin/support-bot/policy-facts")
    assert response.status_code == 200, response.text
    facts = response.json()

    assert {fact["key"] for fact in facts} >= {
        "return_window_days",
        "refund_processing_days",
        "support_email",
    }
    assert all(fact["value"] == "" for fact in facts)
    assert all(fact["isConfigured"] is False for fact in facts)
    # Every fact carries an operator-readable label and hint, so the screen does
    # not need its own copy of what each one means.
    assert all(fact["label"] for fact in facts)


def test_setting_a_fact_switches_on_the_wording_that_needs_it(db: SQLiteDatabase):
    before = _ask(_client(db), "what is your return policy")
    assert "days of delivery" not in before["reply"]

    updated = _staff(db).patch(
        "/v1/admin/support-bot/policy-facts/return_window_days", json={"value": "10"}
    )
    assert updated.status_code == 200, updated.text
    assert updated.json() == {"key": "return_window_days", "value": "10", "isConfigured": True}

    after = _ask(_client(db), "what is your return policy")
    assert "10 days of delivery" in after["reply"]


def test_blanking_a_fact_switches_the_wording_back_off(db: SQLiteDatabase):
    staff = _staff(db)
    staff.patch("/v1/admin/support-bot/policy-facts/return_window_days", json={"value": "10"})
    staff.patch("/v1/admin/support-bot/policy-facts/return_window_days", json={"value": ""})

    reply = _ask(_client(db), "what is your return policy")["reply"]
    assert "10 days" not in reply
    assert "/returns" in reply


def test_unknown_fact_key_is_rejected(db: SQLiteDatabase):
    """Keys come from the migration. An arbitrary one would be data no template
    reads."""
    response = _staff(db).patch(
        "/v1/admin/support-bot/policy-facts/made_up_key", json={"value": "x"}
    )
    assert response.status_code == 404


def test_policy_facts_require_the_manage_permission(db: SQLiteDatabase):
    assert _client(db).get("/v1/admin/support-bot/policy-facts").status_code == 401


# --- Escalation queue -------------------------------------------------------


def test_escalation_queue_records_what_the_classifier_nearly_matched(db: SQLiteDatabase):
    _ask(_client(db), "can you explain the offside rule in football to me")

    response = _staff(db).get("/v1/admin/support-bot/escalations")
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["total"] == 1
    item = body["items"][0]
    assert item["reason"] == "low_confidence"
    assert item["message"].startswith("can you explain the offside")
    assert isinstance(item["alternatives"], list)
    assert item["status"] == "open"


def test_queue_is_ordered_worst_first(db: SQLiteDatabase):
    """A food-safety report must not sit behind a page of delivery questions."""
    public = _client(db)
    _ask(public, "what is the airspeed velocity of an unladen swallow")
    _ask(public, "i ate your flour and ended up in hospital")
    _ask(public, "i want to speak to a human")

    items = _staff(db).get("/v1/admin/support-bot/escalations").json()["items"]
    assert items[0]["severity"] == "critical"
    assert items[0]["intent"] == "safety_food"


def test_queue_can_be_filtered_by_severity(db: SQLiteDatabase):
    public = _client(db)
    _ask(public, "i ate your flour and ended up in hospital")
    _ask(public, "what is the airspeed velocity of an unladen swallow")

    critical = _staff(db).get("/v1/admin/support-bot/escalations?severity=critical").json()
    assert critical["total"] == 1
    assert critical["items"][0]["intent"] == "safety_food"


def test_resolving_an_escalation_removes_it_from_the_open_queue(db: SQLiteDatabase):
    _ask(_client(db), "can you explain the offside rule in football to me")
    staff = _staff(db)
    escalation_id = staff.get("/v1/admin/support-bot/escalations").json()["items"][0]["id"]

    resolved = staff.patch(
        f"/v1/admin/support-bot/escalations/{escalation_id}",
        json={"status": "resolved", "note": "Replied by email."},
    )
    assert resolved.status_code == 200, resolved.text

    assert staff.get("/v1/admin/support-bot/escalations").json()["total"] == 0
    closed = staff.get("/v1/admin/support-bot/escalations?status=resolved").json()
    assert closed["total"] == 1
    assert closed["items"][0]["resolutionNote"] == "Replied by email."
    assert closed["items"][0]["resolvedAt"]


def test_summary_reports_which_intents_keep_escalating(db: SQLiteDatabase):
    """The report an operator acts on: a high count at low confidence is a
    phrasebook gap, a high count at high confidence is policy working."""
    public = _client(db)
    for message in ("i want to speak to a human", "get me a real person", "connect me to an agent"):
        _ask(public, message)
    _ask(public, "what is the airspeed velocity of an unladen swallow")

    summary = _staff(db).get("/v1/admin/support-bot/escalations/summary").json()
    by_intent = {row["intent"]: row for row in summary}

    assert by_intent["human_handoff"]["count"] == 3
    assert by_intent["human_handoff"]["reason"] == "policy"
    assert by_intent["human_handoff"]["averageConfidence"] >= 0.9


def test_unknown_escalation_id_is_a_404(db: SQLiteDatabase):
    response = _staff(db).patch(
        "/v1/admin/support-bot/escalations/sbe_missing", json={"status": "resolved"}
    )
    assert response.status_code == 404


def test_escalation_queue_requires_the_manage_permission(db: SQLiteDatabase):
    assert _client(db).get("/v1/admin/support-bot/escalations").status_code == 401

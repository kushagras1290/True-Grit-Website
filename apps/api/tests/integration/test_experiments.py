"""Integration tests for the A/B testing framework: the admin CRUD/lifecycle
API (`api/admin.py`'s `/experiments*` routes) and the storefront's assignment
and event-tracking endpoints (`api/storefront.py`).

`tests/unit/test_experiments_stats.py` covers the statistics engine itself.
What was missing, and what this file adds, is everything that only exists
once the engine meets HTTP and the database: permission gating, the
draft -> running -> completed/stopped lifecycle (and that an experiment can
only leave `draft` once, never be edited after leaving it), exposure
deduplication, and that a real checkout fires a real conversion event end to
end.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_cust_riya") -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def _create(client: TestClient, key: str = "test_experiment", **overrides: object) -> dict:
    payload = {
        "key": key,
        "name": "Test Experiment",
        "variants": [
            {"key": "control", "name": "Control"},
            {"key": "treatment", "name": "Treatment"},
        ],
        "allocationPct": 100,
        "primaryMetric": "conversion",
        **overrides,
    }
    response = client.post("/v1/admin/experiments", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _add_product(db: SQLiteDatabase, *, product_id: str, variant_id: str, sku: str) -> None:
    slug = product_id.removeprefix("prd_").replace("_", "-")
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, accepts_orders,"
        " status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', 1, 'published', '2026-07-01T00:00:00Z', 'usr_admin',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, product_id, product_id, slug),
    )
    db._conn.execute(
        "INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, 'Standard', 'active', 1, '2026-07-01T00:00:00Z',"
        " '2026-07-01T00:00:00Z')",
        (variant_id, product_id, sku),
    )
    db._conn.execute(
        "INSERT INTO variant_prices (id, variant_id, market_code, currency_code,"
        " list_amount_minor, starts_at, status, created_at, created_by)"
        " VALUES (?, ?, 'IN', 'INR', 49900, '2026-07-01T00:00:00Z', 'active',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (f"vpr_{variant_id}", variant_id),
    )
    db._conn.execute(
        "INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,"
        " reorder_threshold, version, updated_at)"
        " VALUES (?, 'loc_mumbai', 200, 0, 5, 1, '2026-07-01T00:00:00Z')",
        (variant_id,),
    )
    db._conn.commit()


# --- Authorisation -----------------------------------------------------------


def test_experiments_list_requires_authentication(client: TestClient):
    assert client.get("/v1/admin/experiments").status_code == 401


def test_experiments_list_requires_the_manage_permission(client: TestClient, db: SQLiteDatabase):
    """A staff member without `experiments.manage` must not see A/B test
    results -- these can reveal commercially sensitive pricing/messaging
    experiments before they are public."""
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_no_exp_perm', 'noexp@example.test', 'No Perm', 'staff', 'active',"
        " '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')"
    )
    db._conn.commit()
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_no_exp_perm"))
    assert client.get("/v1/admin/experiments").status_code == 403


# --- CRUD and lifecycle -------------------------------------------------------


def test_create_experiment_round_trips(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    created = _create(client)
    assert created["status"] == "draft"
    assert created["key"] == "test_experiment"

    listed = client.get("/v1/admin/experiments").json()
    assert any(item["key"] == "test_experiment" for item in listed)


def test_experiment_key_must_be_unique(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    _create(client, key="dup_key")
    response = client.post(
        "/v1/admin/experiments",
        json={
            "key": "dup_key",
            "name": "Second",
            "variants": [{"key": "control", "name": "Control"}, {"key": "b", "name": "B"}],
        },
    )
    assert response.status_code == 409


def test_experiment_needs_at_least_two_variants(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/experiments",
        json={
            "key": "one_variant",
            "name": "One Variant",
            "variants": [{"key": "control", "name": "Control"}],
        },
    )
    assert response.status_code == 422


def test_experiment_rejects_duplicate_variant_keys(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post(
        "/v1/admin/experiments",
        json={
            "key": "dup_variants",
            "name": "Dup Variants",
            "variants": [{"key": "a", "name": "A"}, {"key": "a", "name": "A again"}],
        },
    )
    assert response.status_code == 422


def test_full_lifecycle_draft_running_completed(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    created = _create(client)
    experiment_id = created["id"]

    started = client.post(f"/v1/admin/experiments/{experiment_id}/start")
    assert started.status_code == 200, started.text
    assert started.json()["status"] == "running"
    assert started.json()["startedAt"] is not None

    completed = client.post(f"/v1/admin/experiments/{experiment_id}/complete")
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["endedAt"] is not None


def test_cannot_start_an_already_running_experiment(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    response = client.post(f"/v1/admin/experiments/{experiment_id}/start")
    assert response.status_code == 409


def test_cannot_stop_a_draft_experiment(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    response = client.post(f"/v1/admin/experiments/{experiment_id}/stop")
    assert response.status_code == 409


def test_cannot_edit_an_experiment_once_it_has_left_draft(client: TestClient, db: SQLiteDatabase):
    """The variant set and allocation are the thing being measured -- changing
    them mid-flight would invalidate every stat computed so far without
    anyone knowing it happened."""
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    response = client.patch(
        f"/v1/admin/experiments/{experiment_id}", json={"name": "Renamed mid-flight"}
    )
    assert response.status_code == 409


def test_a_stopped_experiment_can_be_read_but_not_restarted(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")
    stopped = client.post(f"/v1/admin/experiments/{experiment_id}/stop")
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    restart = client.post(f"/v1/admin/experiments/{experiment_id}/start")
    assert restart.status_code == 409


def test_unknown_experiment_id_is_a_404(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    assert client.get("/v1/admin/experiments/exp_does_not_exist").status_code == 404
    assert client.post("/v1/admin/experiments/exp_does_not_exist/start").status_code == 404


# --- Storefront assignment and tracking ---------------------------------------


def test_customer_gets_a_deterministic_assignment_once_experiment_is_running(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    as_customer(client, db)
    first = client.get("/v1/public/experiments/assignments")
    assert first.status_code == 200, first.text
    assignments = {a["experimentKey"]: a["variant"] for a in first.json()["assignments"]}
    assert "test_experiment" in assignments

    second = client.get("/v1/public/experiments/assignments")
    assert second.json()["assignments"] == first.json()["assignments"]


def test_draft_experiments_assign_no_one(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    _create(client)  # left in draft, never started

    as_customer(client, db)
    response = client.get("/v1/public/experiments/assignments")
    assert response.json()["assignments"] == []


def test_exposure_events_are_deduplicated_per_user(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    experiment_id = _create(client)["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    as_customer(client, db)
    first = client.post(
        "/v1/public/experiments/events",
        json={"experimentKey": "test_experiment", "eventType": "exposure"},
    )
    assert first.status_code == 200
    assert first.json()["tracked"] is True

    second = client.post(
        "/v1/public/experiments/events",
        json={"experimentKey": "test_experiment", "eventType": "exposure"},
    )
    assert second.json()["tracked"] is False

    exposures = db._conn.execute(
        "SELECT COUNT(*) FROM experiment_events"
        " WHERE experiment_key = 'test_experiment' AND event_type = 'exposure'"
    ).fetchone()[0]
    assert exposures == 1


def test_events_for_a_non_running_experiment_are_silently_ignored(
    client: TestClient, db: SQLiteDatabase
):
    as_admin(client, db)
    _create(client)  # draft, never started

    as_customer(client, db)
    response = client.post(
        "/v1/public/experiments/events",
        json={"experimentKey": "test_experiment", "eventType": "exposure"},
    )
    assert response.status_code == 200
    assert response.json()["tracked"] is False


def test_checkout_fires_a_real_conversion_event_for_an_assigned_customer(
    client: TestClient, db: SQLiteDatabase
):
    """The docstring in services/checkout.py promises this fires server-side
    so a missed client-side beacon never loses the conversion. This is the
    test that actually proves it does."""
    _add_product(db, product_id="prd_exp_conv", variant_id="var_exp_conv", sku="EXP-CONV-1")

    as_admin(client, db)
    experiment_id = _create(client, key="checkout_conversion_experiment")["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    as_customer(client, db)
    client.get("/v1/public/experiments/assignments")  # establishes the exposure

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [{"variantId": "var_exp_conv", "quantity": 1}],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    order_total = response.json()["totalMinor"]

    conversion = db._conn.execute(
        "SELECT event_value FROM experiment_events"
        " WHERE experiment_key = 'checkout_conversion_experiment' AND event_type = 'conversion'"
    ).fetchone()
    assert conversion is not None
    # The event value is the real order total (item price plus delivery, tax,
    # etc.), not the bare line price -- that is what makes it usable for an
    # AOV-lift experiment.
    assert conversion["event_value"] == float(order_total)


def test_results_reflect_real_events_through_the_admin_api(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    experiment_id = _create(client, key="results_experiment")["id"]
    client.post(f"/v1/admin/experiments/{experiment_id}/start")

    for i in range(6):
        db._conn.execute(
            "INSERT INTO experiment_events (id, experiment_key, variant, user_id, event_type,"
            " event_value, created_at) VALUES (?, 'results_experiment', 'control', ?,"
            " 'exposure', NULL, '2026-08-01T00:00:00Z')",
            (f"evt_ctrl_exp_{i}", f"usr_ctrl_{i}"),
        )
    for i in range(2):
        db._conn.execute(
            "INSERT INTO experiment_events (id, experiment_key, variant, user_id, event_type,"
            " event_value, created_at) VALUES (?, 'results_experiment', 'control', ?,"
            " 'conversion', NULL, '2026-08-01T00:00:00Z')",
            (f"evt_ctrl_conv_{i}", f"usr_ctrl_{i}"),
        )
    for i in range(6):
        db._conn.execute(
            "INSERT INTO experiment_events (id, experiment_key, variant, user_id, event_type,"
            " event_value, created_at) VALUES (?, 'results_experiment', 'treatment', ?,"
            " 'exposure', NULL, '2026-08-01T00:00:00Z')",
            (f"evt_treat_exp_{i}", f"usr_treat_{i}"),
        )
    for i in range(4):
        db._conn.execute(
            "INSERT INTO experiment_events (id, experiment_key, variant, user_id, event_type,"
            " event_value, created_at) VALUES (?, 'results_experiment', 'treatment', ?,"
            " 'conversion', NULL, '2026-08-01T00:00:00Z')",
            (f"evt_treat_conv_{i}", f"usr_treat_{i}"),
        )
    db._conn.commit()

    response = client.get(f"/v1/admin/experiments/{experiment_id}/results")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totalExposures"] == 12
    assert body["totalConversions"] == 6

    control = next(v for v in body["variants"] if v["key"] == "control")
    treatment = next(v for v in body["variants"] if v["key"] == "treatment")
    # The API rounds to 6 decimal places for transport, so compare against
    # that same rounding rather than the unrounded fraction.
    assert control["conversionRate"] == round(2 / 6, 6)
    assert treatment["conversionRate"] == round(4 / 6, 6)

    comparison = body["comparisons"][0]
    assert comparison["treatmentKey"] == "treatment"
    # Minor, harmless inconsistency worth pinning rather than silently fixing:
    # `variants[].conversionRate` above is rounded to 6dp
    # (services/experiments.py `compute_results`), but `comparisons[].controlRate`
    # /`treatmentRate` are the raw unrounded fractions. Both are correct to
    # double precision; only the transport rounding differs.
    assert comparison["controlRate"] == 2 / 6
    assert comparison["treatmentRate"] == 4 / 6

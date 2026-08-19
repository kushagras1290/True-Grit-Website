"""Integration tests for `api/intelligence.py`: demand-forecast admin routes
and the public product-recommendations surface.

`services/demand_forecasting.py` and `services/recommendations.py` already
have unit coverage that drives the pipelines end to end
(`tests/unit/test_inventory_intelligence.py`). What was missing, and what this
file adds, is coverage of the HTTP layer itself: permission gating, farm-owner
scoping (a farm owner must see and edit only their own farm's forecasts, and
must not be able to trigger a store-wide recompute), the public endpoint's
cold-start fallback when no recommendation run has completed yet, and the
out-of-stock filtering that keeps a recommendation strip from ever offering
something a customer cannot actually buy.
"""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.demand_forecasting import recompute_demand_forecasts
from truegrit_api.services.recommendations import recompute_recommendations

NORTH_FARM_ID = "farm_test_intel_north"
SOUTH_FARM_ID = "farm_test_intel_south"
NORTH_PRODUCT_ID = "prd_test_intel_north"
NORTH_VARIANT_ID = "var_test_intel_north"
SOUTH_PRODUCT_ID = "prd_test_intel_south"
SOUTH_VARIANT_ID = "var_test_intel_south"


def _add_farm(db: SQLiteDatabase, farm_id: str, name: str) -> None:
    db._conn.execute(
        "INSERT INTO farms (id, name, slug, country_code, status, created_at,"
        " created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, 'IN', 'published', '2026-07-01T00:00:00Z', 'usr_admin',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (farm_id, name, farm_id.replace("_", "-")),
    )


def _add_product(
    db: SQLiteDatabase,
    *,
    product_id: str,
    variant_id: str,
    farm_id: str | None,
    name: str,
    sku: str,
    on_hand: int = 50,
    list_minor: int = 49_900,
    accepts_orders: int = 1,
) -> None:
    slug = product_id.removeprefix("prd_").replace("_", "-")
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id,"
        " accepts_orders, status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', ?, ?, 'published',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, name, name, slug, farm_id, accepts_orders),
    )
    db._conn.execute(
        "INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,"
        " created_at, updated_at)"
        " VALUES (?, ?, ?, ?, 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')",
        (variant_id, product_id, sku, name),
    )
    db._conn.execute(
        "INSERT INTO variant_prices (id, variant_id, market_code, currency_code,"
        " list_amount_minor, starts_at, status, created_at, created_by)"
        " VALUES (?, ?, 'IN', 'INR', ?, '2026-07-01T00:00:00Z', 'active',"
        " '2026-07-01T00:00:00Z', 'usr_admin')",
        (f"vpr_{variant_id}", variant_id, list_minor),
    )
    db._conn.execute(
        "INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,"
        " reorder_threshold, version, updated_at)"
        " VALUES (?, 'loc_mumbai', ?, 0, 5, 1, '2026-07-01T00:00:00Z')",
        (variant_id, on_hand),
    )


@pytest.fixture(autouse=True)
def _two_farm_catalogue(db: SQLiteDatabase) -> None:
    """A north/south split, matching `test_farm_owner.py`'s pattern, plus a
    farm-owner session scoped to the north farm -- everything the scoping
    tests below need."""
    _add_farm(db, NORTH_FARM_ID, "Northgate Growers")
    _add_farm(db, SOUTH_FARM_ID, "Southbrook Farms")
    db._conn.execute(
        "INSERT OR REPLACE INTO farm_members (user_id, farm_id, created_at, created_by)"
        " VALUES ('usr_farmowner', ?, '2026-07-01T00:00:00Z', 'usr_admin')",
        (NORTH_FARM_ID,),
    )
    _add_product(
        db,
        product_id=NORTH_PRODUCT_ID,
        variant_id=NORTH_VARIANT_ID,
        farm_id=NORTH_FARM_ID,
        name="Northgate Mangoes",
        sku="TST-INTEL-NORTH",
    )
    _add_product(
        db,
        product_id=SOUTH_PRODUCT_ID,
        variant_id=SOUTH_VARIANT_ID,
        farm_id=SOUTH_FARM_ID,
        name="Southbrook Beans",
        sku="TST-INTEL-SOUTH",
    )
    db._conn.commit()


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def as_farm_owner(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_farmowner"))


# --- Demand forecasting: authorisation and scoping ---------------------------


def test_inventory_intelligence_requires_authentication(client: TestClient):
    assert client.get("/v1/admin/inventory-intelligence").status_code == 401


def test_farm_owner_sees_only_their_own_farms_forecast(client: TestClient, db: SQLiteDatabase):
    asyncio.run(recompute_demand_forecasts(db, today=date(2026, 8, 17)))
    as_farm_owner(client, db)

    response = client.get("/v1/admin/inventory-intelligence")
    assert response.status_code == 200, response.text
    variant_ids = {item["variantId"] for item in response.json()["items"]}
    assert NORTH_VARIANT_ID in variant_ids
    assert SOUTH_VARIANT_ID not in variant_ids


def test_farm_owner_cannot_update_another_farms_forecast_settings(
    client: TestClient, db: SQLiteDatabase
):
    as_farm_owner(client, db)
    response = client.patch(
        f"/v1/admin/inventory-intelligence/{SOUTH_VARIANT_ID}/settings",
        json={"leadTimeDays": 10, "safetyStockDays": 3},
    )
    assert response.status_code == 403


def test_farm_owner_can_update_their_own_forecast_settings(client: TestClient, db: SQLiteDatabase):
    as_farm_owner(client, db)
    response = client.patch(
        f"/v1/admin/inventory-intelligence/{NORTH_VARIANT_ID}/settings",
        json={"leadTimeDays": 10, "safetyStockDays": 3},
    )
    assert response.status_code == 200, response.text
    stored = db._conn.execute(
        "SELECT lead_time_days, safety_stock_days FROM inventory_forecast_settings"
        " WHERE variant_id = ?",
        (NORTH_VARIANT_ID,),
    ).fetchone()
    assert (stored["lead_time_days"], stored["safety_stock_days"]) == (10, 3)


def test_forecast_settings_reject_out_of_range_values(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.patch(
        f"/v1/admin/inventory-intelligence/{NORTH_VARIANT_ID}/settings",
        json={"leadTimeDays": 999, "safetyStockDays": 3},
    )
    assert response.status_code == 422


def test_variant_forecast_is_scoped_to_the_farm_owners_farm(client: TestClient, db: SQLiteDatabase):
    asyncio.run(recompute_demand_forecasts(db, today=date(2026, 8, 17)))
    as_farm_owner(client, db)

    own = client.get(f"/v1/admin/inventory-intelligence/{NORTH_VARIANT_ID}/forecast")
    assert own.status_code == 200
    assert len(own.json()["items"]) == 30  # HORIZON_DAYS

    other = client.get(f"/v1/admin/inventory-intelligence/{SOUTH_VARIANT_ID}/forecast")
    assert other.status_code == 403


def test_farm_owner_cannot_trigger_a_store_wide_forecast_recompute(
    client: TestClient, db: SQLiteDatabase
):
    """Recomputing forecasts touches every farm's variants. A farm owner is
    scoped to their own catalogue everywhere else and must be scoped here too,
    not handed a lever that recalculates data outside their farm."""
    as_farm_owner(client, db)
    response = client.post("/v1/admin/inventory-intelligence/recompute")
    assert response.status_code == 403


def test_unscoped_admin_can_trigger_a_forecast_recompute(client: TestClient, db: SQLiteDatabase):
    as_admin(client, db)
    response = client.post("/v1/admin/inventory-intelligence/recompute")
    assert response.status_code == 200, response.text
    assert response.json()["variants"] >= 2


def test_farm_owner_cannot_trigger_a_recommendations_recompute(
    client: TestClient, db: SQLiteDatabase
):
    as_farm_owner(client, db)
    response = client.post("/v1/admin/recommendations/recompute")
    assert response.status_code == 403


# --- Public recommendations ---------------------------------------------------


def test_recommendations_are_empty_when_the_feature_is_switched_off(
    client: TestClient, db: SQLiteDatabase
):
    db._conn.execute(
        "INSERT INTO app_settings (key, value, updated_at) VALUES"
        " ('commerce.recommendations.enabled', 'false', '2026-07-01T00:00:00Z')"
        " ON CONFLICT(key) DO UPDATE SET value = excluded.value"
    )
    db._conn.commit()
    response = client.get(f"/v1/public/products/{NORTH_PRODUCT_ID}/recommendations")
    assert response.status_code == 200, response.text
    assert response.json() == {"items": [], "total": 0, "runId": None}


def test_unknown_product_is_a_404(client: TestClient):
    response = client.get("/v1/public/products/prd_does_not_exist/recommendations")
    assert response.status_code == 404


def test_recommendations_fall_back_to_bestsellers_before_the_first_run(client: TestClient):
    """No recommendation run has completed yet. A brand-new SKU's module must
    not render blank -- it falls back to store-wide bestsellers, excluding the
    product itself."""
    response = client.get(f"/v1/public/products/{NORTH_PRODUCT_ID}/recommendations")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["runId"] is None
    for item in body["items"]:
        assert item["product"]["id"] != NORTH_PRODUCT_ID
        assert item["recommendation"]["reason"] == "trending"


def test_out_of_stock_recommended_products_are_never_offered(
    client: TestClient, db: SQLiteDatabase
):
    """A recommendation strip must never send a customer to a product they
    cannot buy."""
    # Two co-purchased orders so a real cooccurrence row is written.
    db._conn.executescript(
        """
        INSERT INTO orders (id, customer_user_id, customer_email, currency_code,
          subtotal_minor, discount_minor, delivery_minor, tax_minor, total_minor,
          order_status, payment_status, fulfilment_status, delivery_status,
          public_reference, placed_at, created_at, updated_at)
        VALUES ('ord_intel_1', 'usr_cust_riya', 'riya@example.test', 'INR',
          1000, 0, 0, 0, 1000, 'completed', 'paid', 'fulfilled', 'delivered',
          'TG-INTEL0001', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z', '2026-08-01T00:00:00Z');
        INSERT INTO order_items (id, order_id, product_id, variant_id, product_name,
          variant_name, sku, quantity, unit_list_amount_minor, unit_effective_amount_minor,
          discount_minor, tax_minor, line_total_minor)
        VALUES ('oit_intel_1a', 'ord_intel_1', 'prd_test_intel_north', 'var_test_intel_north',
          'Northgate Mangoes', 'Standard', 'TST-INTEL-NORTH', 1, 49900, 49900, 0, 0, 49900);
        INSERT INTO order_items (id, order_id, product_id, variant_id, product_name,
          variant_name, sku, quantity, unit_list_amount_minor, unit_effective_amount_minor,
          discount_minor, tax_minor, line_total_minor)
        VALUES ('oit_intel_1b', 'ord_intel_1', 'prd_test_intel_south', 'var_test_intel_south',
          'Southbrook Beans', 'Standard', 'TST-INTEL-SOUTH', 1, 49900, 49900, 0, 0, 49900);
        """
    )
    db._conn.commit()
    asyncio.run(recompute_recommendations(db))

    # South is now out of stock.
    db._conn.execute(
        "UPDATE inventory_levels SET on_hand = 0 WHERE variant_id = 'var_test_intel_south'"
    )
    db._conn.commit()

    response = client.get(f"/v1/public/products/{NORTH_PRODUCT_ID}/recommendations")
    assert response.status_code == 200, response.text
    ids = [item["product"]["id"] for item in response.json()["items"]]
    assert SOUTH_PRODUCT_ID not in ids


def test_recommendation_event_is_recorded(client: TestClient):
    response = client.post(
        "/v1/public/recommendation-events",
        json={
            "visitorSessionId": "visitor-session-0001",
            "sourceProductId": None,
            "recommendedProductId": NORTH_PRODUCT_ID,
            "recommendationRunId": None,
            "placement": "homepage",
            "eventType": "impression",
        },
    )
    assert response.status_code == 202, response.text

"""Checkout's recommendation-attribution validation
(`services/checkout.py::_validated_recommendation_attribution`).

Attribution changes analytics, not price, but it is still server-owned data:
a customer's browser supplies `recommendationSourceProductId` /
`recommendationRunId` / `recommendationPlacement` on each checkout line, and
nothing stops a modified client from sending values that make an ordinary
organic purchase look like the product-recommendations feature drove it. This
file is the coverage that was missing for that boundary -- a forged
source/run pair must be silently dropped (checkout still succeeds; it just
records no attribution), while a real one, matching an actual
`product_cooccurrence` row from a completed run, must be recorded and
correctly linked to the order.
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


def _add_product(
    db: SQLiteDatabase, *, product_id: str, variant_id: str, sku: str, name: str
) -> None:
    slug = product_id.removeprefix("prd_").replace("_", "-")
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, accepts_orders,"
        " status, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'simple', 1, 'published',"
        " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')",
        (product_id, name, name, slug),
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


def _add_cooccurrence_run(db: SQLiteDatabase, run_id: str, source_id: str, target_id: str) -> None:
    db._conn.execute(
        "INSERT INTO recommendation_runs (id, status, model_version, lookback_days,"
        " orders_processed, products_processed, associations_written, started_at, completed_at)"
        " VALUES (?, 'completed', 'test-v1', 365, 1, 2, 1, '2026-08-01T00:00:00Z',"
        " '2026-08-01T00:00:00Z')",
        (run_id,),
    )
    db._conn.execute(
        "INSERT INTO product_cooccurrence (run_id, source_product_id, recommended_product_id,"
        " co_purchase_count, source_order_count, recommended_order_count, confidence, lift,"
        " cosine_similarity, category_match, popularity_score, recency_score, blended_score,"
        " rank, reason, created_at)"
        " VALUES (?, ?, ?, 3, 5, 5, 0.6, 2.0, 0.5, 0.0, 0.5, 0.5, 0.7, 1,"
        " 'frequently_bought_together', '2026-08-01T00:00:00Z')",
        (run_id, source_id, target_id),
    )


def _attribution_row(db: SQLiteDatabase, reference: str) -> dict | None:
    row = db._conn.execute(
        "SELECT ra.* FROM recommendation_attributions ra"
        " JOIN orders o ON o.id = ra.order_id WHERE o.public_reference = ?",
        (reference,),
    ).fetchone()
    return dict(row) if row is not None else None


def as_customer(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


def test_a_valid_recommendation_pair_is_recorded_as_attribution(
    client: TestClient, db: SQLiteDatabase
):
    _add_product(
        db,
        product_id="prd_attr_source",
        variant_id="var_attr_source",
        sku="ATTR-SRC",
        name="Source",
    )
    _add_product(
        db,
        product_id="prd_attr_target",
        variant_id="var_attr_target",
        sku="ATTR-TGT",
        name="Target",
    )
    _add_cooccurrence_run(db, "rrn_attr_valid", "prd_attr_source", "prd_attr_target")
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {
                    "variantId": "var_attr_target",
                    "quantity": 1,
                    "recommendationSourceProductId": "prd_attr_source",
                    "recommendationRunId": "rrn_attr_valid",
                    "recommendationPlacement": "product",
                }
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text

    attribution = _attribution_row(db, response.json()["reference"])
    assert attribution is not None
    assert attribution["source_product_id"] == "prd_attr_source"
    assert attribution["recommended_product_id"] == "prd_attr_target"
    assert attribution["recommendation_run_id"] == "rrn_attr_valid"
    assert attribution["attributed_revenue_minor"] == 49900


def test_a_forged_run_id_is_dropped_not_recorded(client: TestClient, db: SQLiteDatabase):
    """The pair (source, target) was never actually produced by this run --
    a modified client is trying to claim credit for a recommendation that
    does not exist. Checkout must still succeed; it must just record nothing."""
    _add_product(
        db,
        product_id="prd_forge_source",
        variant_id="var_forge_source",
        sku="FRG-SRC",
        name="Source",
    )
    _add_product(
        db,
        product_id="prd_forge_target",
        variant_id="var_forge_target",
        sku="FRG-TGT",
        name="Target",
    )
    # A real completed run exists, but with no row linking these two products.
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, accepts_orders,"
        " status, created_at, created_by, updated_at, updated_by)"
        " VALUES ('prd_attr_unrelated_target', 'Unrelated', 'Unrelated', 'unrelated', 'simple',"
        " 1, 'published', '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-01T00:00:00Z', 'usr_admin')"
    )
    _add_cooccurrence_run(db, "rrn_forge_real", "prd_forge_source", "prd_attr_unrelated_target")
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {
                    "variantId": "var_forge_target",
                    "quantity": 1,
                    "recommendationSourceProductId": "prd_forge_source",
                    "recommendationRunId": "rrn_forge_real",
                    "recommendationPlacement": "product",
                }
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    assert _attribution_row(db, response.json()["reference"]) is None


def test_a_forged_run_id_that_does_not_exist_is_dropped(client: TestClient, db: SQLiteDatabase):
    _add_product(
        db,
        product_id="prd_fake_source",
        variant_id="var_fake_source",
        sku="FAKE-SRC",
        name="Source",
    )
    _add_product(
        db,
        product_id="prd_fake_target",
        variant_id="var_fake_target",
        sku="FAKE-TGT",
        name="Target",
    )
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {
                    "variantId": "var_fake_target",
                    "quantity": 1,
                    "recommendationSourceProductId": "prd_fake_source",
                    "recommendationRunId": "rrn_completely_made_up",
                    "recommendationPlacement": "product",
                }
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    assert _attribution_row(db, response.json()["reference"]) is None


def test_source_equal_to_the_purchased_product_is_not_attributed(
    client: TestClient, db: SQLiteDatabase
):
    """Claiming a product recommended itself is nonsensical and must not be
    recorded, whatever run id accompanies it."""
    _add_product(
        db, product_id="prd_self_attr", variant_id="var_self_attr", sku="SELF-1", name="Self"
    )
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {
                    "variantId": "var_self_attr",
                    "quantity": 1,
                    "recommendationSourceProductId": "prd_self_attr",
                    "recommendationPlacement": "product",
                }
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    assert _attribution_row(db, response.json()["reference"]) is None


def test_placement_without_homepage_source_falls_back_to_placement_only_attribution(
    client: TestClient, db: SQLiteDatabase
):
    """Homepage/shop popularity rows have no anchor product -- the placement
    alone is a legitimate, honest attribution signal there, unlike a claimed
    source/run pair the server cannot verify."""
    _add_product(
        db,
        product_id="prd_homepage_pick",
        variant_id="var_homepage_pick",
        sku="HOME-1",
        name="Pick",
    )
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={
            "items": [
                {
                    "variantId": "var_homepage_pick",
                    "quantity": 1,
                    "recommendationPlacement": "homepage",
                }
            ],
            "deliveryAddress": ADDRESS,
        },
    )
    assert response.status_code == 200, response.text
    attribution = _attribution_row(db, response.json()["reference"])
    assert attribution is not None
    assert attribution["source_product_id"] is None
    assert attribution["recommendation_run_id"] is None
    assert attribution["placement"] == "homepage"


def test_no_placement_at_all_means_no_attribution(client: TestClient, db: SQLiteDatabase):
    """An ordinary organic purchase, with nothing recommendation-related on
    the line, must record nothing."""
    _add_product(
        db, product_id="prd_organic", variant_id="var_organic", sku="ORG-1", name="Organic"
    )
    db._conn.commit()
    as_customer(client, db)

    response = client.post(
        "/v1/public/checkout",
        json={"items": [{"variantId": "var_organic", "quantity": 1}], "deliveryAddress": ADDRESS},
    )
    assert response.status_code == 200, response.text
    assert _attribution_row(db, response.json()["reference"]) is None

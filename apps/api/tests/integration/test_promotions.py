"""Coupons and promotions (migration 0005, extended by 0060), end to end
against checkout.

Seeds its own purchasable product (`var_promo_fixture` at 89900) rather than
depending on the demo catalogue: migration 0095 retires that catalogue from
every database it touches (the live site must not keep any trace of it), so
tests cannot rely on it surviving either. A coupon's effect is only
meaningful against a real cart total.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ADDRESS = {
    "recipientName": "Riya Nair",
    "line1": "12 Palm Grove",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postalCode": "400001",
}


@pytest.fixture(autouse=True)
def _promo_fixture_product(db: SQLiteDatabase) -> None:
    """The one synthetic purchasable product every test in this module carts
    -- see the module docstring above for why this is not the old demo
    catalogue's `var_alphonso_1kg`."""
    db._conn.executescript(
        """
        INSERT INTO products (id, internal_name, name, slug, product_type, status,
          accepts_orders, created_at, created_by, updated_at, updated_by)
        VALUES ('prd_promo_fixture', 'Promotions Fixture Product',
          'Promotions Fixture Product', 'promotions-fixture-product', 'simple',
          'published', 1, '2026-07-01T00:00:00Z', 'usr_admin',
          '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,
          created_at, updated_at)
        VALUES ('var_promo_fixture', 'prd_promo_fixture', 'PROMO-FIXTURE-1KG',
          '1 kg', 'active', 1, '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z');
        INSERT INTO variant_prices (id, variant_id, market_code, currency_code,
          list_amount_minor, status, created_at, created_by)
        VALUES ('vpr_promo_fixture', 'var_promo_fixture', 'IN', 'INR', 89900,
          'active', '2026-07-01T00:00:00Z', 'usr_admin');
        INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,
          reorder_threshold, version, updated_at)
        VALUES ('var_promo_fixture', 'loc_mumbai', 500, 0, 20, 1, '2026-07-01T00:00:00Z');
        """
    )
    db._conn.commit()


def as_customer(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def enable_promotions(client: TestClient, db: SQLiteDatabase) -> None:
    as_admin(client, db)
    response = client.patch("/v1/admin/storefront-settings", json={"promotions": True})
    assert response.status_code == 200, response.text


def checkout(client: TestClient, *, coupon_code: str | None = None) -> Response:
    payload: dict[str, Any] = {
        "items": [{"variantId": "var_promo_fixture", "quantity": 1}],
        "deliveryAddress": ADDRESS,
    }
    if coupon_code is not None:
        payload["couponCode"] = coupon_code
    return client.post("/v1/public/checkout", json=payload)


def create_fixed_discount_promotion(
    client: TestClient, db: SQLiteDatabase, **overrides: Any
) -> dict[str, Any]:
    as_admin(client, db)
    body: dict[str, Any] = {
        "name": "Test fixed discount",
        "status": "active",
        "actionType": "fixed_discount",
        "amountMinor": 10_000,
    }
    body.update(overrides)
    response = client.post("/v1/admin/promotions", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def test_admin_can_create_a_promotion_and_issue_a_coupon(client, db):
    promotion = create_fixed_discount_promotion(client, db)
    assert promotion["status"] == "active"

    coupon = client.post(
        f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "welcome10"}
    )
    assert coupon.status_code == 200, coupon.text
    # Stored uppercased and case-insensitive on lookup.
    assert coupon.json()["code"] == "WELCOME10"

    detail = client.get(f"/v1/admin/promotions/{promotion['id']}")
    assert detail.status_code == 200
    assert detail.json()["coupons"][0]["code"] == "WELCOME10"


def test_creating_a_promotion_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.post(
        "/v1/admin/promotions",
        json={
            "name": "Nope",
            "status": "active",
            "actionType": "fixed_discount",
            "amountMinor": 1000,
        },
    )
    assert response.status_code == 403


def test_a_valid_coupon_reduces_the_checkout_total(client, db):
    enable_promotions(client, db)
    promotion = create_fixed_discount_promotion(client, db)
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "SAVE100"})

    as_customer(client, db)
    response = checkout(client, coupon_code="save100")  # lower-case on purpose
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discountMinor"] == 10_000
    assert body["totalMinor"] == body["subtotalMinor"] + body["deliveryMinor"] - 10_000
    assert body["couponCode"] == "SAVE100"

    # Recorded: one adjustment row and one redemption row, both against the
    # real order, so the ledger and the usage-limit checks agree with reality.
    order_id = db._conn.execute(
        "SELECT id FROM orders WHERE public_reference = ?", (response.json()["reference"],)
    ).fetchone()[0]
    adjustment = db._conn.execute(
        "SELECT adjustment_type, amount_minor FROM order_adjustments WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    assert adjustment[0] == "coupon"
    assert adjustment[1] == -10_000
    redemption = db._conn.execute(
        "SELECT order_id FROM coupon_redemptions WHERE order_id = ?", (order_id,)
    ).fetchone()
    assert redemption is not None


def test_an_unknown_coupon_code_is_rejected(client, db):
    enable_promotions(client, db)
    as_customer(client, db)
    response = checkout(client, coupon_code="DOESNOTEXIST")
    assert response.status_code == 422


def test_coupons_are_refused_while_the_feature_is_switched_off(client, db):
    # Default is off (migration 0060) -- do not call enable_promotions here.
    promotion = create_fixed_discount_promotion(client, db)
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "OFFTEST"})

    as_customer(client, db)
    response = checkout(client, coupon_code="OFFTEST")
    assert response.status_code == 422


def test_an_automatic_promotion_with_no_coupons_applies_with_no_code(client, db):
    enable_promotions(client, db)
    create_fixed_discount_promotion(client, db, name="Automatic ₹50 off")
    # No coupon issued for this one -- it is automatic.

    as_customer(client, db)
    response = checkout(client)
    assert response.status_code == 200, response.text
    assert response.json()["discountMinor"] == 10_000
    assert response.json()["couponCode"] is None


def test_a_disabled_feature_does_not_auto_apply_a_promotion_either(client, db):
    create_fixed_discount_promotion(client, db, name="Should not apply")
    as_customer(client, db)
    response = checkout(client)
    assert response.status_code == 200
    assert response.json()["discountMinor"] == 0


def test_free_delivery_action_zeroes_the_delivery_fee(client, db):
    enable_promotions(client, db)
    promotion = create_fixed_discount_promotion(
        client, db, name="Free delivery", actionType="free_delivery", amountMinor=None
    )
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "FREESHIP"})

    as_customer(client, db)
    response = checkout(client, coupon_code="FREESHIP")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["deliveryMinor"] == 0
    assert body["totalMinor"] == body["subtotalMinor"]


def test_percentage_discount_is_capped_by_maximum_discount(client, db):
    enable_promotions(client, db)
    promotion = create_fixed_discount_promotion(
        client,
        db,
        name="20% off, capped",
        actionType="percentage_discount",
        amountMinor=None,
        valueBasisPoints=2000,
        maximumDiscountMinor=5_000,
    )
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "CAPPED20"})

    as_customer(client, db)
    response = checkout(client, coupon_code="CAPPED20")
    assert response.status_code == 200, response.text
    # 20% of 89900 = 17980, but the cap is 5000.
    assert response.json()["discountMinor"] == 5_000


def test_a_usage_limit_total_is_enforced(client, db):
    enable_promotions(client, db)
    promotion = create_fixed_discount_promotion(client, db, name="One use only", usageLimitTotal=1)
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "ONLYONE"})

    as_customer(client, db)
    first = checkout(client, coupon_code="ONLYONE")
    assert first.status_code == 200, first.text

    second = checkout(client, coupon_code="ONLYONE")
    assert second.status_code == 422


def test_a_promotion_with_redemptions_is_archived_not_deleted(client, db):
    enable_promotions(client, db)
    promotion = create_fixed_discount_promotion(client, db)
    client.post(f"/v1/admin/promotions/{promotion['id']}/coupons", json={"code": "KEEPME"})

    as_customer(client, db)
    checkout(client, coupon_code="KEEPME")

    as_admin(client, db)
    deleted = client.delete(f"/v1/admin/promotions/{promotion['id']}")
    assert deleted.status_code == 200
    body = deleted.json()
    assert body["deleted"] is False
    assert body["status"] == "archived"

    still_there = client.get(f"/v1/admin/promotions/{promotion['id']}")
    assert still_there.status_code == 200
    assert still_there.json()["status"] == "archived"


def test_an_unused_promotion_can_be_permanently_deleted(client, db):
    promotion = create_fixed_discount_promotion(client, db)
    as_admin(client, db)
    deleted = client.delete(f"/v1/admin/promotions/{promotion['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True
    assert client.get(f"/v1/admin/promotions/{promotion['id']}").status_code == 404


def test_featured_promotion_endpoint_respects_the_sitewide_switch(client, db):
    promotion = create_fixed_discount_promotion(client, db, name="Featured", headline="Big savings")

    disabled = client.get("/v1/public/promotions/featured")
    assert disabled.status_code == 200
    assert disabled.json()["promotion"] is None

    enable_promotions(client, db)
    client.cookies.clear()
    enabled = client.get("/v1/public/promotions/featured")
    assert enabled.status_code == 200
    assert enabled.json()["promotion"]["id"] == promotion["id"]
    assert enabled.json()["promotion"]["headline"] == "Big savings"


def test_featured_promotion_manual_mode_pins_one_specific_promotion(client, db):
    enable_promotions(client, db)
    create_fixed_discount_promotion(client, db, name="A", priority=100)
    pinned = create_fixed_discount_promotion(client, db, name="B (pinned)", priority=0)

    client.cookies.clear()
    response = client.get(f"/v1/public/promotions/featured?promotionId={pinned['id']}")
    assert response.status_code == 200
    assert response.json()["promotion"]["id"] == pinned["id"]

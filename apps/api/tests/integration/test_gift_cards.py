"""Gift cards (migration 0082), end to end against checkout.

Uses the seeded catalogue (`var_alphonso_1kg`, priced at 89900) the same way
test_promotions.py does, since a redemption's effect is only meaningful
against a real cart total.
"""

from __future__ import annotations

from typing import Any

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


def as_customer(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_cust_riya"))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def enable_gift_cards(client: TestClient, db: SQLiteDatabase) -> None:
    as_admin(client, db)
    response = client.patch("/v1/admin/storefront-settings", json={"giftCards": True})
    assert response.status_code == 200, response.text


def issue_gift_card(client: TestClient, db: SQLiteDatabase, **overrides: Any) -> dict[str, Any]:
    as_admin(client, db)
    body: dict[str, Any] = {"balanceMinor": 50_000}
    body.update(overrides)
    response = client.post("/v1/admin/gift-cards", json=body)
    assert response.status_code == 200, response.text
    return response.json()


def checkout(
    client: TestClient, *, gift_card_code: str | None = None, coupon_code: str | None = None
) -> Response:
    payload: dict[str, Any] = {
        "items": [{"variantId": "var_alphonso_1kg", "quantity": 1}],
        "deliveryAddress": ADDRESS,
    }
    if gift_card_code is not None:
        payload["giftCardCode"] = gift_card_code
    if coupon_code is not None:
        payload["couponCode"] = coupon_code
    return client.post("/v1/public/checkout", json=payload)


def test_admin_can_issue_a_gift_card_with_a_generated_code(client, db):
    card = issue_gift_card(client, db, balanceMinor=100_000)
    assert card["balanceMinor"] == 100_000
    assert len(card["code"]) >= 6

    listed = client.get("/v1/admin/gift-cards").json()
    row = next(item for item in listed["items"] if item["id"] == card["id"])
    assert row["balanceMinor"] == 100_000
    assert row["status"] == "active"


def test_admin_can_issue_a_gift_card_with_a_custom_code(client, db):
    card = issue_gift_card(client, db, code="wintergift", balanceMinor=20_000)
    assert card["code"] == "WINTERGIFT"

    duplicate = client.post(
        "/v1/admin/gift-cards", json={"balanceMinor": 20_000, "code": "WinterGift"}
    )
    assert duplicate.status_code == 409


def test_issuing_a_gift_card_is_permission_gated(client, db):
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    response = client.post("/v1/admin/gift-cards", json={"balanceMinor": 20_000})
    assert response.status_code == 403


def test_gift_card_value_must_be_within_bounds(client, db):
    as_admin(client, db)
    too_small = client.post("/v1/admin/gift-cards", json={"balanceMinor": 50})
    assert too_small.status_code == 422
    too_large = client.post("/v1/admin/gift-cards", json={"balanceMinor": 10_000_000})
    assert too_large.status_code == 422


def test_a_valid_gift_card_reduces_the_checkout_total(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=50_000)

    as_customer(client, db)
    response = checkout(client, gift_card_code=card["code"].lower())  # lower-case on purpose
    assert response.status_code == 200, response.text
    body = response.json()
    pre_gift_card_total = body["subtotalMinor"] + body["deliveryMinor"] - body["discountMinor"]
    assert body["giftCardAppliedMinor"] == 50_000
    assert body["totalMinor"] == pre_gift_card_total - 50_000
    assert body["giftCardCode"] == card["code"]

    # Recorded against the real order, so a repeat GET of the order sees it
    # and the balance ledger agrees with what checkout actually applied.
    order = client.get(f"/v1/public/orders/{body['reference']}")
    assert order.status_code == 200

    as_admin(client, db)
    admin_order = client.get(f"/v1/admin/orders/{body['id']}").json()
    assert admin_order["giftCardAppliedMinor"] == 50_000
    assert admin_order["giftCardCode"] == card["code"]


def test_gift_card_balance_is_exhausted_across_multiple_orders(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=50_000)
    as_customer(client, db)

    first = checkout(client, gift_card_code=card["code"])
    assert first.status_code == 200, first.text
    assert first.json()["giftCardAppliedMinor"] == 50_000

    balance = client.get(f"/v1/public/gift-cards/{card['code']}").json()
    assert balance["balanceMinor"] == 0

    second = checkout(client, gift_card_code=card["code"])
    assert second.status_code == 422
    assert "no balance" in second.json()["error"]["message"].lower()


def test_gift_card_balance_larger_than_one_order_carries_a_remainder(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=200_000)
    as_customer(client, db)

    order = checkout(client, gift_card_code=card["code"])
    assert order.status_code == 200, order.text
    body = order.json()
    pre_gift_card_total = body["subtotalMinor"] + body["deliveryMinor"] - body["discountMinor"]
    assert body["giftCardAppliedMinor"] == pre_gift_card_total, "fully covered, order total is 0"
    assert body["totalMinor"] == 0

    balance = client.get(f"/v1/public/gift-cards/{card['code']}").json()
    assert balance["balanceMinor"] == 200_000 - pre_gift_card_total


def test_gift_card_stacks_with_a_coupon(client, db):
    enable_gift_cards(client, db)
    as_admin(client, db)
    promo = client.post(
        "/v1/admin/promotions",
        json={
            "name": "Stack test",
            "status": "active",
            "actionType": "fixed_discount",
            "amountMinor": 10_000,
        },
    ).json()
    client.post(f"/v1/admin/promotions/{promo['id']}/coupons", json={"code": "STACK10"})
    client.patch("/v1/admin/storefront-settings", json={"promotions": True})
    card = issue_gift_card(client, db, balanceMinor=30_000)

    as_customer(client, db)
    response = checkout(client, gift_card_code=card["code"], coupon_code="STACK10")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["discountMinor"] == 10_000
    assert body["giftCardAppliedMinor"] == 30_000
    assert body["totalMinor"] == body["subtotalMinor"] + body["deliveryMinor"] - 10_000 - 30_000


def test_unknown_gift_card_code_is_rejected(client, db):
    enable_gift_cards(client, db)
    as_customer(client, db)
    response = checkout(client, gift_card_code="NOSUCHCODE")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_cancelled_gift_card_is_rejected(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=50_000)
    as_admin(client, db)
    cancel = client.post(f"/v1/admin/gift-cards/{card['id']}/cancel")
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    as_customer(client, db)
    response = checkout(client, gift_card_code=card["code"])
    assert response.status_code == 422
    assert "no longer active" in response.json()["error"]["message"].lower()


def test_gift_card_code_refused_while_feature_is_disabled(client, db):
    # Default is off (migration 0082) -- do not call enable_gift_cards here.
    card = issue_gift_card(client, db, balanceMinor=50_000)
    as_customer(client, db)
    response = checkout(client, gift_card_code=card["code"])
    assert response.status_code == 422
    assert "not available" in response.json()["error"]["message"].lower()


def test_preview_gift_card_does_not_record_a_redemption(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=50_000)
    as_customer(client, db)

    preview = client.post(
        "/v1/public/checkout/preview-gift-card",
        json={"giftCardCode": card["code"], "amountNeededMinor": 40_000},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["appliedMinor"] == 40_000
    assert preview.json()["remainingAfterMinor"] == 10_000

    # A preview must never touch the ledger -- the full balance is still
    # there for the real checkout below.
    balance = client.get(f"/v1/public/gift-cards/{card['code']}").json()
    assert balance["balanceMinor"] == 50_000


def test_public_balance_lookup_requires_no_sign_in(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=75_000)
    # No session cookie set at all.
    response = client.get(f"/v1/public/gift-cards/{card['code']}")
    assert response.status_code == 200
    assert response.json()["balanceMinor"] == 75_000


def test_gift_card_detail_lists_redemption_history(client, db):
    enable_gift_cards(client, db)
    card = issue_gift_card(client, db, balanceMinor=200_000)
    as_customer(client, db)
    checkout(client, gift_card_code=card["code"])

    as_admin(client, db)
    detail = client.get(f"/v1/admin/gift-cards/{card['id']}").json()
    assert len(detail["redemptions"]) == 1
    assert (
        detail["redemptions"][0]["amountMinor"]
        == detail["initialBalanceMinor"] - detail["balanceMinor"]
    )

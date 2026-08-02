"""Product reviews and ratings (migration 0005, extended by 0057).

These tests place their own product/order fixtures rather than relying on the
seeded catalogue, for the same reason test_content_comments.py owns its
article/recipe: seeded catalogue content is periodically replaced wholesale.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from httpx import Response

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase


@pytest.fixture(autouse=True)
def review_fixtures(db: SQLiteDatabase) -> None:
    """A published product, a completed order for it under usr_reviewer, a
    second not-yet-completed order for the eligibility test, and a second
    published product the customer never bought."""
    db._conn.execute(
        "INSERT INTO users (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES ('usr_reviewer', 'reviewer@example.test', 'Reviewer', 'customer', 'active',"
        "  '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db._conn.execute(
        "INSERT INTO products"
        " (id, internal_name, name, slug, product_type, status, created_at, created_by,"
        "  updated_at, updated_by)"
        " VALUES ('prd_review_fixture', 'Review Fixture', 'Review Fixture Product',"
        "  'review-fixture-product', 'general', 'published', '2026-01-01T00:00:00Z', 'usr_admin',"
        "  '2026-01-01T00:00:00Z', 'usr_admin')"
    )
    db._conn.execute(
        "INSERT INTO products"
        " (id, internal_name, name, slug, product_type, status, created_at, created_by,"
        "  updated_at, updated_by)"
        " VALUES ('prd_other_fixture', 'Other Fixture', 'Other Fixture Product',"
        "  'other-fixture-product', 'general', 'published', '2026-01-01T00:00:00Z', 'usr_admin',"
        "  '2026-01-01T00:00:00Z', 'usr_admin')"
    )
    db._conn.execute(
        "INSERT INTO product_variants (id, product_id, sku, name, status, created_at, updated_at)"
        " VALUES ('var_review_fixture', 'prd_review_fixture', 'REV-FIX-1', 'Default', 'active',"
        "  '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db._conn.execute(
        "INSERT INTO variant_prices"
        " (id, variant_id, market_code, currency_code, list_amount_minor, status, created_at,"
        "  created_by)"
        " VALUES ('prc_review_fixture', 'var_review_fixture', 'IN', 'INR', 10000, 'active',"
        "  '2026-01-01T00:00:00Z', 'usr_admin')"
    )
    db._conn.execute(
        "INSERT INTO orders"
        " (id, public_reference, customer_user_id, customer_email, currency_code, subtotal_minor,"
        "  total_minor, order_status, payment_status, fulfilment_status, delivery_status,"
        "  created_at, updated_at)"
        " VALUES ('ord_review_fixture', 'TG-REVIEW-1', 'usr_reviewer', 'reviewer@example.test',"
        "  'INR', 10000, 10000, 'completed', 'paid', 'fulfilled', 'delivered',"
        "  '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db._conn.execute(
        "INSERT INTO order_items"
        " (id, order_id, product_id, variant_id, product_name, variant_name, sku, quantity,"
        "  unit_list_amount_minor, unit_effective_amount_minor, line_total_minor)"
        " VALUES ('oit_review_fixture', 'ord_review_fixture', 'prd_review_fixture',"
        "  'var_review_fixture', 'Review Fixture Product', 'Default', 'REV-FIX-1', 1, 10000,"
        "  10000, 10000)"
    )
    db._conn.execute(
        "INSERT INTO orders"
        " (id, public_reference, customer_user_id, customer_email, currency_code, subtotal_minor,"
        "  total_minor, order_status, payment_status, fulfilment_status, delivery_status,"
        "  created_at, updated_at)"
        " VALUES ('ord_review_pending', 'TG-REVIEW-2', 'usr_reviewer', 'reviewer@example.test',"
        "  'INR', 10000, 10000, 'confirmed', 'paid', 'unfulfilled', 'not_ready',"
        "  '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
    )
    db._conn.execute(
        "INSERT INTO order_items"
        " (id, order_id, product_id, variant_id, product_name, variant_name, sku, quantity,"
        "  unit_list_amount_minor, unit_effective_amount_minor, line_total_minor)"
        " VALUES ('oit_review_pending', 'ord_review_pending', 'prd_review_fixture',"
        "  'var_review_fixture', 'Review Fixture Product', 'Default', 'REV-FIX-1', 1, 10000,"
        "  10000, 10000)"
    )
    db._conn.commit()


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_reviewer") -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def submit_review(client: TestClient, *, rating: int = 5, body: str | None = None) -> Response:
    return client.post(
        "/v1/public/orders/TG-REVIEW-1/reviews",
        json={
            "productId": "prd_review_fixture",
            "rating": rating,
            "title": "Solid product",
            "body": body or "Exactly what I expected, would buy again without hesitation.",
        },
    )


def test_a_verified_purchaser_can_review_and_it_stays_pending(client, db):
    as_customer(client, db)
    response = submit_review(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "pending"

    # Not yet public: only approved reviews appear on the product feed.
    client.cookies.clear()
    public = client.get("/v1/public/products/review-fixture-product/reviews")
    assert public.status_code == 200
    assert public.json()["items"] == []


def test_reviewing_requires_a_signed_in_customer(client):
    response = submit_review(client)
    assert response.status_code == 401


def test_cannot_review_a_product_not_in_the_order(client, db):
    as_customer(client, db)
    response = client.post(
        "/v1/public/orders/TG-REVIEW-1/reviews",
        json={
            "productId": "prd_other_fixture",
            "rating": 5,
            "body": "This product was never in that order at all.",
        },
    )
    assert response.status_code == 422, response.text


def test_order_must_be_completed_not_confirmed(client, db):
    as_customer(client, db)
    response = client.post(
        "/v1/public/orders/TG-REVIEW-2/reviews",
        json={
            "productId": "prd_review_fixture",
            "rating": 5,
            "body": "This order has not been marked completed yet.",
        },
    )
    assert response.status_code == 409, response.text


def test_a_second_review_of_the_same_product_and_order_is_rejected(client, db):
    as_customer(client, db)
    first = submit_review(client)
    assert first.status_code == 200
    second = submit_review(client)
    assert second.status_code == 409


def test_rating_is_bounded_one_to_five(client, db):
    as_customer(client, db)
    response = submit_review(client, rating=6)
    assert response.status_code == 422


def test_body_has_a_minimum_length(client, db):
    as_customer(client, db)
    response = submit_review(client, body="Bad.")
    assert response.status_code == 422


def test_staff_approve_and_it_becomes_public(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    moderated = client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})
    assert moderated.status_code == 200, moderated.text
    assert moderated.json()["status"] == "approved"

    client.cookies.clear()
    public = client.get("/v1/public/products/review-fixture-product/reviews")
    items = public.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == review_id
    assert items[0]["verifiedPurchase"] is True

    # The catalogue's rating aggregate reflects only approved reviews.
    detail = client.get("/v1/public/products/review-fixture-product")
    assert detail.json()["ratingAverage"] == 5.0
    assert detail.json()["ratingCount"] == 1


def test_staff_reject_keeps_it_off_the_product_page(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    moderated = client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "reject"})
    assert moderated.status_code == 200
    assert moderated.json()["status"] == "rejected"

    client.cookies.clear()
    public = client.get("/v1/public/products/review-fixture-product/reviews")
    assert public.json()["items"] == []


def test_moderating_the_same_status_twice_conflicts(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})
    repeated = client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})
    assert repeated.status_code == 409


def test_moderation_is_permission_gated(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    # usr_blogger holds no reviews.* permission (seeded role: content-only).
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_blogger"))
    response = client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})
    assert response.status_code == 403


def test_admin_can_list_and_delete_a_review(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    listed = client.get("/v1/admin/reviews?status=pending")
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()["items"]]
    assert review_id in ids
    assert listed.json()["pending"] >= 1

    deleted = client.delete(f"/v1/admin/reviews/{review_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True

    still_listed = client.get("/v1/admin/reviews")
    assert review_id not in [row["id"] for row in still_listed.json()["items"]]


def test_admin_can_edit_review_content(client, db):
    as_customer(client, db)
    review_id = submit_review(client, rating=2).json()["id"]

    as_admin(client, db)
    edited = client.patch(
        f"/v1/admin/reviews/{review_id}",
        json={"rating": 4, "title": "Corrected title", "body": "Edited by staff for clarity here."},
    )
    assert edited.status_code == 200, edited.text
    body = edited.json()
    assert body["rating"] == 4
    assert body["title"] == "Corrected title"
    assert body["body"] == "Edited by staff for clarity here."

    listed = client.get("/v1/admin/reviews")
    edited_row = next(row for row in listed.json()["items"] if row["id"] == review_id)
    assert edited_row["rating"] == 4
    assert edited_row["title"] == "Corrected title"


def test_editing_a_review_only_touches_fields_sent(client, db):
    as_customer(client, db)
    review_id = submit_review(client, rating=3).json()["id"]

    as_admin(client, db)
    edited = client.patch(
        f"/v1/admin/reviews/{review_id}", json={"title": "Only the title changed"}
    )
    assert edited.status_code == 200
    body = edited.json()
    assert body["title"] == "Only the title changed"
    assert body["rating"] == 3  # untouched


def test_editing_a_review_rejects_an_impossible_rating(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    response = client.patch(f"/v1/admin/reviews/{review_id}", json={"rating": 9})
    assert response.status_code == 422


def test_editing_is_permission_gated(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_blogger"))
    response = client.patch(f"/v1/admin/reviews/{review_id}", json={"title": "Should not apply"})
    assert response.status_code == 403


def test_all_reviews_endpoint_lists_approved_reviews_sitewide(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})

    client.cookies.clear()
    listed = client.get("/v1/public/reviews?limit=1")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] >= 1
    assert len(body["items"]) == 1

    all_reviews = client.get("/v1/public/reviews?limit=100")
    assert any(item["id"] == review_id for item in all_reviews.json()["items"])
    matched = next(item for item in all_reviews.json()["items"] if item["id"] == review_id)
    assert matched["productSlug"] == "review-fixture-product"


def test_my_order_reviews_shows_status_before_moderation(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    mine = client.get("/v1/public/orders/TG-REVIEW-1/reviews")
    assert mine.status_code == 200
    items = mine.json()["items"]
    assert len(items) == 1
    assert items[0]["id"] == review_id
    assert items[0]["status"] == "pending"


def test_featured_reviews_rule_mode_only_returns_approved_above_the_floor(client, db):
    as_customer(client, db)
    low = submit_review(client, rating=2, body="Not great, would not buy this again honestly.")
    review_id = low.json()["id"]

    as_admin(client, db)
    client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})

    # The seeded catalogue already carries its own approved 4-5 star reviews,
    # so this asserts the low-rated fixture review specifically stays out
    # above the floor and appears once the floor drops to include it --
    # rather than asserting the whole feed is empty.
    client.cookies.clear()
    featured = client.get("/v1/public/reviews/featured?minRating=4")
    assert featured.status_code == 200
    assert review_id not in [item["id"] for item in featured.json()["items"]]

    below_floor = client.get("/v1/public/reviews/featured?minRating=1")
    assert any(item["id"] == review_id for item in below_floor.json()["items"])


def test_featured_reviews_manual_mode_returns_requested_ids_in_order(client, db):
    as_customer(client, db)
    review_id = submit_review(client).json()["id"]

    as_admin(client, db)
    client.post(f"/v1/admin/reviews/{review_id}/moderate", json={"action": "approve"})

    client.cookies.clear()
    featured = client.get(f"/v1/public/reviews/featured?ids={review_id}")
    assert featured.status_code == 200
    items = featured.json()["items"]
    assert len(items) == 1
    assert items[0]["productSlug"] == "review-fixture-product"

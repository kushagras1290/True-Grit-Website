"""Product reviews and ratings (migration 0005, extended by 0057).

A signed-in customer may review a product from one of their own **completed**
orders that contains it -- one review per product per order
(`UNIQUE(product_id, customer_user_id, order_id)`), so a repeat customer may
review a repurchase separately. A review is not visible to other customers
until staff with `reviews.moderate` approve it: unlike discussions and
content_comments (already-live content that moderation reacts to after the
fact), a review is worth keeping off the product page until a human has seen
it -- the same pending-first posture as `content_submissions` and
`farm_partnership_requests`.
"""

from __future__ import annotations

from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_MIN_BODY: Final = 10
_MAX_BODY: Final = 4000
_MAX_TITLE: Final = 120
_MAX_REASON: Final = 500

# Only a completed order proves the reviewer actually received the product.
_ELIGIBLE_ORDER_STATUSES: Final = frozenset({"completed"})

_MODERATION_ACTIONS: Final[dict[str, str]] = {
    "approve": "approved",
    "reject": "rejected",
    "remove": "removed",
}


async def create_review(
    db: Database,
    customer: Principal,
    request_id: str,
    *,
    product_id: str,
    order_id: str,
    rating: int,
    title: str | None,
    body: str,
) -> dict[str, Any]:
    """File one review against a product from the caller's own completed order.

    The caller (route) has already resolved `order_id` from a `public_reference`
    it verified belongs to `customer` -- this function trusts that id but still
    re-checks ownership and status itself, since it is the last line of defence
    before a write.
    """
    if not 1 <= rating <= 5:
        raise ValidationAppError("Rating must be between 1 and 5.")
    text = (body or "").strip()
    if len(text) < _MIN_BODY or len(text) > _MAX_BODY:
        raise ValidationAppError(f"Write between {_MIN_BODY} and {_MAX_BODY} characters.")
    clean_title = (title or "").strip()[:_MAX_TITLE] or None

    order = await db.fetch_one(
        "SELECT id, order_status FROM orders WHERE id = ? AND customer_user_id = ?",
        (order_id, customer.user_id),
    )
    if order is None:
        raise NotFoundError("Order not found.")
    if order["order_status"] not in _ELIGIBLE_ORDER_STATUSES:
        raise ConflictError("This order is not eligible for a review yet.")
    item = await db.fetch_one(
        "SELECT 1 FROM order_items WHERE order_id = ? AND product_id = ?",
        (order_id, product_id),
    )
    if item is None:
        raise ValidationAppError("This product was not part of that order.")
    existing = await db.fetch_one(
        "SELECT id FROM reviews WHERE product_id = ? AND customer_user_id = ? AND order_id = ?",
        (product_id, customer.user_id, order_id),
    )
    if existing is not None:
        raise ConflictError("You have already reviewed this product for this order.")

    now = utc_now_iso()
    review_id = new_id("rev")
    await db.batch(
        [
            (
                "INSERT INTO reviews"
                " (id, product_id, customer_user_id, order_id, rating, title, body, status,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)",
                (
                    review_id,
                    product_id,
                    customer.user_id,
                    order_id,
                    rating,
                    clean_title,
                    text,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="review.created",
                entity_type="review",
                entity_id=review_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"productId": product_id, "orderId": order_id, "rating": rating},
            ),
        ]
    )
    return {"id": review_id, "status": "pending"}


async def moderate_review(
    db: Database,
    actor: Principal,
    request_id: str,
    review_id: str,
    *,
    action: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Approve, reject or remove one review. Reversible; the reason and the
    moderator stay on the row so a decision can be explained later."""
    target = _MODERATION_ACTIONS.get(action)
    if target is None:
        raise ValidationAppError("Unsupported moderation action.")
    current = await db.fetch_one("SELECT * FROM reviews WHERE id = ?", (review_id,))
    if current is None:
        raise NotFoundError("Review not found.")
    if current["status"] == target:
        raise ConflictError(f"This review is already {target}.")
    clean_reason = (reason or "").strip()[:_MAX_REASON] or None

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE reviews SET status = ?, moderated_by = ?, moderated_at = ?,"
                " moderation_reason = ?, updated_at = ? WHERE id = ?",
                (target, actor.user_id, now, clean_reason, now, review_id),
            ),
            audit_statement(
                action=f"review.{action}",
                entity_type="review",
                entity_id=review_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": target, "reason": clean_reason},
            ),
        ]
    )
    return {"id": review_id, "status": target}


async def edit_review(
    db: Database, actor: Principal, request_id: str, review_id: str, fields: dict[str, Any]
) -> dict[str, Any]:
    """Staff correction of a review's own content -- typo fixes, redacting a
    stray phone number, that kind of thing. Distinct from `moderate_review`:
    this changes what the review says, never whether it is shown. Only the
    keys present in `fields` are touched, matching the `exclude_unset` idiom
    the rest of the admin surface uses for partial updates.
    """
    current = await db.fetch_one("SELECT * FROM reviews WHERE id = ?", (review_id,))
    if current is None:
        raise NotFoundError("Review not found.")

    rating = current["rating"]
    if "rating" in fields:
        rating = fields["rating"]
        if rating is None or not 1 <= rating <= 5:
            raise ValidationAppError("Rating must be between 1 and 5.")

    title = current["title"]
    if "title" in fields:
        title = (fields["title"] or "").strip()[:_MAX_TITLE] or None

    body = current["body"]
    if "body" in fields:
        raw_body = fields["body"]
        if raw_body is None:
            raise ValidationAppError("Review text cannot be cleared.")
        body = raw_body.strip()
        if len(body) < _MIN_BODY or len(body) > _MAX_BODY:
            raise ValidationAppError(f"Write between {_MIN_BODY} and {_MAX_BODY} characters.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE reviews SET rating = ?, title = ?, body = ?, updated_at = ? WHERE id = ?",
                (rating, title, body, now, review_id),
            ),
            audit_statement(
                action="review.edited",
                entity_type="review",
                entity_id=review_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={
                    "rating": current["rating"],
                    "title": current["title"],
                    "body": current["body"],
                },
                after={"rating": rating, "title": title, "body": body},
            ),
        ]
    )
    return {"id": review_id, "rating": rating, "title": title, "body": body}


async def delete_review(
    db: Database, actor: Principal, request_id: str, review_id: str
) -> dict[str, Any]:
    """Permanent removal. `moderate_review(action="remove")` is the reversible
    option; this one is for content that must not persist at all."""
    current = await db.fetch_one("SELECT id FROM reviews WHERE id = ?", (review_id,))
    if current is None:
        raise NotFoundError("Review not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM reviews WHERE id = ?", (review_id,)),
            audit_statement(
                action="review.deleted",
                entity_type="review",
                entity_id=review_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": review_id, "deleted": True}

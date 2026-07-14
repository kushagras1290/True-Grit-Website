"""Publishing service.

Publishing a category composes, in ONE database batch: the immutable version
row, the entity status swap, the audit record, and the outbox event. If any
statement fails the batch rolls back — a category can never be published
without its audit trail.
"""

from __future__ import annotations

import json

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.workflow import assert_transition
from truegrit_api.errors import NotFoundError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.content import CategoryRepository
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

# Entity-status -> workflow-state equivalent for transition validation (§18.7).
# A published/unpublished category may be republished: the edit that preceded it
# produced approved content, and publishing always creates a NEW immutable version.
_WORKFLOW_EQUIVALENT = {
    "draft": "approved",
    "approved": "approved",
    "scheduled": "scheduled",
    "published": "approved",
    "unpublished": "approved",
}


async def publish_category(
    db: Database,
    categories: CategoryRepository,
    category_id: str,
    actor: Principal,
    request_id: str,
    change_summary: str | None = None,
) -> dict[str, str | int]:
    category = await categories.get_by_id(category_id)
    if category is None:
        raise NotFoundError("Category not found.")

    current_status = category["status"]
    workflow_current = _WORKFLOW_EQUIVALENT.get(current_status, current_status)
    assert_transition("categories", workflow_current, "published", actor.permissions)

    now = utc_now_iso()
    version_number = await categories.next_version_number(category_id)
    version_id = new_id("cav")
    content_json = json.dumps(
        {
            "name": category["name"],
            "slug": category["slug"],
            "hero": {
                "eyebrow": category["hero_eyebrow"],
                "title": category["hero_title"],
                "description": category["hero_description"],
            },
            "product_assignment_mode": category["product_assignment_mode"],
            "product_rule_json": category["product_rule_json"],
        }
    )

    await db.batch(
        [
            (
                "INSERT INTO category_versions"
                " (id, category_id, version_number, content_json, change_summary,"
                "  workflow_state, created_at, created_by, approved_at, approved_by, published_at)"
                " VALUES (?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?)",
                (
                    version_id,
                    category_id,
                    version_number,
                    content_json,
                    change_summary,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                    now,
                ),
            ),
            (
                "UPDATE categories SET status = 'published', published_version_id = ?,"
                " updated_at = ?, updated_by = ? WHERE id = ?",
                (version_id, now, actor.user_id, category_id),
            ),
            (
                "INSERT INTO audit_logs"
                " (id, actor_user_id, action, entity_type, entity_id,"
                "  before_summary_json, after_summary_json, request_id, source, created_at)"
                " VALUES (?, ?, 'category.published', 'category', ?, ?, ?, ?, 'admin', ?)",
                (
                    new_id("aud"),
                    actor.user_id,
                    category_id,
                    json.dumps({"status": current_status}),
                    json.dumps({"status": "published", "version": version_number}),
                    request_id,
                    now,
                ),
            ),
            (
                "INSERT INTO outbox_events"
                " (id, event_type, event_version, aggregate_type, aggregate_id,"
                "  payload_json, status, available_at, created_at)"
                " VALUES (?, 'content.category.published.v1', 1, 'category',"
                "  ?, ?, 'pending', ?, ?)",
                (
                    new_id("evt"),
                    category_id,
                    json.dumps({"categoryId": category_id, "version": version_number}),
                    now,
                    now,
                ),
            ),
        ]
    )

    return {"id": category_id, "status": "published", "version": version_number}


async def publish_product(
    db: Database,
    product_id: str,
    actor: Principal,
    request_id: str,
    change_summary: str | None = None,
) -> dict[str, str | int]:
    """Publish a product: immutable version row, status swap, audit and outbox in
    one batch — mirrors category publishing so the workflow is identical."""
    product = await db.fetch_one(
        "SELECT * FROM products WHERE id = ? AND archived_at IS NULL",
        (product_id,),
    )
    if product is None:
        raise NotFoundError("Product not found.")

    current_status = product["status"]
    workflow_current = _WORKFLOW_EQUIVALENT.get(current_status, current_status)
    assert_transition("products", workflow_current, "published", actor.permissions)

    now = utc_now_iso()
    version_row = await db.fetch_one(
        "SELECT COALESCE(MAX(version_number), 0) AS max_version"
        " FROM product_versions WHERE product_id = ?",
        (product_id,),
    )
    version_number = int(version_row["max_version"]) + 1 if version_row else 1
    version_id = new_id("prv")
    content_json = json.dumps(
        {
            "name": product["name"],
            "slug": product["slug"],
            "short_description": product["short_description"],
            "product_type": product["product_type"],
        }
    )

    await db.batch(
        [
            (
                "INSERT INTO product_versions"
                " (id, product_id, version_number, content_json, change_summary,"
                "  workflow_state, created_at, created_by, approved_at, approved_by, published_at)"
                " VALUES (?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?)",
                (
                    version_id,
                    product_id,
                    version_number,
                    content_json,
                    change_summary,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                    now,
                ),
            ),
            (
                "UPDATE products SET status = 'published', published_version_id = ?,"
                " updated_at = ?, updated_by = ? WHERE id = ?",
                (version_id, now, actor.user_id, product_id),
            ),
            (
                "INSERT INTO audit_logs"
                " (id, actor_user_id, action, entity_type, entity_id,"
                "  before_summary_json, after_summary_json, request_id, source, created_at)"
                " VALUES (?, ?, 'product.published', 'product', ?, ?, ?, ?, 'admin', ?)",
                (
                    new_id("aud"),
                    actor.user_id,
                    product_id,
                    json.dumps({"status": current_status}),
                    json.dumps({"status": "published", "version": version_number}),
                    request_id,
                    now,
                ),
            ),
            (
                "INSERT INTO outbox_events"
                " (id, event_type, event_version, aggregate_type, aggregate_id,"
                "  payload_json, status, available_at, created_at)"
                " VALUES (?, 'content.product.published.v1', 1, 'product',"
                "  ?, ?, 'pending', ?, ?)",
                (
                    new_id("evt"),
                    product_id,
                    json.dumps({"productId": product_id, "version": version_number}),
                    now,
                    now,
                ),
            ),
        ]
    )

    return {"id": product_id, "status": "published", "version": version_number}

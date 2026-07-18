"""Community blog/recipe submissions: signed-in customers pitch a post or a
recipe (`create_submission`, `update_submission`); staff with
`submissions.review` triage it (`decide_submission`: under_review,
changes_requested, approved, or a terminal rejected).

Approval promotes the submission straight into the existing
`articles`/`recipes` tables as **published**, in the same database batch as
the decision -- the community review step already is the editorial review
(confirmed product decision: approval publishes immediately rather than
landing in the staff draft queue), so there is no separate publish step
behind it. A rejected or changes-requested submission never touches
articles/recipes at all.
"""

from __future__ import annotations

import json
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.blocks import validate_blocks
from truegrit_api.domain.slugs import slugify
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_CONTENT_TYPES = frozenset({"article", "recipe"})
_OPEN_STATUSES = frozenset({"submitted", "under_review", "changes_requested"})
_DECISIONS = frozenset({"under_review", "changes_requested", "approved", "rejected"})
_MAX_INGREDIENTS = 40
_MAX_STEPS = 30
_MAX_TAGS = 12
_MIN_TITLE = 5
_MAX_TITLE = 200
_MIN_BODY = 20


def _body_to_blocks(body: str) -> list[dict[str, Any]]:
    """Split submitted plain text into paragraphs and wrap it as one
    rich-text block -- the same content_json shape articles/recipes already
    store, so a promoted submission renders exactly like staff-authored
    content."""
    paragraphs = [p.strip() for p in body.replace("\r\n", "\n").split("\n\n") if p.strip()]
    if not paragraphs:
        raise ValidationAppError("Submission body cannot be empty.")
    block = {
        "id": "body",
        "version": 1,
        "enabled": True,
        "type": "rich_text",
        "props": {"paragraphs": paragraphs},
    }
    validated = validate_blocks([block])
    return [b.model_dump(mode="json", by_alias=True, exclude_none=True) for b in validated]


async def _unique_slug(db: Database, table: str, base: str) -> str:
    slug = base
    suffix = 2
    while await db.fetch_one(f"SELECT id FROM {table} WHERE slug = ?", (slug,)) is not None:
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


def _validate_common_fields(
    *,
    contact_name: str,
    contact_email: str,
    contact_phone: str | None,
    title: str,
    excerpt: str | None,
    body: str,
) -> dict[str, Any]:
    contact_name = contact_name.strip()
    if not contact_name:
        raise ValidationAppError("Contact name is required.")
    contact_email = contact_email.strip().lower()
    if "@" not in contact_email or len(contact_email) > 254:
        raise ValidationAppError("Enter a valid contact email.")
    title = title.strip()
    if len(title) < _MIN_TITLE or len(title) > _MAX_TITLE:
        raise ValidationAppError(f"Title must be between {_MIN_TITLE} and {_MAX_TITLE} characters.")
    body = body.strip()
    if len(body) < _MIN_BODY:
        raise ValidationAppError(f"Write at least {_MIN_BODY} characters.")
    _body_to_blocks(body)  # validates paragraph safety up front
    return {
        "contact_name": contact_name,
        "contact_email": contact_email,
        "contact_phone": (contact_phone or "").strip()[:32] or None,
        "title": title,
        "excerpt": (excerpt or "").strip()[:400] or None,
        "body": body,
    }


def _validate_recipe_fields(
    *,
    prep_minutes: int | None,
    cook_minutes: int | None,
    servings: int | None,
    dietary_tags: list[str] | None,
    ingredients: list[dict[str, Any]] | None,
    steps: list[str] | None,
) -> dict[str, Any]:
    ingredients = ingredients or []
    if len(ingredients) > _MAX_INGREDIENTS:
        raise ValidationAppError(f"A recipe supports at most {_MAX_INGREDIENTS} ingredients.")
    cleaned_ingredients = []
    for entry in ingredients:
        label = str(entry.get("label", "")).strip()
        if not label:
            raise ValidationAppError("Every ingredient needs a label.")
        cleaned_ingredients.append(
            {
                "label": label[:200],
                "quantityText": str(entry.get("quantityText") or "").strip()[:120],
            }
        )
    if not cleaned_ingredients:
        raise ValidationAppError("List at least one ingredient.")

    cleaned_steps = [s.strip() for s in (steps or []) if s.strip()]
    if not cleaned_steps:
        raise ValidationAppError("List at least one preparation step.")
    if len(cleaned_steps) > _MAX_STEPS:
        raise ValidationAppError(f"A recipe supports at most {_MAX_STEPS} steps.")

    tags = [t.strip() for t in (dietary_tags or []) if t.strip()][:_MAX_TAGS]

    for label, value in (
        ("Prep time", prep_minutes),
        ("Cook time", cook_minutes),
        ("Servings", servings),
    ):
        if value is not None and (value < 0 or value > 100_000):
            raise ValidationAppError(f"{label} is out of range.")

    return {
        "prep_minutes": prep_minutes,
        "cook_minutes": cook_minutes,
        "servings": servings,
        "dietary_tags_json": json.dumps(tags),
        "ingredients_json": json.dumps(cleaned_ingredients),
        "steps_json": json.dumps(cleaned_steps),
    }


async def create_submission(
    db: Database,
    customer: Principal,
    request_id: str,
    *,
    content_type: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str | None,
    title: str,
    excerpt: str | None,
    body: str,
    prep_minutes: int | None = None,
    cook_minutes: int | None = None,
    servings: int | None = None,
    dietary_tags: list[str] | None = None,
    ingredients: list[dict[str, Any]] | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    if content_type not in _CONTENT_TYPES:
        raise ValidationAppError("Unsupported submission type.")
    fields = _validate_common_fields(
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        title=title,
        excerpt=excerpt,
        body=body,
    )
    recipe_fields = {
        "prep_minutes": None,
        "cook_minutes": None,
        "servings": None,
        "dietary_tags_json": None,
        "ingredients_json": None,
        "steps_json": None,
    }
    if content_type == "recipe":
        recipe_fields = _validate_recipe_fields(
            prep_minutes=prep_minutes,
            cook_minutes=cook_minutes,
            servings=servings,
            dietary_tags=dietary_tags,
            ingredients=ingredients,
            steps=steps,
        )

    now = utc_now_iso()
    submission_id = new_id("sub")
    await db.batch(
        [
            (
                "INSERT INTO content_submissions"
                " (id, content_type, status, submitter_user_id, contact_name, contact_email,"
                "  contact_phone, title, excerpt, body, prep_minutes, cook_minutes, servings,"
                "  dietary_tags_json, ingredients_json, steps_json, created_at, updated_at)"
                " VALUES (?, ?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    submission_id,
                    content_type,
                    customer.user_id,
                    fields["contact_name"],
                    fields["contact_email"],
                    fields["contact_phone"],
                    fields["title"],
                    fields["excerpt"],
                    fields["body"],
                    recipe_fields["prep_minutes"],
                    recipe_fields["cook_minutes"],
                    recipe_fields["servings"],
                    recipe_fields["dietary_tags_json"],
                    recipe_fields["ingredients_json"],
                    recipe_fields["steps_json"],
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="content_submission.created",
                entity_type="content_submission",
                entity_id=submission_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="storefront",
                after={"contentType": content_type, "title": fields["title"]},
            ),
        ]
    )
    return {"id": submission_id, "status": "submitted"}


async def update_submission(
    db: Database,
    customer: Principal,
    request_id: str,
    submission_id: str,
    *,
    contact_name: str,
    contact_email: str,
    contact_phone: str | None,
    title: str,
    excerpt: str | None,
    body: str,
    prep_minutes: int | None = None,
    cook_minutes: int | None = None,
    servings: int | None = None,
    dietary_tags: list[str] | None = None,
    ingredients: list[dict[str, Any]] | None = None,
    steps: list[str] | None = None,
) -> dict[str, Any]:
    """Let the original submitter revise a submission after changes were
    requested, then resubmit it for another look -- the same record, so
    reviewers see it come back rather than a brand-new pitch."""
    current = await db.fetch_one("SELECT * FROM content_submissions WHERE id = ?", (submission_id,))
    if current is None or current["submitter_user_id"] != customer.user_id:
        raise NotFoundError("Submission not found.")
    if current["status"] != "changes_requested":
        raise ConflictError("Only a submission with requested changes can be edited.")

    fields = _validate_common_fields(
        contact_name=contact_name,
        contact_email=contact_email,
        contact_phone=contact_phone,
        title=title,
        excerpt=excerpt,
        body=body,
    )
    recipe_fields = {
        "prep_minutes": None,
        "cook_minutes": None,
        "servings": None,
        "dietary_tags_json": None,
        "ingredients_json": None,
        "steps_json": None,
    }
    if current["content_type"] == "recipe":
        recipe_fields = _validate_recipe_fields(
            prep_minutes=prep_minutes,
            cook_minutes=cook_minutes,
            servings=servings,
            dietary_tags=dietary_tags,
            ingredients=ingredients,
            steps=steps,
        )

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE content_submissions SET status = 'submitted', contact_name = ?,"
                " contact_email = ?, contact_phone = ?, title = ?, excerpt = ?, body = ?,"
                " prep_minutes = ?, cook_minutes = ?, servings = ?, dietary_tags_json = ?,"
                " ingredients_json = ?, steps_json = ?, reviewer_notes = NULL, updated_at = ?"
                " WHERE id = ?",
                (
                    fields["contact_name"],
                    fields["contact_email"],
                    fields["contact_phone"],
                    fields["title"],
                    fields["excerpt"],
                    fields["body"],
                    recipe_fields["prep_minutes"],
                    recipe_fields["cook_minutes"],
                    recipe_fields["servings"],
                    recipe_fields["dietary_tags_json"],
                    recipe_fields["ingredients_json"],
                    recipe_fields["steps_json"],
                    now,
                    submission_id,
                ),
            ),
            audit_statement(
                action="content_submission.resubmitted",
                entity_type="content_submission",
                entity_id=submission_id,
                actor_id=customer.user_id,
                request_id=request_id,
                created_at=now,
                source="storefront",
                before={"status": current["status"]},
                after={"status": "submitted"},
            ),
        ]
    )
    return {"id": submission_id, "status": "submitted"}


def _promote_to_article(
    current: dict[str, Any], actor: Principal, now: str, slug: str, request_id: str
) -> tuple[str, list[tuple[str, Any]]]:
    article_id = new_id("art")
    version_id = new_id("arv")
    content_json = json.dumps({"blocks": _body_to_blocks(current["body"]), "pullQuote": None})
    statements: list[tuple[str, Any]] = [
        (
            "INSERT INTO articles"
            " (id, internal_name, title, slug, excerpt, author_user_id, status,"
            "  published_version_id, published_at, indexing_policy, created_at, created_by,"
            "  updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?, ?, 'published', ?, ?, 'index', ?, ?, ?, ?)",
            (
                article_id,
                current["title"],
                current["title"],
                slug,
                current["excerpt"],
                current["submitter_user_id"],
                version_id,
                now,
                now,
                actor.user_id,
                now,
                actor.user_id,
            ),
        ),
        (
            "INSERT INTO article_versions"
            " (id, article_id, version_number, content_json, workflow_state, created_at,"
            "  created_by, approved_at, approved_by, published_at)"
            " VALUES (?, ?, 1, ?, 'published', ?, ?, ?, ?, ?)",
            (
                version_id,
                article_id,
                content_json,
                now,
                current["submitter_user_id"],
                now,
                actor.user_id,
                now,
            ),
        ),
        (
            "INSERT INTO audit_logs"
            " (id, actor_user_id, action, entity_type, entity_id,"
            "  before_summary_json, after_summary_json, request_id, source, created_at)"
            " VALUES (?, ?, 'article.published', 'article', ?, NULL, ?, ?, 'admin', ?)",
            (
                new_id("aud"),
                actor.user_id,
                article_id,
                json.dumps({"status": "published"}),
                request_id,
                now,
            ),
        ),
        (
            "INSERT INTO outbox_events"
            " (id, event_type, event_version, aggregate_type, aggregate_id,"
            "  payload_json, status, available_at, created_at)"
            " VALUES (?, 'content.article.published.v1', 1, 'article', ?, ?, 'pending', ?, ?)",
            (new_id("evt"), article_id, json.dumps({"id": article_id, "version": 1}), now, now),
        ),
    ]
    return article_id, statements


def _promote_to_recipe(
    current: dict[str, Any], actor: Principal, now: str, slug: str, request_id: str
) -> tuple[str, list[tuple[str, Any]]]:
    recipe_id = new_id("rcp")
    version_id = new_id("rcv")
    steps = json.loads(current["steps_json"] or "[]")
    content_json = json.dumps({"blocks": _body_to_blocks(current["body"]), "steps": steps})
    statements: list[tuple[str, Any]] = [
        (
            "INSERT INTO recipes"
            " (id, internal_name, title, slug, excerpt, chef_user_id, status,"
            "  published_version_id, published_at, prep_minutes, cook_minutes, servings,"
            "  dietary_tags_json, indexing_policy, created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?, ?, 'published', ?, ?, ?, ?, ?, ?, 'index', ?, ?, ?, ?)",
            (
                recipe_id,
                current["title"],
                current["title"],
                slug,
                current["excerpt"],
                current["submitter_user_id"],
                version_id,
                now,
                current["prep_minutes"],
                current["cook_minutes"],
                current["servings"],
                current["dietary_tags_json"],
                now,
                actor.user_id,
                now,
                actor.user_id,
            ),
        ),
        (
            "INSERT INTO recipe_versions"
            " (id, recipe_id, version_number, content_json, workflow_state, created_at,"
            "  created_by, approved_at, approved_by, published_at)"
            " VALUES (?, ?, 1, ?, 'published', ?, ?, ?, ?, ?)",
            (
                version_id,
                recipe_id,
                content_json,
                now,
                current["submitter_user_id"],
                now,
                actor.user_id,
                now,
            ),
        ),
        (
            "INSERT INTO audit_logs"
            " (id, actor_user_id, action, entity_type, entity_id,"
            "  before_summary_json, after_summary_json, request_id, source, created_at)"
            " VALUES (?, ?, 'recipe.published', 'recipe', ?, NULL, ?, ?, 'admin', ?)",
            (
                new_id("aud"),
                actor.user_id,
                recipe_id,
                json.dumps({"status": "published"}),
                request_id,
                now,
            ),
        ),
        (
            "INSERT INTO outbox_events"
            " (id, event_type, event_version, aggregate_type, aggregate_id,"
            "  payload_json, status, available_at, created_at)"
            " VALUES (?, 'content.recipe.published.v1', 1, 'recipe', ?, ?, 'pending', ?, ?)",
            (new_id("evt"), recipe_id, json.dumps({"id": recipe_id, "version": 1}), now, now),
        ),
    ]
    for index, entry in enumerate(json.loads(current["ingredients_json"] or "[]")):
        statements.append(
            (
                "INSERT INTO recipe_ingredients"
                " (id, recipe_id, label, quantity_text, product_id, sort_order)"
                " VALUES (?, ?, ?, ?, NULL, ?)",
                (
                    new_id("ing"),
                    recipe_id,
                    entry["label"],
                    entry.get("quantityText") or None,
                    index,
                ),
            )
        )
    return recipe_id, statements


async def decide_submission(
    db: Database,
    actor: Principal,
    request_id: str,
    submission_id: str,
    *,
    decision: str,
    note: str | None = None,
) -> dict[str, Any]:
    if decision not in _DECISIONS:
        raise ValidationAppError("Unsupported decision.")
    current = await db.fetch_one("SELECT * FROM content_submissions WHERE id = ?", (submission_id,))
    if current is None:
        raise NotFoundError("Submission not found.")
    if current["status"] not in _OPEN_STATUSES:
        raise ConflictError(f"Cannot move a '{current['status']}' submission to '{decision}'.")
    note = (note or "").strip()[:2000] or None
    if decision in ("changes_requested", "rejected") and not note:
        raise ValidationAppError("A note is required when requesting changes or rejecting.")

    now = utc_now_iso()
    statements: list[tuple[str, Any]] = []
    result: dict[str, Any] = {"id": submission_id, "status": decision}

    if decision == "approved":
        table = "articles" if current["content_type"] == "article" else "recipes"
        slug = await _unique_slug(db, table, slugify(current["title"]))
        if current["content_type"] == "article":
            entity_id, promote_statements = _promote_to_article(
                current, actor, now, slug, request_id
            )
            statements.extend(promote_statements)
            statements.append(
                (
                    "UPDATE content_submissions SET status = 'approved', reviewer_notes = ?,"
                    " reviewed_by = ?, reviewed_at = ?, updated_at = ?, published_article_id = ?"
                    " WHERE id = ?",
                    (note, actor.user_id, now, now, entity_id, submission_id),
                )
            )
        else:
            entity_id, promote_statements = _promote_to_recipe(
                current, actor, now, slug, request_id
            )
            statements.extend(promote_statements)
            statements.append(
                (
                    "UPDATE content_submissions SET status = 'approved', reviewer_notes = ?,"
                    " reviewed_by = ?, reviewed_at = ?, updated_at = ?, published_recipe_id = ?"
                    " WHERE id = ?",
                    (note, actor.user_id, now, now, entity_id, submission_id),
                )
            )
        result["publishedId"] = entity_id
        result["slug"] = slug
    else:
        statements.append(
            (
                "UPDATE content_submissions SET status = ?, reviewer_notes = ?, reviewed_by = ?,"
                " reviewed_at = ?, updated_at = ? WHERE id = ?",
                (decision, note, actor.user_id, now, now, submission_id),
            )
        )

    statements.append(
        audit_statement(
            action=f"content_submission.{decision}",
            entity_type="content_submission",
            entity_id=submission_id,
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            before={"status": current["status"]},
            after={"status": decision, "note": note},
        )
    )
    await db.batch(statements)
    return result

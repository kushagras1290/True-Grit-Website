"""Article (blog) admin authoring and review workflow.

Layering mirrors `services.catalogue`: this module owns business rules and
multi-statement writes; `repositories.content.ArticleRepository` owns reads.
Publishing itself lives in `services.publishing.publish_article` so every
content type's publish mechanics stay in one place.

Ownership scoping: the `blogger` role holds `articles.edit` but not
`articles.approve` — anyone in that position may only touch their own
articles (`author_user_id`). Reviewers (`articles.approve`) see and act on
everyone's. A missing or foreign article always raises NotFound rather than
PermissionDenied so scoped principals can never learn an id exists.
"""

from __future__ import annotations

import json
from typing import Any

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.blocks import validate_blocks
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.domain.workflow import assert_transition
from truegrit_api.errors import ConflictError, NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_METADATA_FIELDS = (
    "title",
    "excerpt",
    "hero_media_id",
    "hero_image_url",
    "hero_image_alt",
    "reading_minutes",
    "seo_title",
    "seo_description",
    "seo_keywords",
    "canonical_url",
    "indexing_policy",
)


def assert_owns_or_reviews(article: dict[str, Any], actor: Principal) -> None:
    if actor.has("articles.approve"):
        return
    if article.get("author_user_id") != actor.user_id:
        raise NotFoundError("Article not found.")


def _dump_blocks(raw_blocks: Any) -> list[dict[str, Any]]:
    validated = validate_blocks(raw_blocks)
    return [block.model_dump(mode="json", by_alias=True, exclude_none=True) for block in validated]


async def create_article(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    title: str,
    slug: str | None = None,
    excerpt: str | None = None,
) -> dict[str, Any]:
    title = title.strip()
    if not title:
        raise ValidationAppError("Title is required.")
    slug_value = validate_slug(slug.strip()) if slug else slugify(title)
    existing = await db.fetch_one("SELECT id FROM articles WHERE slug = ?", (slug_value,))
    if existing is not None:
        raise ValidationAppError("An article with that slug already exists.")

    now = utc_now_iso()
    article_id = new_id("art")
    version_id = new_id("arv")
    await db.batch(
        [
            (
                "INSERT INTO articles"
                " (id, internal_name, title, slug, excerpt, author_user_id, status,"
                "  indexing_policy, created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, 'draft', 'index', ?, ?, ?, ?)",
                (
                    article_id,
                    title,
                    title,
                    slug_value,
                    (excerpt or "").strip() or None,
                    actor.user_id,
                    now,
                    actor.user_id,
                    now,
                    actor.user_id,
                ),
            ),
            (
                "INSERT INTO article_versions"
                " (id, article_id, version_number, content_json, workflow_state,"
                " created_at, created_by)"
                " VALUES (?, ?, 1, ?, 'draft', ?, ?)",
                (version_id, article_id, json.dumps({"blocks": []}), now, actor.user_id),
            ),
            audit_statement(
                action="article.created",
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"title": title, "slug": slug_value},
            ),
        ]
    )
    return {"id": article_id}


async def update_article(
    db: Database,
    actor: Principal,
    request_id: str,
    article_id: str,
    *,
    fields: dict[str, Any],
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if current is None:
        raise NotFoundError("Article not found.")
    assert_owns_or_reviews(current, actor)
    if current["status"] == "archived":
        raise ConflictError("Archived articles cannot be edited.")

    now = utc_now_iso()
    updates: dict[str, Any] = {}
    for key in _METADATA_FIELDS:
        if key in fields:
            updates[key] = fields[key]
    if "indexing_policy" in updates and updates["indexing_policy"] not in ("index", "noindex"):
        raise ValidationAppError("Unsupported indexing policy.")
    if "slug" in fields and fields["slug"] is not None:
        slug_value = validate_slug(fields["slug"].strip())
        existing = await db.fetch_one(
            "SELECT id FROM articles WHERE slug = ? AND id != ?", (slug_value, article_id)
        )
        if existing is not None:
            raise ValidationAppError("An article with that slug already exists.")
        updates["slug"] = slug_value
    if actor.has("articles.approve") and "author_user_id" in fields and fields["author_user_id"]:
        updates["author_user_id"] = fields["author_user_id"]

    statements: list[tuple[str, Any]] = []
    content_changed = "blocks" in fields or "pull_quote" in fields
    if content_changed:
        blocks = _dump_blocks(fields.get("blocks", []))
        content_json = json.dumps({"blocks": blocks, "pullQuote": fields.get("pull_quote")})
        if current["status"] == "published":
            # The live version stays untouched; a new draft version is queued
            # for the next review + publish cycle.
            version_id = new_id("arv")
            next_number_row = await db.fetch_one(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS n"
                " FROM article_versions WHERE article_id = ?",
                (article_id,),
            )
            assert next_number_row is not None  # COALESCE aggregate always returns one row
            statements.append(
                (
                    "INSERT INTO article_versions"
                    " (id, article_id, version_number, content_json, workflow_state,"
                    " created_at, created_by)"
                    " VALUES (?, ?, ?, ?, 'draft', ?, ?)",
                    (
                        version_id,
                        article_id,
                        int(next_number_row["n"]),
                        content_json,
                        now,
                        actor.user_id,
                    ),
                )
            )
        else:
            latest = await db.fetch_one(
                "SELECT id FROM article_versions WHERE article_id = ?"
                " ORDER BY version_number DESC LIMIT 1",
                (article_id,),
            )
            if latest is None:
                raise ConflictError("Article has no version to edit.")
            statements.append(
                (
                    "UPDATE article_versions SET content_json = ? WHERE id = ?",
                    (content_json, latest["id"]),
                )
            )
            # Editing content while awaiting review restarts the review cycle.
            if current["status"] in ("in_review", "approved"):
                updates["status"] = "draft"

    if updates:
        updates["updated_at"] = now
        updates["updated_by"] = actor.user_id
        assignments = ", ".join(f"{key} = ?" for key in updates)
        statements.append(
            (f"UPDATE articles SET {assignments} WHERE id = ?", (*updates.values(), article_id))
        )

    if statements:
        statements.append(
            audit_statement(
                action="article.updated",
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={
                    "status": updates.get("status", current["status"]),
                    "contentChanged": content_changed,
                },
            )
        )
        await db.batch(statements)
    return {"id": article_id}


async def _transition(
    db: Database,
    actor: Principal,
    request_id: str,
    article_id: str,
    *,
    target: str,
    action: str,
    note: str | None = None,
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if current is None:
        raise NotFoundError("Article not found.")
    assert_owns_or_reviews(current, actor)
    assert_transition("articles", current["status"], target, actor.permissions)

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE articles SET status = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                (target, now, actor.user_id, article_id),
            ),
            audit_statement(
                action=action,
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": target, "note": note},
            ),
        ]
    )
    return {"id": article_id, "status": target}


async def submit_article(
    db: Database, actor: Principal, request_id: str, article_id: str
) -> dict[str, Any]:
    return await _transition(
        db, actor, request_id, article_id, target="in_review", action="article.submitted"
    )


async def approve_article(
    db: Database, actor: Principal, request_id: str, article_id: str
) -> dict[str, Any]:
    return await _transition(
        db, actor, request_id, article_id, target="approved", action="article.approved"
    )


async def request_article_changes(
    db: Database, actor: Principal, request_id: str, article_id: str, note: str
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if current is None:
        raise NotFoundError("Article not found.")
    # Validated as a real transition (requires articles.approve) even though
    # the entity status column has no 'changes_requested' value to hold — it
    # collapses straight back to 'draft' for the author to act on.
    assert_transition("articles", current["status"], "changes_requested", actor.permissions)
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE articles SET status = 'draft', updated_at = ?, updated_by = ? WHERE id = ?",
                (now, actor.user_id, article_id),
            ),
            audit_statement(
                action="article.changes_requested",
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "draft", "note": note},
            ),
        ]
    )
    return {"id": article_id, "status": "draft"}


async def unpublish_article(
    db: Database, actor: Principal, request_id: str, article_id: str
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM articles WHERE id = ?", (article_id,))
    if current is None:
        raise NotFoundError("Article not found.")
    if not actor.has("articles.publish"):
        raise NotFoundError("Article not found.")
    if current["status"] != "published":
        raise ConflictError("Only a published article can be unpublished.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE articles SET status = 'unpublished', updated_at = ?, updated_by = ?"
                " WHERE id = ?",
                (now, actor.user_id, article_id),
            ),
            audit_statement(
                action="article.unpublished",
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": "published"},
                after={"status": "unpublished"},
            ),
        ]
    )
    return {"id": article_id, "status": "unpublished"}


async def archive_article(
    db: Database, actor: Principal, request_id: str, article_id: str
) -> dict[str, Any]:
    """Soft-delete, mirroring `services.catalogue.archive_product` — flips
    status to 'archived' and stamps archived_at rather than issuing a SQL
    DELETE, so the post stays recoverable from /archive."""
    current = await db.fetch_one(
        "SELECT id, status, author_user_id FROM articles WHERE id = ? AND archived_at IS NULL",
        (article_id,),
    )
    if current is None:
        raise NotFoundError("Article not found.")
    assert_owns_or_reviews(current, actor)
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE articles SET status = 'archived', archived_at = ?, updated_at = ?,"
                " updated_by = ? WHERE id = ?",
                (now, now, actor.user_id, article_id),
            ),
            audit_statement(
                action="article.archived",
                entity_type="article",
                entity_id=article_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "archived"},
            ),
        ]
    )
    return {"id": article_id, "status": "archived"}

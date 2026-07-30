"""Recipe admin authoring and review workflow.

Mirrors `services.articles` exactly — same layering, same workflow shape —
but recipes keep their structured cooking data (`recipe_ingredients` table,
`steps`) alongside the optional `blocks` intro/story section, rather than
being fully block-based like articles.

Ownership scoping: the `chef` role holds `recipes.edit` but not
`recipes.approve` — anyone in that position may only touch their own recipes
(`chef_user_id`). Reviewers (`recipes.approve`) see and act on everyone's.
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
    "prep_minutes",
    "cook_minutes",
    "servings",
    "hero_media_id",
    "hero_image_url",
    "hero_image_alt",
    "seo_title",
    "seo_description",
    "seo_keywords",
    "canonical_url",
    "indexing_policy",
)
_MAX_INGREDIENTS = 40
_MAX_STEPS = 30


def assert_owns_or_reviews(recipe: dict[str, Any], actor: Principal) -> None:
    if actor.has("recipes.approve"):
        return
    if recipe.get("chef_user_id") != actor.user_id:
        raise NotFoundError("Recipe not found.")


def _dump_blocks(raw_blocks: Any) -> list[dict[str, Any]]:
    validated = validate_blocks(raw_blocks)
    return [block.model_dump(mode="json", by_alias=True, exclude_none=True) for block in validated]


def _validate_steps(steps: Any) -> list[str]:
    if not isinstance(steps, list) or not all(isinstance(s, str) for s in steps):
        raise ValidationAppError("Steps must be a list of text instructions.")
    if len(steps) > _MAX_STEPS:
        raise ValidationAppError(f"A recipe supports at most {_MAX_STEPS} steps.")
    return [s.strip() for s in steps if s.strip()]


async def create_recipe(
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
    existing = await db.fetch_one("SELECT id FROM recipes WHERE slug = ?", (slug_value,))
    if existing is not None:
        raise ValidationAppError("A recipe with that slug already exists.")

    now = utc_now_iso()
    recipe_id = new_id("rcp")
    version_id = new_id("rcv")
    await db.batch(
        [
            (
                "INSERT INTO recipes"
                " (id, internal_name, title, slug, excerpt, chef_user_id, status,"
                "  indexing_policy, created_at, created_by, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?, ?, ?, 'draft', 'index', ?, ?, ?, ?)",
                (
                    recipe_id,
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
                "INSERT INTO recipe_versions"
                " (id, recipe_id, version_number, content_json, workflow_state,"
                " created_at, created_by)"
                " VALUES (?, ?, 1, ?, 'draft', ?, ?)",
                (
                    version_id,
                    recipe_id,
                    json.dumps({"blocks": [], "steps": []}),
                    now,
                    actor.user_id,
                ),
            ),
            audit_statement(
                action="recipe.created",
                entity_type="recipe",
                entity_id=recipe_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"title": title, "slug": slug_value},
            ),
        ]
    )
    return {"id": recipe_id}


async def _replace_ingredients(
    recipe_id: str, ingredients: list[dict[str, Any]]
) -> list[tuple[str, Any]]:
    if len(ingredients) > _MAX_INGREDIENTS:
        raise ValidationAppError(f"A recipe supports at most {_MAX_INGREDIENTS} ingredients.")
    statements: list[tuple[str, Any]] = [
        ("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
    ]
    for index, entry in enumerate(ingredients):
        label = str(entry.get("label", "")).strip()
        if not label:
            raise ValidationAppError("Every ingredient needs a label.")
        statements.append(
            (
                "INSERT INTO recipe_ingredients"
                " (id, recipe_id, label, quantity_text, product_id, sort_order)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    new_id("ing"),
                    recipe_id,
                    label[:200],
                    (str(entry.get("quantity_text") or "").strip() or None),
                    entry.get("product_id") or None,
                    index,
                ),
            )
        )
    return statements


async def update_recipe(
    db: Database,
    actor: Principal,
    request_id: str,
    recipe_id: str,
    *,
    fields: dict[str, Any],
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    if current is None:
        raise NotFoundError("Recipe not found.")
    assert_owns_or_reviews(current, actor)
    if current["status"] == "archived":
        raise ConflictError("Archived recipes cannot be edited.")

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
            "SELECT id FROM recipes WHERE slug = ? AND id != ?", (slug_value, recipe_id)
        )
        if existing is not None:
            raise ValidationAppError("A recipe with that slug already exists.")
        updates["slug"] = slug_value
    if "dietary_tags" in fields and fields["dietary_tags"] is not None:
        updates["dietary_tags_json"] = json.dumps([str(t) for t in fields["dietary_tags"]][:12])
    if actor.has("recipes.approve") and "chef_user_id" in fields and fields["chef_user_id"]:
        updates["chef_user_id"] = fields["chef_user_id"]

    statements: list[tuple[str, Any]] = []
    if "ingredients" in fields and fields["ingredients"] is not None:
        statements.extend(await _replace_ingredients(recipe_id, fields["ingredients"]))

    content_changed = "blocks" in fields or "steps" in fields
    if content_changed:
        blocks = _dump_blocks(fields.get("blocks", []))
        steps = _validate_steps(fields.get("steps", []))
        content_json = json.dumps({"blocks": blocks, "steps": steps})
        if current["status"] == "published":
            version_id = new_id("rcv")
            next_number_row = await db.fetch_one(
                "SELECT COALESCE(MAX(version_number), 0) + 1 AS n"
                " FROM recipe_versions WHERE recipe_id = ?",
                (recipe_id,),
            )
            assert next_number_row is not None  # COALESCE aggregate always returns one row
            statements.append(
                (
                    "INSERT INTO recipe_versions"
                    " (id, recipe_id, version_number, content_json, workflow_state,"
                    " created_at, created_by)"
                    " VALUES (?, ?, ?, ?, 'draft', ?, ?)",
                    (
                        version_id,
                        recipe_id,
                        int(next_number_row["n"]),
                        content_json,
                        now,
                        actor.user_id,
                    ),
                )
            )
        else:
            latest = await db.fetch_one(
                "SELECT id FROM recipe_versions WHERE recipe_id = ?"
                " ORDER BY version_number DESC LIMIT 1",
                (recipe_id,),
            )
            if latest is None:
                raise ConflictError("Recipe has no version to edit.")
            statements.append(
                (
                    "UPDATE recipe_versions SET content_json = ? WHERE id = ?",
                    (content_json, latest["id"]),
                )
            )
            if current["status"] in ("in_review", "approved"):
                updates["status"] = "draft"

    if updates:
        updates["updated_at"] = now
        updates["updated_by"] = actor.user_id
        assignments = ", ".join(f"{key} = ?" for key in updates)
        statements.append(
            (f"UPDATE recipes SET {assignments} WHERE id = ?", (*updates.values(), recipe_id))
        )

    if statements:
        statements.append(
            audit_statement(
                action="recipe.updated",
                entity_type="recipe",
                entity_id=recipe_id,
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
    return {"id": recipe_id}


async def _transition(
    db: Database,
    actor: Principal,
    request_id: str,
    recipe_id: str,
    *,
    target: str,
    action: str,
    note: str | None = None,
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    if current is None:
        raise NotFoundError("Recipe not found.")
    assert_owns_or_reviews(current, actor)
    assert_transition("recipes", current["status"], target, actor.permissions)

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE recipes SET status = ?, updated_at = ?, updated_by = ? WHERE id = ?",
                (target, now, actor.user_id, recipe_id),
            ),
            audit_statement(
                action=action,
                entity_type="recipe",
                entity_id=recipe_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": target, "note": note},
            ),
        ]
    )
    return {"id": recipe_id, "status": target}


async def submit_recipe(
    db: Database, actor: Principal, request_id: str, recipe_id: str
) -> dict[str, Any]:
    return await _transition(
        db, actor, request_id, recipe_id, target="in_review", action="recipe.submitted"
    )


async def approve_recipe(
    db: Database, actor: Principal, request_id: str, recipe_id: str
) -> dict[str, Any]:
    return await _transition(
        db, actor, request_id, recipe_id, target="approved", action="recipe.approved"
    )


async def request_recipe_changes(
    db: Database, actor: Principal, request_id: str, recipe_id: str, note: str
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    if current is None:
        raise NotFoundError("Recipe not found.")
    assert_transition("recipes", current["status"], "changes_requested", actor.permissions)
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE recipes SET status = 'draft', updated_at = ?, updated_by = ? WHERE id = ?",
                (now, actor.user_id, recipe_id),
            ),
            audit_statement(
                action="recipe.changes_requested",
                entity_type="recipe",
                entity_id=recipe_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "draft", "note": note},
            ),
        ]
    )
    return {"id": recipe_id, "status": "draft"}


async def unpublish_recipe(
    db: Database, actor: Principal, request_id: str, recipe_id: str
) -> dict[str, Any]:
    current = await db.fetch_one("SELECT * FROM recipes WHERE id = ?", (recipe_id,))
    if current is None:
        raise NotFoundError("Recipe not found.")
    if not actor.has("recipes.publish"):
        raise NotFoundError("Recipe not found.")
    if current["status"] != "published":
        raise ConflictError("Only a published recipe can be unpublished.")
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE recipes SET status = 'unpublished', updated_at = ?, updated_by = ?"
                " WHERE id = ?",
                (now, actor.user_id, recipe_id),
            ),
            audit_statement(
                action="recipe.unpublished",
                entity_type="recipe",
                entity_id=recipe_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": "published"},
                after={"status": "unpublished"},
            ),
        ]
    )
    return {"id": recipe_id, "status": "unpublished"}

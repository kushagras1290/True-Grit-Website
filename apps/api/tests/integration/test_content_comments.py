"""Reader comments on published blog posts and recipes.

These tests publish their own article and recipe rather than commenting on
seeded ones. The seed's editorial content is periodically replaced wholesale by
migrations (0046 deleted the previous set), and a comment test that breaks
because someone rewrote the demo blog is a test that reports the wrong thing.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from tests.integration.conftest import SESSION_COOKIE, create_session
from truegrit_api.platform.database import SQLiteDatabase

ARTICLE_SLUG = "comment-fixture-article"
RECIPE_SLUG = "comment-fixture-recipe"


@pytest.fixture(autouse=True)
def published_content(db: SQLiteDatabase) -> None:
    """One published article and one published recipe, owned by these tests."""
    db._conn.execute(
        "INSERT INTO articles (id, internal_name, title, slug, excerpt, status,"
        " published_at, created_at, created_by, updated_at, updated_by)"
        " VALUES ('art_cmt_fixture', 'Comment fixture', 'A post worth discussing', ?,"
        " 'Something to talk about.', 'published', '2026-07-20T00:00:00Z',"
        " '2026-07-20T00:00:00Z', 'usr_editor', '2026-07-20T00:00:00Z', 'usr_editor')",
        (ARTICLE_SLUG,),
    )
    db._conn.execute(
        "INSERT INTO recipes (id, internal_name, title, slug, excerpt, status,"
        " published_at, created_at, created_by, updated_at, updated_by)"
        " VALUES ('rcp_cmt_fixture', 'Comment fixture', 'A dish worth discussing', ?,"
        " 'Something to cook.', 'published', '2026-07-20T00:00:00Z',"
        " '2026-07-20T00:00:00Z', 'usr_editor', '2026-07-20T00:00:00Z', 'usr_editor')",
        (RECIPE_SLUG,),
    )
    db._conn.commit()


def as_customer(client: TestClient, db: SQLiteDatabase, user_id: str = "usr_reader") -> None:
    db._conn.execute(
        "INSERT OR IGNORE INTO users"
        " (id, email, display_name, user_type, status, created_at, updated_at)"
        " VALUES (?, ?, ?, 'customer', 'active', '2026-07-01T00:00:00Z', '2026-07-01T00:00:00Z')",
        (user_id, f"{user_id}@example.test", "Priya Sharma"),
    )
    db._conn.commit()
    client.cookies.set(SESSION_COOKIE, create_session(db, user_id))


def as_admin(client: TestClient, db: SQLiteDatabase) -> None:
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_admin"))


def post_comment(client: TestClient, kind: str, slug: str, body: str):
    return client.post(f"/v1/public/content/{kind}/{slug}/comments", json={"body": body})


# --- Reading and writing ----------------------------------------------------


@pytest.mark.parametrize(("kind", "slug"), [("article", ARTICLE_SLUG), ("recipe", RECIPE_SLUG)])
def test_a_customer_comments_and_everyone_can_read_it(
    client: TestClient, db: SQLiteDatabase, kind: str, slug: str
):
    as_customer(client, db)
    created = post_comment(client, kind, slug, "We grow the same millet in Karnataka.")
    assert created.status_code == 200, created.text

    # Reads are public: drop the session and the thread is still there.
    client.cookies.clear()
    listed = client.get(f"/v1/public/content/{kind}/{slug}/comments")
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    assert body["enabled"] is True
    assert body["items"][0]["authorName"] == "Priya Sharma"
    assert body["items"][0]["body"].startswith("We grow")


def test_commenting_requires_a_signed_in_customer(client: TestClient):
    assert post_comment(client, "article", ARTICLE_SLUG, "Anonymous thoughts").status_code == 401


def test_comments_are_ordered_oldest_first(client: TestClient, db: SQLiteDatabase):
    """A conversation is read top to bottom, unlike the moderation queue."""
    as_customer(client, db, "usr_reader_a")
    post_comment(client, "article", ARTICLE_SLUG, "First thing said.")
    as_customer(client, db, "usr_reader_b")
    post_comment(client, "article", ARTICLE_SLUG, "Second thing said.")

    items = client.get(f"/v1/public/content/article/{ARTICLE_SLUG}/comments").json()["items"]
    assert [item["body"] for item in items] == ["First thing said.", "Second thing said."]


def test_a_comment_cannot_be_attached_to_unpublished_or_unknown_content(
    client: TestClient, db: SQLiteDatabase
):
    """A comment on a draft would go live the instant the draft did, unseen."""
    db._conn.execute("UPDATE articles SET status = 'draft' WHERE slug = ?", (ARTICLE_SLUG,))
    db._conn.commit()
    as_customer(client, db)

    assert post_comment(client, "article", ARTICLE_SLUG, "Sneaking in early.").status_code == 404
    assert post_comment(client, "article", "no-such-post", "Nowhere at all.").status_code == 404
    # The discriminator is validated too — no third content type exists.
    assert post_comment(client, "product", RECIPE_SLUG, "Wrong kind entirely.").status_code == 404


@pytest.mark.parametrize("body", ["", "x", "y" * 4001])
def test_comment_length_is_bounded(client: TestClient, db: SQLiteDatabase, body: str):
    as_customer(client, db)
    assert post_comment(client, "article", ARTICLE_SLUG, body).status_code == 422


def test_comments_can_be_closed_site_wide(client: TestClient, db: SQLiteDatabase):
    """Closing comments must not hide the conversation that already happened —
    the switch stops new ones, the thread stays readable."""
    as_customer(client, db)
    post_comment(client, "article", ARTICLE_SLUG, "Said while the doors were open.")

    db._conn.execute("UPDATE app_settings SET value = '0' WHERE key = 'content_comments.enabled'")
    db._conn.commit()

    assert post_comment(client, "article", ARTICLE_SLUG, "Said too late.").status_code == 403
    listed = client.get(f"/v1/public/content/article/{ARTICLE_SLUG}/comments").json()
    assert listed["enabled"] is False
    assert listed["total"] == 1


# --- Moderation -------------------------------------------------------------


def test_staff_hide_restore_and_delete(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    comment_id = post_comment(client, "recipe", RECIPE_SLUG, "Not a kind word.").json()["id"]

    as_admin(client, db)
    queue = client.get("/v1/admin/content-comments").json()
    assert queue["total"] == 1
    assert queue["items"][0]["parentSlug"] == RECIPE_SLUG
    assert queue["items"][0]["contentType"] == "recipe"

    hidden = client.post(
        f"/v1/admin/content-comments/{comment_id}/moderate",
        json={"action": "hide", "reason": "Abusive."},
    )
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "hidden"
    # Hiding is immediate on the public thread.
    assert client.get(f"/v1/public/content/recipe/{RECIPE_SLUG}/comments").json()["total"] == 0
    # And it is idempotent-refusing rather than silently re-applying.
    assert (
        client.post(
            f"/v1/admin/content-comments/{comment_id}/moderate", json={"action": "hide"}
        ).status_code
        == 409
    )

    client.post(f"/v1/admin/content-comments/{comment_id}/moderate", json={"action": "restore"})
    assert client.get(f"/v1/public/content/recipe/{RECIPE_SLUG}/comments").json()["total"] == 1

    assert client.delete(f"/v1/admin/content-comments/{comment_id}").status_code == 200
    assert client.get("/v1/admin/content-comments").json()["total"] == 0


def test_moderation_is_permission_gated(client: TestClient, db: SQLiteDatabase):
    as_customer(client, db)
    comment_id = post_comment(client, "article", ARTICLE_SLUG, "Perfectly fine.").json()["id"]

    # Content Editor can draft articles but does not police the community.
    client.cookies.set(SESSION_COOKIE, create_session(db, "usr_editor"))
    assert client.get("/v1/admin/content-comments").status_code == 403
    assert (
        client.post(
            f"/v1/admin/content-comments/{comment_id}/moderate", json={"action": "hide"}
        ).status_code
        == 403
    )


def test_deleting_a_post_takes_its_comments_with_it(client: TestClient, db: SQLiteDatabase):
    """The foreign key is a real one, so a removed post leaves no orphans."""
    as_customer(client, db)
    post_comment(client, "article", ARTICLE_SLUG, "Attached to this post.")

    db._conn.execute("PRAGMA foreign_keys = ON")
    db._conn.execute("DELETE FROM articles WHERE slug = ?", (ARTICLE_SLUG,))
    db._conn.commit()

    remaining = db._conn.execute("SELECT COUNT(*) AS total FROM content_comments").fetchone()
    assert remaining["total"] == 0

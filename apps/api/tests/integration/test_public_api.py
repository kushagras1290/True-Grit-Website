from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from truegrit_api.platform.database import SQLiteDatabase

# ---------------------------------------------------------------------------
# Synthetic public-catalogue fixture
#
# Migration 0095 retires the old demo catalogue -- both the hand-authored
# five-product set (migration 0059) and the later bulk-generated ~1500
# product taxonomy (migration 0056/0058) -- from every database it touches,
# unconditionally: products/categories are archived (not deleted, so their
# ids/slugs stay taken), farms are deleted outright, and recipes/articles are
# deleted then replaced by 0095's own real editorial content. This module
# never resurrects any of that retired data and never reuses its ids, slugs
# or names (see `_revenue_baseline` in test_revenue.py for the established
# pattern this follows). Every id below carries an obviously-synthetic
# `_pub_` marker; every slug is prefixed `test-` where the equivalent demo
# slug (e.g. "fruits", "fresh-fruits", "grains-and-millets") is still taken
# by an archived row and would collide on the UNIQUE constraint.
#
# Recipes, articles and discussions are *not* emptied by 0095 the way
# products/categories/farms are -- a fresh database already carries real
# editorial content and (for discussions) real community threads. Rather than
# hard-code a production content volume that is free to keep growing, this
# fixture records each table's baseline count before adding its own rows
# (all dated visibly later than anything already seeded), and returns the
# baselines so a test can compute an exact total/pagination boundary without
# depending on how much real content happens to exist today.
# ---------------------------------------------------------------------------

DEPARTMENT_ID = "cat_pub_fruits"
DEPARTMENT_SLUG = "test-fruits"
DEPARTMENT_NAME = "Fresh Fruits"

SECTIONS = [
    {
        "key": "tropical",
        "id": "cat_pub_tropical",
        "slug": "test-tropical-fruits",
        "name": "Tropical Fruits",
        "sort_order": 1,
    },
    {
        "key": "citrus",
        "id": "cat_pub_citrus",
        "slug": "test-citrus-fruits",
        "name": "Citrus Fruits",
        "sort_order": 2,
    },
    {
        "key": "berries",
        "id": "cat_pub_berries",
        "slug": "test-berries-small-fruits",
        "name": "Berries & Small Fruits",
        "sort_order": 3,
    },
    {
        "key": "melons",
        "id": "cat_pub_melons",
        "slug": "test-melons-orchard-fruits",
        "name": "Melons & Orchard Fruits",
        "sort_order": 4,
    },
]
PRODUCTS_PER_SECTION = 8

VEGETABLES_DEPARTMENT_ID = "cat_pub_vegetables"
VEGETABLES_DEPARTMENT_SLUG = "test-vegetables"
VEGETABLES_DEPARTMENT_NAME = "Test Vegetables Department"

FRESH_FRUITS_CATEGORY_ID = "cat_pub_ff"
FRESH_FRUITS_CATEGORY_SLUG = "test-fresh-fruits"
FRESH_FRUITS_CATEGORY_NAME = "Test Fresh Fruits"
FRESH_FRUITS_HERO_TITLE = "Test fruit, honestly labeled"

GRAINS_CATEGORY_ID = "cat_pub_grains"
GRAINS_CATEGORY_SLUG = "test-grains-millets"
GRAINS_CATEGORY_NAME = "Test Grains and Millets"

FARM_1_ID, FARM_1_SLUG, FARM_1_NAME = "farm_pub_1", "test-farm-one", "Test Farm One"
FARM_2_ID, FARM_2_SLUG, FARM_2_NAME = "farm_pub_2", "test-farm-two", "Test Farm Two"

PRODUCT_A_ID = "prd_pub_a"
PRODUCT_A_SLUG = "test-fresh-fruit-a"
PRODUCT_A_NAME = "Test Fresh Fruit A"
PRODUCT_A_LEAD_PRICE_MINOR = 89_900

PRODUCT_B_ID = "prd_pub_b"
PRODUCT_B_SLUG = "test-fresh-fruit-b"

PRODUCT_C_ID = "prd_pub_c"
PRODUCT_C_SLUG = "test-grain-product-c"
PRODUCT_C_SEARCH_TERM = "sprouted"

PRODUCT_D_ID = "prd_pub_d"
PRODUCT_D_SLUG = "test-grain-product-d"
PRODUCT_D_SEARCH_TERM = "heirloom"
PRODUCT_D_SEARCH_PHRASE = "heirloom bean blend"

PRODUCT_E_ID = "prd_pub_e"
PRODUCT_E_SLUG = "test-fresh-fruit-e"

RECIPE_COUNT = 15
ARTICLE_COUNT = 15
DISCUSSION_COUNT = 15

FEATURED_RECIPE_SLUG = "test-featured-recipe"
FEATURED_ARTICLE_SLUG = "test-featured-article"
FEATURED_ARTICLE_TITLE = "How to compare test fixtures without losing the plot"
FEATURED_DISCUSSION_ID = "dsc_pub_featured"

ANNOUNCEMENT_MESSAGE = "Test season alert for the public API fixture."
ANNOUNCEMENT_PATH = "/seasonal"

_NOW = "2026-08-10T00:00:00Z"
_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def _restrict_product(db: SQLiteDatabase, product_id: str, countries: list[str]) -> None:
    """Seed helper: limit a product's release to the given countries."""
    db._conn.execute("UPDATE products SET release_scope = 'selected' WHERE id = ?", (product_id,))
    for code in countries:
        db._conn.execute(
            "INSERT INTO product_release_countries (product_id, country_code, added_at, added_by)"
            " VALUES (?, ?, '2026-07-16T00:00:00Z', 'usr_admin')",
            (product_id, code),
        )
    db._conn.commit()


def _insert_category(
    db: SQLiteDatabase,
    *,
    id_: str,
    name: str,
    slug: str,
    parent_id: str | None,
    level: int,
    sort_order: int,
    hero_title: str | None = None,
) -> None:
    db._conn.execute(
        "INSERT INTO categories (id, internal_name, name, slug, parent_id, path, level,"
        " sort_order, status, visibility, product_assignment_mode, hero_title,"
        " created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'published', 'public', 'manual', ?, ?, 'usr_admin', ?,"
        " 'usr_admin')",
        (id_, name, name, slug, parent_id, f"/{slug}", level, sort_order, hero_title, _NOW, _NOW),
    )


def _insert_product(
    db: SQLiteDatabase,
    *,
    id_: str,
    name: str,
    slug: str,
    farm_id: str,
    short_description: str = "",
) -> None:
    db._conn.execute(
        "INSERT INTO products (id, internal_name, name, slug, product_type, farm_id, status,"
        " short_description, created_at, created_by, updated_at, updated_by)"
        " VALUES (?, ?, ?, ?, 'grocery', ?, 'published', ?, ?, 'usr_admin', ?, 'usr_admin')",
        (id_, name, name, slug, farm_id, short_description, _NOW, _NOW),
    )


def _insert_variant(
    db: SQLiteDatabase,
    *,
    id_: str,
    product_id: str,
    name: str,
    sku: str,
    list_minor: int,
    sale_minor: int | None = None,
    sort_order: int = 0,
) -> None:
    db._conn.execute(
        "INSERT INTO product_variants (id, product_id, sku, name, status, sort_order,"
        " created_at, updated_at) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)",
        (id_, product_id, sku, name, sort_order, _NOW, _NOW),
    )
    db._conn.execute(
        "INSERT INTO variant_prices (id, variant_id, market_code, currency_code,"
        " list_amount_minor, sale_amount_minor, status, created_at, created_by)"
        " VALUES (?, ?, 'IN', 'INR', ?, ?, 'active', ?, 'usr_admin')",
        (f"vp_{id_}", id_, list_minor, sale_minor, _NOW),
    )
    # 50 on hand against a reorder threshold of 5 -- comfortably `in_stock`
    # (see `domain.inventory.availability_label`).
    db._conn.execute(
        "INSERT INTO inventory_levels (variant_id, location_id, on_hand, reserved,"
        " reorder_threshold, version, updated_at) VALUES (?, 'loc_mumbai', 50, 0, 5, 1, ?)",
        (id_, _NOW),
    )


def _link_product_category(
    db: SQLiteDatabase,
    product_id: str,
    category_id: str,
    *,
    is_primary: int = 1,
    sort_order: int = 0,
) -> None:
    db._conn.execute(
        "INSERT INTO product_categories (product_id, category_id, is_primary, sort_order,"
        " assigned_at, assigned_by) VALUES (?, ?, ?, ?, ?, 'usr_admin')",
        (product_id, category_id, is_primary, sort_order, _NOW),
    )


def _tag_product(db: SQLiteDatabase, product_id: str, tag_id: str) -> None:
    db._conn.execute(
        "INSERT INTO product_tags (product_id, tag_id) VALUES (?, ?)", (product_id, tag_id)
    )


def _certify_product(db: SQLiteDatabase, product_id: str, certification_id: str) -> None:
    db._conn.execute(
        "INSERT INTO product_certifications (product_id, certification_id, claim_review_state)"
        " VALUES (?, ?, 'approved')",
        (product_id, certification_id),
    )


def _insert_farms(db: SQLiteDatabase) -> None:
    for farm_id, name, slug in (
        (FARM_1_ID, FARM_1_NAME, FARM_1_SLUG),
        (FARM_2_ID, FARM_2_NAME, FARM_2_SLUG),
    ):
        db._conn.execute(
            "INSERT INTO farms (id, name, slug, country_code, status, story_json,"
            " created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, 'IN', 'published', ?, ?, 'usr_admin', ?, 'usr_admin')",
            (
                farm_id,
                name,
                slug,
                json.dumps({"summary": f"{name} synthetic test summary."}),
                _NOW,
                _NOW,
            ),
        )


def _insert_department_and_flat_categories(db: SQLiteDatabase) -> None:
    _insert_category(
        db,
        id_=DEPARTMENT_ID,
        name=DEPARTMENT_NAME,
        slug=DEPARTMENT_SLUG,
        parent_id=None,
        level=0,
        sort_order=101,
    )
    for section in SECTIONS:
        _insert_category(
            db,
            id_=section["id"],
            name=section["name"],
            slug=section["slug"],
            parent_id=DEPARTMENT_ID,
            level=1,
            sort_order=section["sort_order"],
        )
    # Independent second department, deliberately childless -- only needed to
    # prove departments sort before their own sections and stay contiguous
    # when interleaved with another branch (sort_order is only meaningful
    # among siblings).
    _insert_category(
        db,
        id_=VEGETABLES_DEPARTMENT_ID,
        name=VEGETABLES_DEPARTMENT_NAME,
        slug=VEGETABLES_DEPARTMENT_SLUG,
        parent_id=None,
        level=0,
        sort_order=102,
    )
    _insert_category(
        db,
        id_=FRESH_FRUITS_CATEGORY_ID,
        name=FRESH_FRUITS_CATEGORY_NAME,
        slug=FRESH_FRUITS_CATEGORY_SLUG,
        parent_id=None,
        level=0,
        sort_order=103,
        hero_title=FRESH_FRUITS_HERO_TITLE,
    )
    _insert_category(
        db,
        id_=GRAINS_CATEGORY_ID,
        name=GRAINS_CATEGORY_NAME,
        slug=GRAINS_CATEGORY_SLUG,
        parent_id=None,
        level=0,
        sort_order=104,
    )


def _insert_section_products(db: SQLiteDatabase) -> None:
    """8 published products per section (32 total), each linked to both its
    section and the department -- the department's own product filter joins
    on `product_categories` directly, so covering all four sections requires
    every product to carry a department-level row too."""
    for section in SECTIONS:
        section_word = section["name"].split()[0]
        for i in range(1, PRODUCTS_PER_SECTION + 1):
            product_id = f"prd_pub_{section['key']}_{i}"
            slug = f"test-{section['key']}-fruit-{i}"
            name = f"Test {section_word} Fruit {i}"
            farm_id = FARM_1_ID if i % 2 == 0 else FARM_2_ID
            _insert_product(db, id_=product_id, name=name, slug=slug, farm_id=farm_id)
            variant_id = f"var_pub_{section['key']}_{i}"
            _insert_variant(
                db,
                id_=variant_id,
                product_id=product_id,
                name="Standard pack",
                sku=f"TST-{section['key'].upper()}-{i}",
                list_minor=9_900 + i * 100,
            )
            _link_product_category(db, product_id, section["id"], is_primary=1, sort_order=i)
            _link_product_category(db, product_id, DEPARTMENT_ID, is_primary=0, sort_order=i)


def _insert_diet_and_certification_products(db: SQLiteDatabase) -> None:
    """Five products (A-E) exercising the diet/certification facets. Exact
    membership (re-derived straight from this file's own assertions before
    they were rewritten):
      - vegan: {A, B, C, D, E} -- all five.
      - pgs-india: {A, B, C, E} -- everything except D.
      - india-organic: {A, D} -- only these two.
    """
    _insert_product(
        db,
        id_=PRODUCT_A_ID,
        name=PRODUCT_A_NAME,
        slug=PRODUCT_A_SLUG,
        farm_id=FARM_1_ID,
        short_description="Synthetic flagship fruit product used to test filters and detail pages.",
    )
    _insert_variant(
        db,
        id_="var_pub_a_1",
        product_id=PRODUCT_A_ID,
        name="Fresh pack",
        sku="TGP-A-FRESH",
        list_minor=PRODUCT_A_LEAD_PRICE_MINOR,
        sort_order=0,
    )
    _insert_variant(
        db,
        id_="var_pub_a_2",
        product_id=PRODUCT_A_ID,
        name="250 g small pack",
        sku="TGP-A-250G",
        list_minor=29_900,
        sale_minor=24_900,
        sort_order=1,
    )
    _insert_variant(
        db,
        id_="var_pub_a_3",
        product_id=PRODUCT_A_ID,
        name="1000 g family pack",
        sku="TGP-A-1000G",
        list_minor=99_900,
        sort_order=2,
    )
    _link_product_category(db, PRODUCT_A_ID, FRESH_FRUITS_CATEGORY_ID)
    for tag_id in ("tag_vegan", "tag_vegetarian", "tag_gluten_free"):
        _tag_product(db, PRODUCT_A_ID, tag_id)
    _certify_product(db, PRODUCT_A_ID, "cert_india_organic")
    _certify_product(db, PRODUCT_A_ID, "cert_pgs_india")

    _insert_product(
        db,
        id_=PRODUCT_B_ID,
        name="Test Fresh Fruit B",
        slug=PRODUCT_B_SLUG,
        farm_id=FARM_2_ID,
        short_description="Synthetic fruit product used to round out diet/certification filters.",
    )
    _insert_variant(
        db,
        id_="var_pub_b_1",
        product_id=PRODUCT_B_ID,
        name="Standard pack",
        sku="TGP-B-STD",
        list_minor=5_900,
    )
    _tag_product(db, PRODUCT_B_ID, "tag_vegan")
    _certify_product(db, PRODUCT_B_ID, "cert_pgs_india")

    _insert_product(
        db,
        id_=PRODUCT_C_ID,
        name="Test Grain Product C",
        slug=PRODUCT_C_SLUG,
        farm_id=FARM_1_ID,
        short_description="Coarse, stone-milled and sprouted grain flour used for search testing.",
    )
    _insert_variant(
        db,
        id_="var_pub_c_1",
        product_id=PRODUCT_C_ID,
        name="Standard pack",
        sku="TGP-C-STD",
        list_minor=6_900,
    )
    _link_product_category(db, PRODUCT_C_ID, GRAINS_CATEGORY_ID, sort_order=1)
    _tag_product(db, PRODUCT_C_ID, "tag_vegan")
    _certify_product(db, PRODUCT_C_ID, "cert_pgs_india")

    _insert_product(
        db,
        id_=PRODUCT_D_ID,
        name="Test Grain Product D",
        slug=PRODUCT_D_SLUG,
        farm_id=FARM_2_ID,
        short_description="A hearty heirloom bean blend used for search testing.",
    )
    _insert_variant(
        db,
        id_="var_pub_d_1",
        product_id=PRODUCT_D_ID,
        name="Standard pack",
        sku="TGP-D-STD",
        list_minor=7_900,
    )
    _link_product_category(db, PRODUCT_D_ID, GRAINS_CATEGORY_ID, sort_order=2)
    _tag_product(db, PRODUCT_D_ID, "tag_vegan")
    _certify_product(db, PRODUCT_D_ID, "cert_india_organic")

    _insert_product(
        db,
        id_=PRODUCT_E_ID,
        name="Test Fresh Fruit E",
        slug=PRODUCT_E_SLUG,
        farm_id=FARM_1_ID,
        short_description="Synthetic fruit product used to round out diet/certification filters.",
    )
    _insert_variant(
        db,
        id_="var_pub_e_1",
        product_id=PRODUCT_E_ID,
        name="Standard pack",
        sku="TGP-E-STD",
        list_minor=8_900,
    )
    _tag_product(db, PRODUCT_E_ID, "tag_vegan")
    _certify_product(db, PRODUCT_E_ID, "cert_pgs_india")


def _insert_recipes(db: SQLiteDatabase) -> int:
    """Returns the published-recipe count that existed before this call."""
    baseline = db._conn.execute(
        "SELECT COUNT(*) AS n FROM recipes WHERE status = 'published'"
    ).fetchone()["n"]
    for i in range(1, RECIPE_COUNT + 1):
        featured = i == 1
        recipe_id = "rcp_pub_featured" if featured else f"rcp_pub_{i:02d}"
        slug = FEATURED_RECIPE_SLUG if featured else f"test-recipe-{i:02d}"
        title = "Test Featured Recipe" if featured else f"Test Recipe {i:02d}"
        published_at = f"2026-08-10T00:{i:02d}:00Z"
        version_id = f"{recipe_id}_v1"
        steps = (
            [f"Featured step {n}." for n in range(1, 7)]
            if featured
            else ["Mix the ingredients.", "Cook and serve."]
        )
        content = json.dumps({"steps": steps, "blocks": []})
        db._conn.execute(
            "INSERT INTO recipes (id, internal_name, title, slug, excerpt, prep_minutes,"
            " cook_minutes, servings, dietary_tags_json, status, published_version_id,"
            " published_at, created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?, 10, 20, 4, '[]', 'published', ?, ?, ?, 'usr_admin', ?,"
            " 'usr_admin')",
            (
                recipe_id,
                title,
                title,
                slug,
                f"{title} excerpt.",
                version_id,
                published_at,
                published_at,
                published_at,
            ),
        )
        db._conn.execute(
            "INSERT INTO recipe_versions (id, recipe_id, version_number, content_json,"
            " workflow_state, created_at, created_by) VALUES (?, ?, 1, ?, 'published', ?,"
            " 'usr_admin')",
            (version_id, recipe_id, content, published_at),
        )
        if featured:
            ingredients = [
                ("Test grain product C", "200 g", PRODUCT_C_ID),
                *[(f"Test ingredient {n}", "1 unit", None) for n in range(2, 7)],
            ]
            for n, (label, quantity_text, product_id) in enumerate(ingredients, start=1):
                db._conn.execute(
                    "INSERT INTO recipe_ingredients (id, recipe_id, label, quantity_text,"
                    " product_id, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                    (f"{recipe_id}_ing_{n}", recipe_id, label, quantity_text, product_id, n),
                )
    return baseline


def _insert_articles(db: SQLiteDatabase) -> int:
    """Returns the published-article count that existed before this call."""
    baseline = db._conn.execute(
        "SELECT COUNT(*) AS n FROM articles WHERE status = 'published'"
    ).fetchone()["n"]
    for i in range(1, ARTICLE_COUNT + 1):
        featured = i == 1
        article_id = "art_pub_featured" if featured else f"art_pub_{i:02d}"
        slug = FEATURED_ARTICLE_SLUG if featured else f"test-article-{i:02d}"
        title = FEATURED_ARTICLE_TITLE if featured else f"Test Article {i:02d}"
        published_at = f"2026-08-10T00:{i:02d}:00Z"
        version_id = f"{article_id}_v1"
        # Alternate authors across every row (not just the featured one) so
        # any 10-item slice of the 15 -- whichever order `published_at DESC`
        # happens to produce -- still carries at least two distinct names.
        author_user_id = "usr_editor" if i % 2 == 0 else None
        if featured:
            blocks = [
                {
                    "type": "faq",
                    "enabled": True,
                    "props": {
                        "items": [
                            {"question": f"Test question {n}?", "answer": f"Test answer {n}."}
                            for n in range(1, 6)
                        ]
                    },
                }
            ]
        else:
            blocks = []
        content = json.dumps({"blocks": blocks})
        db._conn.execute(
            "INSERT INTO articles (id, internal_name, title, slug, excerpt, author_user_id,"
            " reading_minutes, status, published_version_id, published_at, created_at,"
            " created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, ?, ?, 4, 'published', ?, ?, ?, 'usr_admin', ?, 'usr_admin')",
            (
                article_id,
                title,
                title,
                slug,
                f"{title} excerpt.",
                author_user_id,
                version_id,
                published_at,
                published_at,
                published_at,
            ),
        )
        db._conn.execute(
            "INSERT INTO article_versions (id, article_id, version_number, content_json,"
            " workflow_state, created_at, created_by) VALUES (?, ?, 1, ?, 'published', ?,"
            " 'usr_admin')",
            (version_id, article_id, content, published_at),
        )
    return baseline


def _insert_discussions(db: SQLiteDatabase) -> int:
    """Returns the visible-discussion count that existed before this call."""
    baseline = db._conn.execute(
        "SELECT COUNT(*) AS n FROM discussions WHERE status = 'visible'"
    ).fetchone()["n"]
    long_body = " ".join(
        f"This is filler sentence number {n} for the fixture discussion body." for n in range(1, 9)
    )
    # Anchored to the newest thread the migrations actually ship rather than to
    # a literal date. This batch has to dominate page one of
    # `ORDER BY last_activity_at DESC`, and every content migration that adds
    # threads moves that goalpost -- migration 0102 moved it from 2026-08-02 to
    # 2026-08-12 and broke the hard-coded date that used to live here.
    newest = db._conn.execute(
        "SELECT MAX(last_activity_at) AS newest FROM discussions WHERE status = 'visible'"
    ).fetchone()["newest"]
    anchor = (
        datetime.strptime(newest, _TIMESTAMP_FORMAT).replace(tzinfo=timezone.utc)
        if newest
        else datetime(2026, 1, 1, tzinfo=timezone.utc)
    ) + timedelta(days=1)
    for i in range(1, DISCUSSION_COUNT + 1):
        featured = i == 1
        discussion_id = FEATURED_DISCUSSION_ID if featured else f"dsc_pub_{i:02d}"
        title = "Test Featured Discussion" if featured else f"Test Discussion {i:02d}"
        body = long_body if featured else f"Test discussion body number {i}."
        last_activity_at = (anchor + timedelta(minutes=i)).strftime(_TIMESTAMP_FORMAT)
        db._conn.execute(
            "INSERT INTO discussions (id, author_user_id, title, body, status, comment_count,"
            " last_activity_at, created_at, updated_at) VALUES (?, 'usr_admin', ?, ?, 'visible',"
            " 0, ?, ?, ?)",
            (discussion_id, title, body, last_activity_at, last_activity_at, last_activity_at),
        )
    return baseline


def _update_announcement(db: SQLiteDatabase) -> None:
    """`announcements.country` is UNIQUE and a fresh database already carries
    exactly one row (country='global'); `active_announcement()` reads
    whichever active row was updated most recently regardless of country, so
    updating that one row in place is enough to make it the answer."""
    db._conn.execute(
        "UPDATE announcements SET message = ?, destination_path = ?, active = 1, updated_at = ?"
        " WHERE country = 'global'",
        (ANNOUNCEMENT_MESSAGE, ANNOUNCEMENT_PATH, _NOW),
    )


@pytest.fixture(autouse=True)
def public_catalogue_baseline(db: SQLiteDatabase) -> dict[str, int]:
    """Builds the small, obviously-synthetic public catalogue every test in
    this module reads from -- see the module docstring for why this exists
    and how it avoids both resurrecting the retired demo catalogue and
    hard-coding the live editorial library's ever-changing content volume.

    Returns each content table's baseline count (before this fixture's own
    rows), so a test needing an exact total or pagination boundary can add
    its own constant delta (`RECIPE_COUNT`, `ARTICLE_COUNT`,
    `DISCUSSION_COUNT`) rather than assume a specific production volume.
    """
    _insert_farms(db)
    _insert_department_and_flat_categories(db)
    _insert_section_products(db)
    _insert_diet_and_certification_products(db)
    _update_announcement(db)
    baselines = {
        "recipes": _insert_recipes(db),
        "articles": _insert_articles(db),
        "discussions": _insert_discussions(db),
    }
    db._conn.commit()
    return baselines


def test_health(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_bootstrap_navigation_and_announcement(client: TestClient):
    body = client.get("/v1/public/bootstrap").json()
    labels = [item["label"] for item in body["navigation"]]
    assert labels == ["Shop", "Seasonal", "Farmers", "Recipes", "Blog", "Our Standards"]
    assert body["navigation"][1]["path"] == "/seasonal"
    assert [item["path"] for item in body["footerNavigation"]] == [
        "/about",
        "/delivery",
        "/returns",
        "/contact",
        "/privacy",
        "/terms",
        "/help",
    ]
    assert body["announcement"]["message"].startswith("Test season alert")
    assert body["announcement"]["path"] == ANNOUNCEMENT_PATH


def test_home_returns_published_blocks_only(client: TestClient):
    body = client.get("/v1/public/home").json()
    types = [block["type"] for block in body["blocks"]]
    hero = body["blocks"][0]
    assert types[0] == "hero"
    # Migration 0095's live-catalogue relaunch replaced the twelve-image
    # branded banner library (migration 0047) with a four-image catalogue
    # carousel. Asserted by shape rather than by one hard-coded filename so
    # re-art-directing the carousel does not break this test -- what matters
    # here is that the homepage serves a populated hero, not which picture is
    # currently first or how many slides it currently has.
    assert hero["props"]["imageUrl"].startswith("/banners/home/")
    assert hero["props"]["imageAlt"]
    slides = hero["props"]["slides"]
    assert len(slides) == 4
    assert all(slide["imageUrl"].startswith("/banners/home/") for slide in slides)
    assert all(slide["href"].startswith("/") for slide in slides)
    assert "product_collection" in types
    assert body["seo"]["title"].startswith("True Grit")


def test_public_content_surfaces_read_from_database(
    client: TestClient, public_catalogue_baseline: dict[str, int]
):
    farms = client.get("/v1/public/farms").json()["items"]
    assert {FARM_1_SLUG, FARM_2_SLUG} <= {farm["slug"] for farm in farms}
    farm = client.get(f"/v1/public/farms/{FARM_1_SLUG}").json()
    assert farm["name"] == FARM_1_NAME
    assert PRODUCT_A_SLUG in farm["productSlugs"]

    recipe_page = client.get("/v1/public/recipes").json()
    assert recipe_page["total"] == public_catalogue_baseline["recipes"] + RECIPE_COUNT
    assert recipe_page["limit"] == 12
    assert len(recipe_page["items"]) == 12
    featured_recipe = client.get(f"/v1/public/recipes/{FEATURED_RECIPE_SLUG}").json()
    assert featured_recipe["ingredients"][0]["productSlug"] == PRODUCT_C_SLUG

    # The first page also proves the published byline is not one synthetic
    # editor on every story.
    article_page = client.get("/v1/public/articles").json()
    assert article_page["total"] == public_catalogue_baseline["articles"] + ARTICLE_COUNT
    assert article_page["limit"] == 10
    assert len(article_page["items"]) == 10
    assert len({item["authorName"] for item in article_page["items"]}) >= 2
    featured_article = client.get(f"/v1/public/articles/{FEATURED_ARTICLE_SLUG}").json()
    assert featured_article["authorName"] == "True Grit"


def test_public_content_lists_support_pagination(
    client: TestClient, public_catalogue_baseline: dict[str, int]
):
    first_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 0}).json()
    second_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 12}).json()
    assert first_recipes["total"] == second_recipes["total"]
    assert first_recipes["offset"] == 0
    assert second_recipes["offset"] == 12
    assert {item["id"] for item in first_recipes["items"]}.isdisjoint(
        item["id"] for item in second_recipes["items"]
    )

    # An offset one short of the total article count must return exactly the
    # final post while preserving the collection-wide total.
    article_total = public_catalogue_baseline["articles"] + ARTICLE_COUNT
    first_articles = client.get("/v1/public/articles", params={"limit": 10, "offset": 0}).json()
    last_articles = client.get(
        "/v1/public/articles", params={"limit": 10, "offset": article_total - 1}
    ).json()
    assert first_articles["total"] == last_articles["total"] == article_total
    assert len(first_articles["items"]) == 10
    assert len(last_articles["items"]) == 1


def test_community_discussions_return_total_for_pagination(
    client: TestClient, public_catalogue_baseline: dict[str, int]
):
    discussion_total = public_catalogue_baseline["discussions"] + DISCUSSION_COUNT
    first_page = client.get(
        "/v1/public/community/discussions", params={"limit": 12, "offset": 0}
    ).json()
    last_page = client.get(
        "/v1/public/community/discussions",
        params={"limit": 12, "offset": discussion_total - 4},
    ).json()
    assert first_page["total"] == last_page["total"] == discussion_total
    assert len(first_page["items"]) == 12
    assert len(last_page["items"]) == 4
    # This fixture's rows are all dated strictly later than any pre-existing
    # thread, so they dominate `ORDER BY last_activity_at DESC` and every
    # item on page one must be one of ours.
    assert all(item["id"].startswith("dsc_pub_") for item in first_page["items"])


def test_practical_content_and_catalogue_variants_are_public(client: TestClient):
    article = client.get(f"/v1/public/articles/{FEATURED_ARTICLE_SLUG}").json()
    assert article["title"] == FEATURED_ARTICLE_TITLE
    checks = next(block for block in article["blocks"] if block["type"] == "faq")
    assert len(checks["props"]["items"]) == 5

    recipe = client.get(f"/v1/public/recipes/{FEATURED_RECIPE_SLUG}").json()
    assert len(recipe["ingredients"]) == 6
    assert len(recipe["steps"]) == 6

    discussion = client.get(f"/v1/public/community/discussions/{FEATURED_DISCUSSION_ID}").json()
    assert len(discussion["body"].split()) >= 55

    product = client.get(f"/v1/public/products/{PRODUCT_A_SLUG}").json()
    assert [variant["name"] for variant in product["variants"]] == [
        "Fresh pack",
        "250 g small pack",
        "1000 g family pack",
    ]


def test_public_pages_and_site_documents_have_generated_defaults(client: TestClient):
    home_page = client.get("/v1/public/pages/home").json()
    assert home_page["slug"] == "home"
    assert home_page["blocks"][0]["type"] == "hero"

    about_page = client.get("/v1/public/pages/about").json()
    assert about_page["title"] == "About True Grit"
    assert about_page["blocks"][0]["type"] == "hero"

    # The test client runs with app_env="development", which -- like every
    # non-production environment -- disallows everything by default so a
    # deployed test/staging environment can never be crawled by accident
    # (see tests/unit/test_site_documents.py for the production-mode shape).
    robots = client.get("/v1/public/site-documents/robots_txt").json()
    assert "Disallow: /" in robots["content"]
    assert robots["contentType"].startswith("text/plain")

    sitemap = client.get("/v1/public/site-documents/sitemap_xml").json()
    assert "<sitemapindex" in sitemap["content"]
    assert "/sitemaps/products.xml" in sitemap["content"]
    assert sitemap["contentType"].startswith("application/xml")

    products_sitemap = client.get("/v1/public/sitemaps/products").text
    assert f"/product/{PRODUCT_A_SLUG}" in products_sitemap

    pages_sitemap = client.get("/v1/public/sitemaps/pages").text
    assert "/about" in pages_sitemap

    blog_sitemap = client.get("/v1/public/sitemaps/blog").text
    assert f"/blog/{FEATURED_ARTICLE_SLUG}" in blog_sitemap

    llms = client.get("/v1/public/site-documents/llms_txt").json()
    assert "## Core Pages" in llms["content"]


def test_category_page_resolves_dynamic_rule(client: TestClient):
    response = client.get(f"/v1/public/categories/{FRESH_FRUITS_CATEGORY_SLUG}")
    assert response.status_code == 200
    body = response.json()
    assert body["hero"]["title"] == FRESH_FRUITS_HERO_TITLE
    slugs = [product["slug"] for product in body["products"]]
    assert slugs == [PRODUCT_A_SLUG]
    product = body["products"][0]
    assert product["priceMinor"] == PRODUCT_A_LEAD_PRICE_MINOR
    assert product["availability"] == "in_stock"
    assert product["certifications"] == ["India Organic (NPOP)", "PGS-India Green"]


def test_category_page_grains_includes_buyable_rajma(client: TestClient):
    body = client.get(f"/v1/public/categories/{GRAINS_CATEGORY_SLUG}").json()
    by_slug = {product["slug"]: product for product in body["products"]}
    assert set(by_slug) == {PRODUCT_C_SLUG, PRODUCT_D_SLUG}
    assert by_slug[PRODUCT_D_SLUG]["availability"] == "in_stock"


def test_unknown_and_invalid_category_slugs(client: TestClient):
    assert client.get("/v1/public/categories/not-a-category").status_code == 404
    response = client.get("/v1/public/categories/DROP%20TABLE")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Category hierarchy (shop sidebar, department rail, drill-down)
# ---------------------------------------------------------------------------


def test_categories_list_exposes_tree_position(client: TestClient):
    items = client.get("/v1/public/categories").json()["items"]
    by_slug = {item["slug"]: item for item in items}

    department = by_slug[DEPARTMENT_SLUG]
    assert department["level"] == 0
    assert department["parentId"] is None

    section = by_slug[SECTIONS[0]["slug"]]
    assert section["level"] == 1
    assert section["parentId"] == department["id"]


def test_categories_list_orders_departments_before_their_own_sections(client: TestClient):
    """`sort_order` is only meaningful among siblings, so ordering by it globally
    would open the list with unrelated subcategories ahead of an unrelated
    department. Each branch must be contiguous. Two independent departments
    (one with sections, one without) are enough to prove this -- sort_order
    only matters among siblings, not how many departments exist."""
    items = client.get("/v1/public/categories").json()["items"]
    assert items[0]["level"] == 0, "the list must start with a department"

    positions = {item["id"]: index for index, item in enumerate(items)}
    departments = [item for item in items if item["level"] == 0]
    assert len(departments) >= 2

    for section in (item for item in items if item["level"] == 1):
        parent_index = positions[section["parentId"]]
        assert parent_index < positions[section["id"]], (
            f"{section['slug']} appears before its own department"
        )
        # Contiguity: nothing from another branch sits between the two.
        between = items[parent_index + 1 : positions[section["id"]]]
        assert all(
            item["level"] == 1 and item["parentId"] == section["parentId"] for item in between
        ), f"{section['slug']} is separated from its department by another branch"


def test_category_page_accepts_a_country(client: TestClient):
    """The storefront forwards the visitor's country on every catalogue request,
    so the geo clause's table alias must match the query's own alias. When it
    did not, every category page 500'd for real traffic while passing every
    test that omitted `?country=`."""
    for slug in (DEPARTMENT_SLUG, SECTIONS[0]["slug"], FRESH_FRUITS_CATEGORY_SLUG):
        response = client.get(f"/v1/public/categories/{slug}", params={"country": "IN"})
        assert response.status_code == 200, f"{slug}: {response.text}"
        assert response.json()["slug"] == slug


def test_department_page_lists_its_published_sections(client: TestClient):
    body = client.get(f"/v1/public/categories/{DEPARTMENT_SLUG}").json()
    slugs = [item["slug"] for item in body["subcategories"]]
    assert slugs == [section["slug"] for section in SECTIONS]
    assert all(item["level"] == 1 for item in body["subcategories"])


def test_section_page_breadcrumbs_name_the_department(client: TestClient):
    body = client.get(f"/v1/public/categories/{SECTIONS[0]['slug']}").json()
    assert [crumb["label"] for crumb in body["breadcrumbs"]] == [
        "Home",
        "Shop",
        DEPARTMENT_NAME,
        SECTIONS[0]["name"],
    ]
    assert body["breadcrumbs"][2]["path"] == f"/shop?category={DEPARTMENT_SLUG}"
    # A department has no parent, so its trail is unchanged.
    department = client.get(f"/v1/public/categories/{DEPARTMENT_SLUG}").json()
    assert [crumb["label"] for crumb in department["breadcrumbs"]] == [
        "Home",
        "Shop",
        DEPARTMENT_NAME,
    ]


def test_unpublished_department_hides_its_sections(client: TestClient, db: SQLiteDatabase):
    """Un-publishing a department must not leave its sections claiming a parent
    the storefront can no longer see, or they would surface as top-level."""
    db._conn.execute(
        "UPDATE categories SET status = 'unpublished' WHERE slug = ?", (DEPARTMENT_SLUG,)
    )
    db._conn.commit()

    items = client.get("/v1/public/categories").json()["items"]
    assert DEPARTMENT_SLUG not in {item["slug"] for item in items}
    orphan = next(item for item in items if item["slug"] == SECTIONS[0]["slug"])
    # Still reports its parent, so the storefront's tree builder drops it rather
    # than promoting it into the department rail.
    assert orphan["parentId"] == DEPARTMENT_ID
    assert client.get(f"/v1/public/categories/{DEPARTMENT_SLUG}").status_code == 404


# ---------------------------------------------------------------------------
# Shop grid filtering (?category=)
# ---------------------------------------------------------------------------


def test_products_list_filters_by_category(client: TestClient):
    body = client.get("/v1/public/products", params={"category": SECTIONS[0]["slug"]}).json()
    assert body["total"] == PRODUCTS_PER_SECTION
    assert len(body["items"]) == PRODUCTS_PER_SECTION

    department = client.get("/v1/public/products", params={"category": DEPARTMENT_SLUG}).json()
    assert department["total"] == PRODUCTS_PER_SECTION * len(SECTIONS), (
        "a department covers all four of its sections"
    )


def test_products_list_category_filter_paginates(client: TestClient):
    first = client.get(
        "/v1/public/products", params={"category": DEPARTMENT_SLUG, "limit": 10, "offset": 0}
    ).json()
    second = client.get(
        "/v1/public/products", params={"category": DEPARTMENT_SLUG, "limit": 10, "offset": 10}
    ).json()
    total = PRODUCTS_PER_SECTION * len(SECTIONS)
    assert first["total"] == second["total"] == total
    assert len(first["items"]) == len(second["items"]) == 10
    assert not {p["slug"] for p in first["items"]} & {p["slug"] for p in second["items"]}


def test_products_list_filters_by_diet_tag(client: TestClient):
    body = client.get("/v1/public/products", params={"diet": "vegan"}).json()
    slugs = {product["slug"] for product in body["items"]}
    assert slugs == {
        PRODUCT_A_SLUG,
        PRODUCT_B_SLUG,
        PRODUCT_C_SLUG,
        PRODUCT_D_SLUG,
        PRODUCT_E_SLUG,
    }
    assert body["total"] == 5


def test_products_list_diet_filter_is_or_within_facet(client: TestClient):
    """Selecting two diet tags matches products carrying *either* one, not
    both -- a shopper ticking Gluten Free and Nut Free wants more results,
    not fewer."""
    only_gluten_free = client.get("/v1/public/products", params={"diet": "gluten-free"}).json()
    only_nut_free = client.get("/v1/public/products", params={"diet": "nut-free"}).json()
    combined = client.get("/v1/public/products", params={"diet": "gluten-free,nut-free"}).json()
    assert combined["total"] == len(
        {p["slug"] for p in only_gluten_free["items"]} | {p["slug"] for p in only_nut_free["items"]}
    )


def test_products_list_filters_by_certification(client: TestClient):
    # This fixture is fully isolated (no other product in a fresh database
    # carries a certification), so the subset check below is also exact --
    # kept as a subset for the same reason the original assertion was: the
    # facet is meant to be additive, not an exhaustive enumeration.
    body = client.get("/v1/public/products", params={"certification": "pgs-india"}).json()
    slugs = {product["slug"] for product in body["items"]}
    assert {PRODUCT_A_SLUG, PRODUCT_B_SLUG, PRODUCT_C_SLUG, PRODUCT_E_SLUG} <= slugs
    assert PRODUCT_D_SLUG not in slugs, "only carries india-organic, not pgs-india"


def test_products_list_combines_diet_and_certification_filters(client: TestClient):
    """Diet and certification are AND-ed together: only products matching
    both facets survive."""
    body = client.get(
        "/v1/public/products", params={"diet": "vegan", "certification": "india-organic"}
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    assert slugs == {PRODUCT_A_SLUG, PRODUCT_D_SLUG}


def test_products_list_diet_filter_combines_with_category(client: TestClient):
    body = client.get(
        "/v1/public/products", params={"category": GRAINS_CATEGORY_SLUG, "diet": "vegan"}
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    assert PRODUCT_D_SLUG in slugs
    assert PRODUCT_A_SLUG not in slugs, "not in this category"


def test_filters_endpoint_returns_full_vocabulary(client: TestClient):
    body = client.get("/v1/public/filters").json()
    diet_keys = {tag["key"] for tag in body["dietTags"]}
    assert {"vegan", "vegetarian", "dairy-free", "nut-free", "gluten-free", "plant-based"} <= (
        diet_keys
    )
    certification_slugs = {cert["slug"] for cert in body["certifications"]}
    assert {"india-organic", "pgs-india", "jaivik-bharat"} <= certification_slugs


def test_unknown_category_filter_returns_empty_not_everything(client: TestClient):
    """A stale bookmark must not silently widen into the full catalogue."""
    body = client.get("/v1/public/products", params={"category": "not-a-category"}).json()
    assert body == {"items": [], "total": 0}


def test_unpublished_category_filter_returns_empty(client: TestClient, db: SQLiteDatabase):
    db._conn.execute(
        "UPDATE categories SET status = 'unpublished' WHERE slug = ?", (SECTIONS[0]["slug"],)
    )
    db._conn.commit()
    body = client.get("/v1/public/products", params={"category": SECTIONS[0]["slug"]}).json()
    assert body == {"items": [], "total": 0}


def test_invalid_category_filter_is_rejected(client: TestClient):
    response = client.get("/v1/public/products", params={"category": "DROP TABLE"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_slugs_take_precedence_over_category_filter(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": PRODUCT_A_SLUG, "category": SECTIONS[0]["slug"]},
    ).json()
    assert [product["slug"] for product in body["items"]] == [PRODUCT_A_SLUG]


def test_product_detail_contract(client: TestClient):
    body = client.get(f"/v1/public/products/{PRODUCT_A_SLUG}").json()
    assert body["name"] == PRODUCT_A_NAME
    assert [variant["sku"] for variant in body["variants"]] == [
        "TGP-A-FRESH",
        "TGP-A-250G",
        "TGP-A-1000G",
    ]
    assert body["variants"][1]["saleMinor"] == 24_900
    assert body["traceability"][0]["label"] == "Farm"
    assert body["seo"]["canonicalPath"] == f"/product/{PRODUCT_A_SLUG}"
    assert body["relatedSlugs"] == []


def test_products_list_returns_published_summaries(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": f"{PRODUCT_A_SLUG},{PRODUCT_D_SLUG}"},
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    assert PRODUCT_A_SLUG in slugs
    assert PRODUCT_D_SLUG in slugs
    sample = next(p for p in body["items"] if p["slug"] == PRODUCT_A_SLUG)
    assert sample["priceMinor"] == PRODUCT_A_LEAD_PRICE_MINOR
    assert sample["certifications"] == ["India Organic (NPOP)", "PGS-India Green"]
    # A batched summary carries enough to add the lead variant to a cart --
    # no separate per-slug detail request needed (see SCAL-007 in the
    # scalability assessment: this is what lets recipe.tsx's shoppable
    # ingredients batch through a single `?slugs=` request).
    assert sample["leadVariantId"] == "var_pub_a_1"


def test_products_list_by_slugs_preserves_order(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": f"{PRODUCT_D_SLUG},{PRODUCT_A_SLUG}"},
    ).json()
    assert [p["slug"] for p in body["items"]] == [PRODUCT_D_SLUG, PRODUCT_A_SLUG]


def test_products_list_ignores_unknown_slugs(client: TestClient):
    body = client.get(
        "/v1/public/products", params={"slugs": f"{PRODUCT_A_SLUG},does-not-exist"}
    ).json()
    assert [p["slug"] for p in body["items"]] == [PRODUCT_A_SLUG]


def test_products_list_does_not_collide_with_detail_route(client: TestClient):
    # The literal /products path must not be swallowed by /products/{slug}.
    assert client.get("/v1/public/products").status_code == 200
    assert client.get(f"/v1/public/products/{PRODUCT_A_SLUG}").status_code == 200


def test_search_matches_synonyms(client: TestClient):
    body = client.get("/v1/public/search", params={"q": PRODUCT_C_SEARCH_TERM}).json()
    product_group = next(group for group in body["groups"] if group["group"] == "products")
    assert any(item["slug"] == PRODUCT_C_SLUG for item in product_group["items"])

    direct = client.get("/v1/public/search", params={"q": PRODUCT_D_SEARCH_TERM}).json()
    assert direct["total"] >= 1


def test_search_zero_results_is_safe(client: TestClient):
    body = client.get("/v1/public/search", params={"q": "zzzzunknownterm"}).json()
    assert body == {"query": "zzzzunknownterm", "total": 0, "groups": []}


def _search_product_slugs(client: TestClient, query: str, **params: str) -> set[str]:
    body = client.get("/v1/public/search", params={"q": query, **params}).json()
    return {
        item["slug"]
        for group in body["groups"]
        if group["group"] == "products"
        for item in group["items"]
    }


def test_search_reflects_live_catalogue(client: TestClient, db: SQLiteDatabase):
    # Product hits come from the live products table, so an unpublish takes
    # effect immediately (the FTS shadow table is only seeded, never synced).
    assert PRODUCT_C_SLUG in _search_product_slugs(client, PRODUCT_C_SEARCH_TERM)

    db._conn.execute("UPDATE products SET status = 'unpublished' WHERE id = ?", (PRODUCT_C_ID,))
    db._conn.commit()

    assert PRODUCT_C_SLUG not in _search_product_slugs(client, PRODUCT_C_SEARCH_TERM)


def test_search_product_items_carry_slug(client: TestClient):
    body = client.get("/v1/public/search", params={"q": PRODUCT_D_SEARCH_PHRASE}).json()
    product_group = next(group for group in body["groups"] if group["group"] == "products")
    assert any(item["slug"] == PRODUCT_D_SLUG for item in product_group["items"])


# ---------------------------------------------------------------------------
# Geo release
# ---------------------------------------------------------------------------


def test_geo_release_filters_product_lists(client: TestClient, db: SQLiteDatabase):
    _restrict_product(db, PRODUCT_D_ID, ["US"])

    india = client.get(
        "/v1/public/products",
        params={"country": "IN", "slugs": PRODUCT_D_SLUG},
    ).json()
    assert PRODUCT_D_SLUG not in {p["slug"] for p in india["items"]}

    united_states = client.get(
        "/v1/public/products",
        params={"country": "us", "slugs": PRODUCT_D_SLUG},
    ).json()
    assert PRODUCT_D_SLUG in {p["slug"] for p in united_states["items"]}

    # No country -> no filtering (internal callers, older clients).
    unfiltered = client.get("/v1/public/products", params={"slugs": PRODUCT_D_SLUG}).json()
    assert PRODUCT_D_SLUG in {p["slug"] for p in unfiltered["items"]}


def test_geo_release_locks_product_detail(client: TestClient, db: SQLiteDatabase):
    _restrict_product(db, PRODUCT_D_ID, ["US"])
    assert (
        client.get(f"/v1/public/products/{PRODUCT_D_SLUG}", params={"country": "IN"}).status_code
        == 404
    )
    assert (
        client.get(f"/v1/public/products/{PRODUCT_D_SLUG}", params={"country": "US"}).status_code
        == 200
    )


def test_geo_release_filters_search_and_category(client: TestClient, db: SQLiteDatabase):
    # Scoped to the restricted product: the other grain product stays
    # globally released and must keep matching, so an empty result set would
    # prove nothing about geo filtering.
    assert PRODUCT_D_SLUG in _search_product_slugs(client, PRODUCT_D_SEARCH_TERM, country="IN")

    _restrict_product(db, PRODUCT_D_ID, ["US"])

    assert PRODUCT_D_SLUG not in _search_product_slugs(client, PRODUCT_D_SEARCH_TERM, country="IN")
    assert PRODUCT_D_SLUG in _search_product_slugs(client, PRODUCT_D_SEARCH_TERM, country="US")

    category = client.get(
        f"/v1/public/categories/{GRAINS_CATEGORY_SLUG}", params={"country": "IN"}
    ).json()
    assert {p["slug"] for p in category["products"]} == {PRODUCT_C_SLUG}


def test_country_param_must_be_two_letters(client: TestClient):
    response = client.get("/v1/public/products", params={"country": "U1"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Highlighted products (search page slots)
# ---------------------------------------------------------------------------


def test_highlights_return_curated_order_published_only(client: TestClient, db: SQLiteDatabase):
    db._conn.executescript(
        f"""
        INSERT INTO highlighted_products (product_id, sort_order, added_at, added_by) VALUES
          ('{PRODUCT_C_ID}', 1, '2026-07-16T00:00:00Z', 'usr_admin'),
          ('{PRODUCT_A_ID}', 0, '2026-07-16T00:00:00Z', 'usr_admin');
        """
    )
    db._conn.commit()
    body = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in body["items"]] == [PRODUCT_A_SLUG, PRODUCT_C_SLUG]

    # Unpublishing removes the slot from customers without touching curation.
    db._conn.execute("UPDATE products SET status = 'unpublished' WHERE id = ?", (PRODUCT_A_ID,))
    db._conn.commit()
    body = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in body["items"]] == [PRODUCT_C_SLUG]


def test_highlights_respect_geo_release(client: TestClient, db: SQLiteDatabase):
    db._conn.execute(
        "INSERT INTO highlighted_products (product_id, sort_order, added_at, added_by)"
        " VALUES (?, 0, '2026-07-16T00:00:00Z', 'usr_admin')",
        (PRODUCT_D_ID,),
    )
    db._conn.commit()
    _restrict_product(db, PRODUCT_D_ID, ["US"])
    india = client.get("/v1/public/highlights", params={"country": "IN"}).json()
    assert india["items"] == []
    united_states = client.get("/v1/public/highlights", params={"country": "US"}).json()
    assert [p["slug"] for p in united_states["items"]] == [PRODUCT_D_SLUG]

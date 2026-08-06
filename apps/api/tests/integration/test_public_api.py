from fastapi.testclient import TestClient

from truegrit_api.platform.database import SQLiteDatabase


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
    assert body["announcement"]["message"].startswith("Alphonso season")
    assert body["announcement"]["path"] == "/seasonal"


def test_home_returns_published_blocks_only(client: TestClient):
    body = client.get("/v1/public/home").json()
    types = [block["type"] for block in body["blocks"]]
    hero = body["blocks"][0]
    assert types[0] == "hero"
    # Migration 0047 replaced the single placeholder hero with the twelve-image
    # branded banner library. Asserted by shape rather than by one hard-coded
    # filename so re-art-directing the carousel does not break this test --
    # what matters here is that the homepage serves a populated hero, not which
    # picture is currently first.
    assert hero["props"]["imageUrl"].startswith("/banners/home/")
    assert hero["props"]["imageAlt"]
    slides = hero["props"]["slides"]
    assert len(slides) == 12
    assert all(slide["imageUrl"].startswith("/banners/home/") for slide in slides)
    assert all(slide["href"].startswith("/") for slide in slides)
    assert "product_collection" in types
    assert body["seo"]["title"].startswith("True Grit")


def test_public_content_surfaces_read_from_database(client: TestClient):
    farms = client.get("/v1/public/farms").json()["items"]
    assert {farm["slug"] for farm in farms} == {
        "anandvan-collective",
        "devika-organics",
        "himgiri-terraces",
    }
    farm = client.get("/v1/public/farms/devika-organics").json()
    assert farm["name"] == "Devika Organics"
    # Containment, not equality: this farm now supplies a large slice of the
    # catalogue, and the contract under test is that its own products are
    # listed — not how many it happens to have.
    assert "organic-alphonso-mangoes" in farm["productSlugs"]

    recipe_page = client.get("/v1/public/recipes").json()
    assert recipe_page["total"] == 551
    assert recipe_page["limit"] == 12
    assert len(recipe_page["items"]) == 12
    ragi_recipe = client.get("/v1/public/recipes/crisp-sprouted-ragi-dosa").json()
    assert ragi_recipe["ingredients"][0]["productSlug"] == "sprouted-ragi-flour"

    # Migration 0050 restores the original visible volume without restoring
    # the old three-template filler catalogue. The first page also proves the
    # published byline is no longer one synthetic editor on every story.
    article_page = client.get("/v1/public/articles").json()
    assert article_page["total"] == 351
    assert article_page["limit"] == 10
    assert len(article_page["items"]) == 10
    assert len({item["authorName"] for item in article_page["items"]}) >= 2
    millet_article = client.get("/v1/public/articles/choose-ragi-jowar-bajra-little-millet").json()
    assert millet_article["authorName"] == "True Grit Kitchen"


def test_public_content_lists_support_pagination(client: TestClient):
    first_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 0}).json()
    second_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 12}).json()
    assert first_recipes["total"] == second_recipes["total"] == 551
    assert first_recipes["offset"] == 0
    assert second_recipes["offset"] == 12
    assert {item["id"] for item in first_recipes["items"]}.isdisjoint(
        item["id"] for item in second_recipes["items"]
    )

    # The expanded library contains 351 distinct posts. An offset of 350 must
    # return the final post while preserving the collection-wide total.
    first_articles = client.get("/v1/public/articles", params={"limit": 10, "offset": 0}).json()
    last_articles = client.get("/v1/public/articles", params={"limit": 10, "offset": 350}).json()
    assert first_articles["total"] == last_articles["total"] == 351
    assert len(first_articles["items"]) == 10
    assert len(last_articles["items"]) == 1


def test_community_discussions_return_total_for_pagination(client: TestClient):
    first_page = client.get(
        "/v1/public/community/discussions", params={"limit": 12, "offset": 0}
    ).json()
    last_page = client.get(
        "/v1/public/community/discussions", params={"limit": 12, "offset": 396}
    ).json()
    assert first_page["total"] == last_page["total"] == 400
    assert len(first_page["items"]) == 12
    assert len(last_page["items"]) == 4
    assert all(not item["id"].startswith("dsc_expansion_") for item in first_page["items"])


def test_practical_content_and_catalogue_variants_are_public(client: TestClient):
    article = client.get("/v1/public/articles/compare-cooking-oils-for-real-kitchens").json()
    assert article["title"] == "How to compare cooking oils without chasing one perfect oil"
    checks = next(block for block in article["blocks"] if block["type"] == "faq")
    assert len(checks["props"]["items"]) == 5

    recipe = client.get("/v1/public/recipes/lemon-spinach-chickpea-skillet").json()
    assert len(recipe["ingredients"]) == 6
    assert len(recipe["steps"]) == 6

    discussion = client.get("/v1/public/community/discussions/dsc_practical_001").json()
    assert len(discussion["body"].split()) >= 55

    product = client.get("/v1/public/products/organic-kesar-mango").json()
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

    robots = client.get("/v1/public/site-documents/robots_txt").json()
    assert "Sitemap:" in robots["content"]
    assert robots["contentType"].startswith("text/plain")

    sitemap = client.get("/v1/public/site-documents/sitemap_xml").json()
    assert "<sitemapindex" in sitemap["content"]
    assert "/sitemaps/products.xml" in sitemap["content"]
    assert sitemap["contentType"].startswith("application/xml")

    products_sitemap = client.get("/v1/public/sitemaps/products").text
    assert "/product/organic-alphonso-mangoes" in products_sitemap

    pages_sitemap = client.get("/v1/public/sitemaps/pages").text
    assert "/about" in pages_sitemap

    blog_sitemap = client.get("/v1/public/sitemaps/blog").text
    assert "/blog/choose-ragi-jowar-bajra-little-millet" in blog_sitemap

    llms = client.get("/v1/public/site-documents/llms_txt").json()
    assert "## Core Pages" in llms["content"]


def test_category_page_resolves_dynamic_rule(client: TestClient):
    response = client.get("/v1/public/categories/fresh-fruits")
    assert response.status_code == 200
    body = response.json()
    assert body["hero"]["title"] == "Fruit, at its honest best"
    slugs = [product["slug"] for product in body["products"]]
    assert slugs == ["organic-alphonso-mangoes"]
    product = body["products"][0]
    assert product["priceMinor"] == 89900
    assert product["availability"] == "in_stock"
    assert product["certifications"] == ["India Organic (NPOP)", "PGS-India Green"]


def test_category_page_grains_includes_buyable_rajma(client: TestClient):
    body = client.get("/v1/public/categories/grains-and-millets").json()
    by_slug = {product["slug"]: product for product in body["products"]}
    assert set(by_slug) == {"sprouted-ragi-flour", "himalayan-red-rajma"}
    assert by_slug["himalayan-red-rajma"]["availability"] == "in_stock"


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

    department = by_slug["fruits"]
    assert department["level"] == 0
    assert department["parentId"] is None

    section = by_slug["tropical-fruits"]
    assert section["level"] == 1
    assert section["parentId"] == department["id"]


def test_categories_list_orders_departments_before_their_own_sections(client: TestClient):
    """`sort_order` is only meaningful among siblings, so ordering by it globally
    used to open the list with unrelated subcategories (sort_order 1-4) ahead of
    every department (11-50). Each branch must now be contiguous."""
    items = client.get("/v1/public/categories").json()["items"]
    assert items[0]["level"] == 0, "the list must start with a department"

    positions = {item["id"]: index for index, item in enumerate(items)}
    departments = [item for item in items if item["level"] == 0]
    assert len(departments) >= 20

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
    for slug in ("fruits", "tropical-fruits", "fresh-fruits"):
        response = client.get(f"/v1/public/categories/{slug}", params={"country": "IN"})
        assert response.status_code == 200, f"{slug}: {response.text}"
        assert response.json()["slug"] == slug


def test_department_page_lists_its_published_sections(client: TestClient):
    body = client.get("/v1/public/categories/fruits").json()
    slugs = [item["slug"] for item in body["subcategories"]]
    assert slugs == [
        "tropical-fruits",
        "citrus-fruits",
        "berries-small-fruits",
        "melons-orchard-fruits",
    ]
    assert all(item["level"] == 1 for item in body["subcategories"])


def test_section_page_breadcrumbs_name_the_department(client: TestClient):
    body = client.get("/v1/public/categories/tropical-fruits").json()
    assert [crumb["label"] for crumb in body["breadcrumbs"]] == [
        "Home",
        "Shop",
        "Fresh Fruits",
        "Tropical Fruits",
    ]
    assert body["breadcrumbs"][2]["path"] == "/shop?category=fruits"
    # A department has no parent, so its trail is unchanged.
    department = client.get("/v1/public/categories/fruits").json()
    assert [crumb["label"] for crumb in department["breadcrumbs"]] == [
        "Home",
        "Shop",
        "Fresh Fruits",
    ]


def test_unpublished_department_hides_its_sections(client: TestClient, db: SQLiteDatabase):
    """Un-publishing a department must not leave its sections claiming a parent
    the storefront can no longer see, or they would surface as top-level."""
    db._conn.execute("UPDATE categories SET status = 'unpublished' WHERE slug = 'fruits'")
    db._conn.commit()

    items = client.get("/v1/public/categories").json()["items"]
    assert "fruits" not in {item["slug"] for item in items}
    orphan = next(item for item in items if item["slug"] == "tropical-fruits")
    # Still reports its parent, so the storefront's tree builder drops it rather
    # than promoting it into the department rail.
    assert orphan["parentId"] == "cat_market_fruits"
    assert client.get("/v1/public/categories/fruits").status_code == 404


# ---------------------------------------------------------------------------
# Shop grid filtering (?category=)
# ---------------------------------------------------------------------------


def test_products_list_filters_by_category(client: TestClient):
    body = client.get("/v1/public/products", params={"category": "tropical-fruits"}).json()
    assert body["total"] == 8
    assert len(body["items"]) == 8

    department = client.get("/v1/public/products", params={"category": "fruits"}).json()
    assert department["total"] == 32, "a department covers all four of its sections"


def test_products_list_category_filter_paginates(client: TestClient):
    first = client.get(
        "/v1/public/products", params={"category": "fruits", "limit": 10, "offset": 0}
    ).json()
    second = client.get(
        "/v1/public/products", params={"category": "fruits", "limit": 10, "offset": 10}
    ).json()
    assert first["total"] == second["total"] == 32
    assert len(first["items"]) == len(second["items"]) == 10
    assert not {p["slug"] for p in first["items"]} & {p["slug"] for p in second["items"]}


def test_products_list_filters_by_diet_tag(client: TestClient):
    body = client.get("/v1/public/products", params={"diet": "vegan"}).json()
    slugs = {product["slug"] for product in body["items"]}
    assert slugs == {
        "organic-alphonso-mangoes",
        "organic-baby-spinach",
        "sprouted-ragi-flour",
        "himalayan-red-rajma",
        "wood-pressed-groundnut-oil",
    }
    assert body["total"] == 5


def test_products_list_diet_filter_is_or_within_facet(client: TestClient):
    """Selecting two diet tags matches products carrying *either* one, not
    both -- a shopper ticking Gluten Free and Nut Free wants more results,
    not fewer."""
    only_gluten_free = client.get("/v1/public/products", params={"diet": "gluten-free"}).json()
    only_nut_free = client.get("/v1/public/products", params={"diet": "nut-free"}).json()
    combined = client.get(
        "/v1/public/products", params={"diet": "gluten-free,nut-free"}
    ).json()
    assert combined["total"] == len(
        {p["slug"] for p in only_gluten_free["items"]} | {p["slug"] for p in only_nut_free["items"]}
    )


def test_products_list_filters_by_certification(client: TestClient):
    # The bulk-generated catalogue also carries pgs-india certifications
    # (see catalogue.generated.json), so this only asserts the hand-authored
    # products are included, not that the result is exactly these four.
    body = client.get("/v1/public/products", params={"certification": "pgs-india"}).json()
    slugs = {product["slug"] for product in body["items"]}
    assert {
        "organic-alphonso-mangoes",
        "organic-baby-spinach",
        "sprouted-ragi-flour",
        "wood-pressed-groundnut-oil",
    } <= slugs
    assert "himalayan-red-rajma" not in slugs, "only carries india-organic, not pgs-india"


def test_products_list_combines_diet_and_certification_filters(client: TestClient):
    """Diet and certification are AND-ed together: only products matching
    both facets survive."""
    body = client.get(
        "/v1/public/products", params={"diet": "vegan", "certification": "india-organic"}
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    assert slugs == {"organic-alphonso-mangoes", "himalayan-red-rajma"}


def test_products_list_diet_filter_combines_with_category(client: TestClient):
    body = client.get(
        "/v1/public/products", params={"category": "grains-and-millets", "diet": "vegan"}
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    assert "himalayan-red-rajma" in slugs
    assert "organic-alphonso-mangoes" not in slugs, "not in this category"


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
    db._conn.execute("UPDATE categories SET status = 'unpublished' WHERE slug = 'tropical-fruits'")
    db._conn.commit()
    body = client.get("/v1/public/products", params={"category": "tropical-fruits"}).json()
    assert body == {"items": [], "total": 0}


def test_invalid_category_filter_is_rejected(client: TestClient):
    response = client.get("/v1/public/products", params={"category": "DROP TABLE"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_slugs_take_precedence_over_category_filter(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": "organic-alphonso-mangoes", "category": "tropical-fruits"},
    ).json()
    assert [product["slug"] for product in body["items"]] == ["organic-alphonso-mangoes"]


def test_product_detail_contract(client: TestClient):
    body = client.get("/v1/public/products/organic-alphonso-mangoes").json()
    assert body["name"] == "Organic Alphonso Mangoes"
    assert [variant["sku"] for variant in body["variants"]] == [
        "TRG-MNG-1KG",
        "TRG-MNG-2KG",
        "TRG-MNG-5KG",
    ]
    assert body["variants"][1]["saleMinor"] == 149900
    assert body["traceability"][0]["label"] == "Farm"
    assert body["seo"]["canonicalPath"] == "/product/organic-alphonso-mangoes"
    assert body["relatedSlugs"] == []


def test_products_list_returns_published_summaries(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": "organic-alphonso-mangoes,himalayan-red-rajma"},
    ).json()
    slugs = {product["slug"] for product in body["items"]}
    # Every published seed product, and nothing in draft/archived.
    assert "organic-alphonso-mangoes" in slugs
    assert "himalayan-red-rajma" in slugs
    sample = next(p for p in body["items"] if p["slug"] == "organic-alphonso-mangoes")
    assert sample["priceMinor"] == 89900
    assert sample["certifications"] == ["India Organic (NPOP)", "PGS-India Green"]
    # A batched summary carries enough to add the lead variant to a cart --
    # no separate per-slug detail request needed (see SCAL-007 in the
    # scalability assessment: this is what lets recipe.tsx's shoppable
    # ingredients batch through a single `?slugs=` request).
    assert sample["leadVariantId"] == "var_alphonso_1kg"


def test_products_list_by_slugs_preserves_order(client: TestClient):
    body = client.get(
        "/v1/public/products",
        params={"slugs": "himalayan-red-rajma,organic-alphonso-mangoes"},
    ).json()
    assert [p["slug"] for p in body["items"]] == [
        "himalayan-red-rajma",
        "organic-alphonso-mangoes",
    ]


def test_products_list_ignores_unknown_slugs(client: TestClient):
    body = client.get(
        "/v1/public/products", params={"slugs": "organic-alphonso-mangoes,does-not-exist"}
    ).json()
    assert [p["slug"] for p in body["items"]] == ["organic-alphonso-mangoes"]


def test_products_list_does_not_collide_with_detail_route(client: TestClient):
    # The literal /products path must not be swallowed by /products/{slug}.
    assert client.get("/v1/public/products").status_code == 200
    assert client.get("/v1/public/products/organic-alphonso-mangoes").status_code == 200


def test_search_matches_synonyms(client: TestClient):
    body = client.get("/v1/public/search", params={"q": "finger millet"}).json()
    product_group = next(group for group in body["groups"] if group["group"] == "products")
    assert any("Ragi" in item["name"] for item in product_group["items"])

    direct = client.get("/v1/public/search", params={"q": "rajma"}).json()
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
    # Asserted on the one product being unpublished rather than on the absence
    # of every "ragi" result — the catalogue carries many other ragi products,
    # and they are meant to keep matching.
    assert "sprouted-ragi-flour" in _search_product_slugs(client, "stone milled")

    db._conn.execute("UPDATE products SET status = 'unpublished' WHERE id = 'prd_ragi'")
    db._conn.commit()

    assert "sprouted-ragi-flour" not in _search_product_slugs(client, "stone milled")


def test_search_product_items_carry_slug(client: TestClient):
    body = client.get("/v1/public/search", params={"q": "himalayan red rajma"}).json()
    product_group = next(group for group in body["groups"] if group["group"] == "products")
    assert any(item["slug"] == "himalayan-red-rajma" for item in product_group["items"])


# ---------------------------------------------------------------------------
# Geo release
# ---------------------------------------------------------------------------


def test_geo_release_filters_product_lists(client: TestClient, db: SQLiteDatabase):
    _restrict_product(db, "prd_rajma", ["US"])

    india = client.get(
        "/v1/public/products",
        params={"country": "IN", "slugs": "himalayan-red-rajma"},
    ).json()
    assert "himalayan-red-rajma" not in {p["slug"] for p in india["items"]}

    united_states = client.get(
        "/v1/public/products",
        params={"country": "us", "slugs": "himalayan-red-rajma"},
    ).json()
    assert "himalayan-red-rajma" in {p["slug"] for p in united_states["items"]}

    # No country -> no filtering (internal callers, older clients).
    unfiltered = client.get("/v1/public/products", params={"slugs": "himalayan-red-rajma"}).json()
    assert "himalayan-red-rajma" in {p["slug"] for p in unfiltered["items"]}


def test_geo_release_locks_product_detail(client: TestClient, db: SQLiteDatabase):
    _restrict_product(db, "prd_rajma", ["US"])
    assert (
        client.get("/v1/public/products/himalayan-red-rajma", params={"country": "IN"}).status_code
        == 404
    )
    assert (
        client.get("/v1/public/products/himalayan-red-rajma", params={"country": "US"}).status_code
        == 200
    )


def test_geo_release_filters_search_and_category(client: TestClient, db: SQLiteDatabase):
    # Scoped to the restricted product: other rajma products stay globally
    # released and must keep matching, so an empty result set would prove
    # nothing about geo filtering.
    assert "himalayan-red-rajma" in _search_product_slugs(client, "rajma", country="IN")

    _restrict_product(db, "prd_rajma", ["US"])

    assert "himalayan-red-rajma" not in _search_product_slugs(client, "rajma", country="IN")
    assert "himalayan-red-rajma" in _search_product_slugs(client, "rajma", country="US")

    category = client.get(
        "/v1/public/categories/grains-and-millets", params={"country": "IN"}
    ).json()
    assert {p["slug"] for p in category["products"]} == {"sprouted-ragi-flour"}


def test_country_param_must_be_two_letters(client: TestClient):
    response = client.get("/v1/public/products", params={"country": "U1"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


# ---------------------------------------------------------------------------
# Highlighted products (search page slots)
# ---------------------------------------------------------------------------


def test_highlights_return_curated_order_published_only(client: TestClient, db: SQLiteDatabase):
    db._conn.executescript(
        """
        INSERT INTO highlighted_products (product_id, sort_order, added_at, added_by) VALUES
          ('prd_ragi', 1, '2026-07-16T00:00:00Z', 'usr_admin'),
          ('prd_alphonso', 0, '2026-07-16T00:00:00Z', 'usr_admin');
        """
    )
    db._conn.commit()
    body = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in body["items"]] == [
        "organic-alphonso-mangoes",
        "sprouted-ragi-flour",
    ]

    # Unpublishing removes the slot from customers without touching curation.
    db._conn.execute("UPDATE products SET status = 'unpublished' WHERE id = 'prd_alphonso'")
    db._conn.commit()
    body = client.get("/v1/public/highlights").json()
    assert [p["slug"] for p in body["items"]] == ["sprouted-ragi-flour"]


def test_highlights_respect_geo_release(client: TestClient, db: SQLiteDatabase):
    db._conn.execute(
        "INSERT INTO highlighted_products (product_id, sort_order, added_at, added_by)"
        " VALUES ('prd_rajma', 0, '2026-07-16T00:00:00Z', 'usr_admin')"
    )
    db._conn.commit()
    _restrict_product(db, "prd_rajma", ["US"])
    india = client.get("/v1/public/highlights", params={"country": "IN"}).json()
    assert india["items"] == []
    united_states = client.get("/v1/public/highlights", params={"country": "US"}).json()
    assert [p["slug"] for p in united_states["items"]] == ["himalayan-red-rajma"]

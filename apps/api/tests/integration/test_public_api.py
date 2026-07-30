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
    assert types[0] == "hero"
    assert body["blocks"][0]["props"]["imageUrl"] == "/homepage-hero.png"
    assert body["blocks"][0]["props"]["imageAlt"] == "Organic mangoes held in a sunlit orchard"
    assert len(body["blocks"][0]["props"]["slides"]) == 5
    assert body["blocks"][0]["props"]["slides"][1]["href"] == "/category/organic-vegetables"
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
    assert farm["productSlugs"] == ["organic-alphonso-mangoes"]

    recipe_page = client.get("/v1/public/recipes").json()
    assert recipe_page["total"] == 301
    assert recipe_page["limit"] == 12
    assert len(recipe_page["items"]) == 12
    ragi_recipe = client.get("/v1/public/recipes/crisp-sprouted-ragi-dosa").json()
    assert ragi_recipe["ingredients"][0]["productSlug"] == "sprouted-ragi-flour"

    article_page = client.get("/v1/public/articles").json()
    assert article_page["total"] == 201
    assert article_page["limit"] == 10
    assert len(article_page["items"]) == 10
    millet_article = client.get("/v1/public/articles/quiet-revival-of-indian-millets").json()
    assert millet_article["authorName"] == "Kabir Mehta"


def test_public_content_lists_support_pagination(client: TestClient):
    first_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 0}).json()
    second_recipes = client.get("/v1/public/recipes", params={"limit": 12, "offset": 12}).json()
    assert first_recipes["total"] == second_recipes["total"] == 301
    assert first_recipes["offset"] == 0
    assert second_recipes["offset"] == 12
    assert {item["id"] for item in first_recipes["items"]}.isdisjoint(
        item["id"] for item in second_recipes["items"]
    )

    first_articles = client.get("/v1/public/articles", params={"limit": 10, "offset": 0}).json()
    last_articles = client.get("/v1/public/articles", params={"limit": 10, "offset": 200}).json()
    assert first_articles["total"] == last_articles["total"] == 201
    assert len(first_articles["items"]) == 10
    assert len(last_articles["items"]) == 1


def test_community_discussions_return_total_for_pagination(client: TestClient):
    first_page = client.get(
        "/v1/public/community/discussions", params={"limit": 12, "offset": 0}
    ).json()
    last_page = client.get(
        "/v1/public/community/discussions", params={"limit": 12, "offset": 192}
    ).json()
    assert first_page["total"] == last_page["total"] == 200
    assert len(first_page["items"]) == 12
    assert len(last_page["items"]) == 8


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
    assert "/blog/quiet-revival-of-indian-millets" in blog_sitemap

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
    assert product["certification"] == "India Organic (NPOP)"


def test_category_page_grains_includes_low_stock_rajma(client: TestClient):
    body = client.get("/v1/public/categories/grains-and-millets").json()
    by_slug = {product["slug"]: product for product in body["products"]}
    assert set(by_slug) == {"sprouted-ragi-flour", "himalayan-red-rajma"}
    assert by_slug["himalayan-red-rajma"]["availability"] == "low_stock"


def test_unknown_and_invalid_category_slugs(client: TestClient):
    assert client.get("/v1/public/categories/not-a-category").status_code == 404
    response = client.get("/v1/public/categories/DROP%20TABLE")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_product_detail_contract(client: TestClient):
    body = client.get("/v1/public/products/organic-alphonso-mangoes").json()
    assert body["name"] == "Organic Alphonso Mangoes"
    assert [variant["sku"] for variant in body["variants"]] == ["TRG-MNG-1KG", "TRG-MNG-2KG"]
    assert body["variants"][1]["saleMinor"] == 149900
    assert body["traceability"][0]["label"] == "Farm"
    assert body["seo"]["canonicalPath"] == "/product/organic-alphonso-mangoes"
    assert body["relatedSlugs"] == []


def test_products_list_returns_published_summaries(client: TestClient):
    body = client.get("/v1/public/products").json()
    slugs = {product["slug"] for product in body["items"]}
    # Every published seed product, and nothing in draft/archived.
    assert "organic-alphonso-mangoes" in slugs
    assert "himalayan-red-rajma" in slugs
    sample = next(p for p in body["items"] if p["slug"] == "organic-alphonso-mangoes")
    assert sample["priceMinor"] == 89900
    assert sample["certification"] == "India Organic (NPOP)"


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


def test_search_reflects_live_catalogue(client: TestClient, db: SQLiteDatabase):
    # Product hits come from the live products table, so an unpublish takes
    # effect immediately (the FTS shadow table is only seeded, never synced).
    db._conn.execute("UPDATE products SET status = 'unpublished' WHERE id = 'prd_ragi'")
    db._conn.commit()
    body = client.get("/v1/public/search", params={"q": "ragi"}).json()
    product_groups = [group for group in body["groups"] if group["group"] == "products"]
    names = [item["name"] for group in product_groups for item in group["items"]]
    assert all("Ragi" not in name for name in names)


def test_search_product_items_carry_slug(client: TestClient):
    body = client.get("/v1/public/search", params={"q": "rajma"}).json()
    product_group = next(group for group in body["groups"] if group["group"] == "products")
    assert product_group["items"][0]["slug"] == "himalayan-red-rajma"


# ---------------------------------------------------------------------------
# Geo release
# ---------------------------------------------------------------------------


def test_geo_release_filters_product_lists(client: TestClient, db: SQLiteDatabase):
    _restrict_product(db, "prd_rajma", ["US"])

    india = client.get("/v1/public/products", params={"country": "IN"}).json()
    assert "himalayan-red-rajma" not in {p["slug"] for p in india["items"]}

    united_states = client.get("/v1/public/products", params={"country": "us"}).json()
    assert "himalayan-red-rajma" in {p["slug"] for p in united_states["items"]}

    # No country -> no filtering (internal callers, older clients).
    unfiltered = client.get("/v1/public/products").json()
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
    _restrict_product(db, "prd_rajma", ["US"])

    search = client.get("/v1/public/search", params={"q": "rajma", "country": "IN"}).json()
    product_groups = [group for group in search["groups"] if group["group"] == "products"]
    assert not product_groups

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

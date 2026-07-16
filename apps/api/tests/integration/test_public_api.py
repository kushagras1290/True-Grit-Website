from fastapi.testclient import TestClient


def test_health(client: TestClient):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "x-request-id" in response.headers


def test_bootstrap_navigation_and_announcement(client: TestClient):
    body = client.get("/v1/public/bootstrap").json()
    labels = [item["label"] for item in body["navigation"]]
    assert labels == ["Shop", "Seasonal", "Farmers", "Recipes", "Journal", "Our Standards"]
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
    assert "product_collection" in types
    assert body["seo"]["title"].startswith("True Grit")


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

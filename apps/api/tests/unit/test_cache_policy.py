from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.testclient import TestClient

from truegrit_api.middleware.cache_policy import PublicCachePolicyMiddleware, cache_tags


def _client() -> TestClient:
    app = FastAPI()
    app.add_middleware(PublicCachePolicyMiddleware)

    @app.get("/{path:path}")
    async def response(path: str) -> Response:
        if path.endswith("sets-cookie"):
            return Response("ok", headers={"set-cookie": "session=secret"})
        return Response("ok")

    return TestClient(app)


def test_anonymous_public_read_is_shared_cacheable() -> None:
    response = _client().get("/v1/public/products/organic-rice?country=IN&locale=en-IN")

    assert response.headers["x-cache-policy"] == "public"
    assert "s-maxage=60" in response.headers["cache-control"]
    assert response.headers["cache-tag"] == (
        "truegrit-public-api,truegrit-products,truegrit-products-organic-rice"
    )


def test_cookie_or_authorization_bypasses_shared_cache() -> None:
    client = _client()

    cookie_response = client.get("/v1/public/home", headers={"cookie": "tg_session=secret"})
    authorization_response = client.get(
        "/v1/public/home", headers={"authorization": "Bearer secret"}
    )

    assert cookie_response.headers["cache-control"] == "no-store"
    assert authorization_response.headers["cache-control"] == "no-store"


def test_private_public_namespace_route_is_never_shared() -> None:
    response = _client().get("/v1/public/orders/TG-123")

    assert response.headers["x-cache-policy"] == "bypass"
    assert response.headers["cache-control"] == "no-store"


def test_set_cookie_response_is_never_shared() -> None:
    response = _client().get("/v1/public/sets-cookie")

    assert response.headers["x-cache-policy"] == "bypass"
    assert response.headers["cache-control"] == "no-store"


def test_cache_tags_are_bounded() -> None:
    identifier = "x" * 200

    tags = cache_tags(f"/v1/public/products/{identifier}")

    assert len(tags.rsplit("-", 1)[-1]) == 80

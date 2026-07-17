"""Owner-managed public crawler documents with generated defaults."""

from __future__ import annotations

from html import escape
from typing import Any

from truegrit_api.config import Settings
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    ArticleRepository,
    CategoryRepository,
    FarmRepository,
    RecipeRepository,
)

SITE_DOCUMENT_TYPES = {
    "robots_txt": "text/plain; charset=utf-8",
    "sitemap_xml": "application/xml; charset=utf-8",
    "llms_txt": "text/plain; charset=utf-8",
}


def _origin(settings: Settings) -> str:
    return settings.public_storefront_url.rstrip("/")


def _url(settings: Settings, path: str) -> str:
    return f"{_origin(settings)}{path}"


def default_robots_txt(settings: Settings) -> str:
    return "\n".join(
        [
            "User-agent: *",
            "Allow: /",
            "Disallow: /checkout",
            "Disallow: /account",
            "Disallow: /payment/",
            "",
            f"Sitemap: {_url(settings, '/sitemap.xml')}",
            "",
        ]
    )


async def default_sitemap_xml(db: Database, settings: Settings) -> str:
    static_paths = [
        "/",
        "/shop",
        "/seasonal",
        "/farms",
        "/recipes",
        "/journal",
        "/standards",
        "/about",
        "/delivery",
        "/returns",
        "/contact",
        "/privacy",
        "/terms",
        "/help",
    ]
    categories = await CategoryRepository(db).list_published()
    products = await CatalogueRepository(db).list_all_published()
    farms = await FarmRepository(db).list_published()
    recipes = await RecipeRepository(db).list_published()
    articles = await ArticleRepository(db).list_published()

    paths = [
        *static_paths,
        *(f"/category/{entry['slug']}" for entry in categories),
        *(f"/product/{entry['slug']}" for entry in products),
        *(f"/farms/{entry['slug']}" for entry in farms),
        *(f"/recipes/{entry['slug']}" for entry in recipes),
        *(f"/journal/{entry['slug']}" for entry in articles),
    ]
    unique_paths = list(dict.fromkeys(paths))
    urls = "\n".join(
        f"  <url><loc>{escape(_url(settings, path))}</loc></url>" for path in unique_paths
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}\n"
        "</urlset>\n"
    )


async def default_llms_txt(db: Database, settings: Settings) -> str:
    categories = await CategoryRepository(db).list_published()
    products = await CatalogueRepository(db).list_all_published(limit=50)
    lines = [
        "# True Grit",
        "",
        (
            "Traceable organic food from verified farms, with published product, farm, "
            "recipe, and policy pages."
        ),
        "",
        "## Core Pages",
        f"- Home: {_url(settings, '/')}",
        f"- Shop: {_url(settings, '/shop')}",
        f"- Farmers: {_url(settings, '/farms')}",
        f"- Recipes: {_url(settings, '/recipes')}",
        f"- Journal: {_url(settings, '/journal')}",
        f"- Standards: {_url(settings, '/standards')}",
        "",
        "## Product Categories",
        *[
            f"- {entry['name']}: {_url(settings, '/category/' + entry['slug'])}"
            for entry in categories
        ],
        "",
        "## Featured Product URLs",
        *[
            f"- {entry['name']}: {_url(settings, '/product/' + entry['slug'])}"
            for entry in products
        ],
        "",
        "## Policies",
        f"- Delivery: {_url(settings, '/delivery')}",
        f"- Returns: {_url(settings, '/returns')}",
        f"- Privacy: {_url(settings, '/privacy')}",
        f"- Terms: {_url(settings, '/terms')}",
        f"- Help: {_url(settings, '/help')}",
        "",
    ]
    return "\n".join(lines)


async def default_site_documents(db: Database, settings: Settings) -> dict[str, dict[str, Any]]:
    return {
        "robots_txt": {
            "key": "robots_txt",
            "content": default_robots_txt(settings),
            "content_type": SITE_DOCUMENT_TYPES["robots_txt"],
            "updated_at": "",
        },
        "sitemap_xml": {
            "key": "sitemap_xml",
            "content": await default_sitemap_xml(db, settings),
            "content_type": SITE_DOCUMENT_TYPES["sitemap_xml"],
            "updated_at": "",
        },
        "llms_txt": {
            "key": "llms_txt",
            "content": await default_llms_txt(db, settings),
            "content_type": SITE_DOCUMENT_TYPES["llms_txt"],
            "updated_at": "",
        },
    }

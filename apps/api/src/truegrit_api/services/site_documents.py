"""Owner-managed public crawler documents, plus the dynamic sitemap family.

The sitemap is a small index pointing at one sub-sitemap per content type
(products, categories, pages, blog, recipes, farms) — the same shape a large
storefront's generated sitemap takes (an index fanning out to per-type
files), so a future jump to sharded per-type files (`products1.xml`,
`products2.xml`, ...) only ever means adding pagination inside one function,
never restructuring the index. Sub-sitemaps are always generated live from
D1 on request; only the index itself goes through the owner-overridable
``site_documents`` table (so an owner can still hand-edit it if they ever
need to), because the sub-sitemaps are mechanically derived and should never
go stale behind a forgotten manual edit.
"""

from __future__ import annotations

from html import escape
from typing import Any

from truegrit_api.config import Settings
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    ArticleRepository,
    CategoryRepository,
    DiscussionRepository,
    FarmRepository,
    PageRepository,
    RecipeRepository,
)

SITE_DOCUMENT_TYPES = {
    "robots_txt": "text/plain; charset=utf-8",
    "sitemap_xml": "application/xml; charset=utf-8",
    "llms_txt": "text/plain; charset=utf-8",
}

# kind -> (changefreq, priority), matched to how often each content type
# actually changes.
SITEMAP_KINDS: dict[str, tuple[str, str]] = {
    "products": ("weekly", "0.8"),
    "categories": ("monthly", "0.6"),
    "pages": ("monthly", "0.5"),
    "blog": ("weekly", "0.6"),
    "recipes": ("weekly", "0.6"),
    "farms": ("monthly", "0.5"),
    "discussions": ("weekly", "0.3"),
}


def _origin(settings: Settings) -> str:
    return settings.public_storefront_url.rstrip("/")


def _url(settings: Settings, path: str) -> str:
    return f"{_origin(settings)}{path}"


def _urlset(settings: Settings, entries: list[tuple[str, str | None]], kind: str) -> str:
    changefreq, priority = SITEMAP_KINDS[kind]
    rows = []
    for path, lastmod in entries:
        loc = escape(_url(settings, path))
        lastmod_tag = f"<lastmod>{escape(lastmod)}</lastmod>" if lastmod else ""
        rows.append(
            f"  <url><loc>{loc}</loc>{lastmod_tag}"
            f"<changefreq>{changefreq}</changefreq><priority>{priority}</priority></url>"
        )
    body = "\n".join(rows)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{body}\n"
        "</urlset>\n"
    )


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


def sitemap_index_xml(settings: Settings) -> str:
    entries = "\n".join(
        f"  <sitemap><loc>{escape(_url(settings, f'/sitemaps/{kind}.xml'))}</loc></sitemap>"
        for kind in SITEMAP_KINDS
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</sitemapindex>\n"
    )


async def sitemap_products_xml(db: Database, settings: Settings) -> str:
    products, _total = await CatalogueRepository(db).list_all_published()
    entries = [(f"/product/{p['slug']}", p.get("updated_at")) for p in products]
    return _urlset(settings, entries, "products")


async def sitemap_categories_xml(db: Database, settings: Settings) -> str:
    categories = await CategoryRepository(db).list_published()
    entries: list[tuple[str, str | None]] = [(f"/category/{c['slug']}", None) for c in categories]
    return _urlset(settings, entries, "categories")


async def sitemap_pages_xml(db: Database, settings: Settings) -> str:
    pages = await PageRepository(db).list_published()
    entries = [
        ("/" if page["slug"] == "home" else f"/{page['slug']}", page.get("updated_at"))
        for page in pages
    ]
    return _urlset(settings, entries, "pages")


async def sitemap_blog_xml(db: Database, settings: Settings) -> str:
    articles = await ArticleRepository(db).list_published()
    entries = [(f"/blog/{a['slug']}", a.get("published_at") or None) for a in articles]
    return _urlset(settings, entries, "blog")


async def sitemap_recipes_xml(db: Database, settings: Settings) -> str:
    recipes = await RecipeRepository(db).list_published()
    entries: list[tuple[str, str | None]] = [(f"/recipes/{r['slug']}", None) for r in recipes]
    return _urlset(settings, entries, "recipes")


async def sitemap_farms_xml(db: Database, settings: Settings) -> str:
    farms = await FarmRepository(db).list_published()
    entries: list[tuple[str, str | None]] = [(f"/farms/{f['slug']}", None) for f in farms]
    return _urlset(settings, entries, "farms")


async def sitemap_discussions_xml(db: Database, settings: Settings) -> str:
    """Community discussion threads. Same "always live" contract as every
    other sub-sitemap: a newly started (or newly hidden) discussion is
    reflected on the next request, no manual step."""
    discussions = await DiscussionRepository(db).list_all_visible_for_sitemap()
    entries: list[tuple[str, str | None]] = [
        (f"/community/{d['id']}", d.get("updated_at")) for d in discussions
    ]
    return _urlset(settings, entries, "discussions")


SITEMAP_GENERATORS = {
    "products": sitemap_products_xml,
    "categories": sitemap_categories_xml,
    "pages": sitemap_pages_xml,
    "blog": sitemap_blog_xml,
    "recipes": sitemap_recipes_xml,
    "farms": sitemap_farms_xml,
    "discussions": sitemap_discussions_xml,
}


_LLMS_LIST_CAP = 50


async def default_llms_txt(db: Database, settings: Settings) -> str:
    categories = await CategoryRepository(db).list_published()
    products, _total = await CatalogueRepository(db).list_all_published(limit=_LLMS_LIST_CAP)
    articles = (await ArticleRepository(db).list_published())[:_LLMS_LIST_CAP]
    recipes = (await RecipeRepository(db).list_published())[:_LLMS_LIST_CAP]
    lines = [
        "# True Grit",
        "",
        (
            "Traceable organic food from verified farms, with published product, farm, "
            "recipe, blog and community pages."
        ),
        "",
        "## Core Pages",
        f"- Home: {_url(settings, '/')}",
        f"- Shop: {_url(settings, '/shop')}",
        f"- Farmers: {_url(settings, '/farms')}",
        f"- Recipes: {_url(settings, '/recipes')}",
        f"- Blog: {_url(settings, '/blog')}",
        f"- Community: {_url(settings, '/community')}",
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
        "## Blog Articles",
        *[f"- {entry['title']}: {_url(settings, '/blog/' + entry['slug'])}" for entry in articles],
        "",
        "## Recipes",
        *[f"- {entry['title']}: {_url(settings, '/recipes/' + entry['slug'])}" for entry in recipes],
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
            "content": sitemap_index_xml(settings),
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

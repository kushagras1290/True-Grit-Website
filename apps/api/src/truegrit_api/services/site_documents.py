"""Owner-managed public crawler documents, plus the dynamic sitemap family.

The sitemap is a small index pointing at one sub-sitemap per content type
(products, categories, pages, blog, recipes, farms, discussions) — the same
shape a large storefront's generated sitemap takes (an index fanning out to
per-type files), so a future jump to sharded per-type files
(`products1.xml`, `products2.xml`, ...) only ever means adding pagination
inside one function, never restructuring the index. Sub-sitemaps are always
generated live from D1 on request; only the index itself goes through the
owner-overridable ``site_documents`` table (so an owner can still hand-edit
it if they ever need to), because the sub-sitemaps are mechanically derived
and should never go stale behind a forgotten manual edit.

Every generator reads through a repository's `list_slugs_for_sitemap`, which
selects only the slug and timestamp columns a `<url>` renders. That is not an
optimisation detail — the generators used to reuse the storefront's own
listing queries, which assemble prices, inventory, version bodies and
ingredient lists per row. Asking those for the whole catalogue at once
exceeded the Worker CPU limit, so `/sitemaps/products` returned 500 and
`/sitemaps/recipes` timed out, and the storefront published empty urlsets in
their place. Keep sitemap reads on the narrow queries.
"""

from __future__ import annotations

import asyncio
from html import escape
from typing import Any, NamedTuple

from truegrit_api.config import Settings
from truegrit_api.domain.sitemap import SITEMAP_MAX_URLS, w3c_datetime
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

# Storefront landing routes that live in code (`apps/storefront/app/routes.ts`)
# rather than the CMS `pages` table, so no repository query can discover them.
# Without this list the site's main hubs — the shop, the blog index, the farmer
# directory — were absent from the sitemap entirely while every policy page was
# present. They ride in the `pages` file and outrank it on priority because
# they are the entry points crawlers should reach first.
#
# Add a route here only if it is indexable: `/cart`, `/checkout`, `/account/*`,
# `/payment/*`, `/search` and the submission forms are deliberately absent, and
# robots.txt disallows the private ones.
STOREFRONT_LANDING_PATHS: tuple[str, ...] = (
    "/shop",
    "/seasonal",
    "/farms",
    "/recipes",
    "/blog",
    "/community",
    "/contact",
)
_LANDING_PRIORITY = "0.9"
_LANDING_CHANGEFREQ = "weekly"


class SitemapEntry(NamedTuple):
    """One `<url>` row. `changefreq`/`priority` default to the values the kind
    declares in `SITEMAP_KINDS`; only entries that genuinely differ from their
    neighbours (the landing hubs inside `pages`) set them."""

    path: str
    lastmod: object = None
    changefreq: str | None = None
    priority: str | None = None


def _origin(settings: Settings) -> str:
    return settings.public_storefront_url.rstrip("/")


def _url(settings: Settings, path: str) -> str:
    return f"{_origin(settings)}{path}"


def _urlset(settings: Settings, entries: list[SitemapEntry], kind: str) -> str:
    default_changefreq, default_priority = SITEMAP_KINDS[kind]
    rows = []
    for entry in entries[:SITEMAP_MAX_URLS]:
        loc = escape(_url(settings, entry.path))
        # A malformed <lastmod> invalidates the whole file, so an unparseable
        # timestamp is dropped rather than echoed through (see `w3c_datetime`).
        lastmod = w3c_datetime(entry.lastmod)
        lastmod_tag = f"<lastmod>{escape(lastmod)}</lastmod>" if lastmod else ""
        changefreq = entry.changefreq or default_changefreq
        priority = entry.priority or default_priority
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
    # A non-production environment (test/staging/dev) has no admin-set
    # override by default, so without this it silently inherited the
    # production "Allow: /" and was free for any crawler to index --
    # exactly what put test.truegritin.com's product pages into Google.
    # Blocking crawling here is the ceiling; an owner can still relax it for
    # a specific environment via Site Settings > Crawler files if they ever
    # need to (that DB-backed override always wins over this default).
    if settings.app_env != "production":
        return "\n".join(["User-agent: *", "Disallow: /", ""])
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
    products = await CatalogueRepository(db).list_slugs_for_sitemap()
    entries = [SitemapEntry(f"/product/{p['slug']}", p["updated_at"]) for p in products]
    return _urlset(settings, entries, "products")


async def sitemap_categories_xml(db: Database, settings: Settings) -> str:
    categories = await CategoryRepository(db).list_slugs_for_sitemap()
    entries = [SitemapEntry(f"/category/{c['slug']}", c["updated_at"]) for c in categories]
    return _urlset(settings, entries, "categories")


async def sitemap_pages_xml(db: Database, settings: Settings) -> str:
    """CMS pages plus the code-backed landing routes.

    A page published in the admin appears here on the next request with no
    code change — that is the whole contract of this file. The landing paths
    are merged in for routes that have no CMS row at all; a CMS page always
    wins a collision, because it carries a real `lastmod` and an owner may
    have deliberately taken it out of the index.
    """
    pages = await PageRepository(db).list_slugs_for_sitemap()
    entries = [
        SitemapEntry(
            "/" if page["slug"] == "home" else f"/{page['slug']}",
            page["updated_at"],
        )
        for page in pages
    ]
    known = {entry.path for entry in entries}
    entries.extend(
        SitemapEntry(path, None, _LANDING_CHANGEFREQ, _LANDING_PRIORITY)
        for path in STOREFRONT_LANDING_PATHS
        if path not in known
    )
    return _urlset(settings, entries, "pages")


async def sitemap_blog_xml(db: Database, settings: Settings) -> str:
    articles = await ArticleRepository(db).list_slugs_for_sitemap()
    entries = [SitemapEntry(f"/blog/{a['slug']}", a["updated_at"]) for a in articles]
    return _urlset(settings, entries, "blog")


async def sitemap_recipes_xml(db: Database, settings: Settings) -> str:
    recipes = await RecipeRepository(db).list_slugs_for_sitemap()
    entries = [SitemapEntry(f"/recipes/{r['slug']}", r["updated_at"]) for r in recipes]
    return _urlset(settings, entries, "recipes")


async def sitemap_farms_xml(db: Database, settings: Settings) -> str:
    farms = await FarmRepository(db).list_slugs_for_sitemap()
    entries = [SitemapEntry(f"/farms/{f['slug']}", f["updated_at"]) for f in farms]
    return _urlset(settings, entries, "farms")


async def sitemap_discussions_xml(db: Database, settings: Settings) -> str:
    """Community discussion threads. Same "always live" contract as every
    other sub-sitemap: a newly started (or newly hidden) discussion is
    reflected on the next request, no manual step."""
    discussions = await DiscussionRepository(db).list_all_visible_for_sitemap()
    entries = [SitemapEntry(f"/community/{d['id']}", d["updated_at"]) for d in discussions]
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
    # Four independent reads with no data dependency between them -- run
    # concurrently rather than paying their latency serially, since this
    # itself sits on the (now single-key-scoped, see `default_site_document`)
    # public endpoint's hot path.
    categories, (products, _total), articles, recipes = await asyncio.gather(
        CategoryRepository(db).list_published(),
        CatalogueRepository(db).list_all_published(limit=_LLMS_LIST_CAP),
        ArticleRepository(db).list_published(limit=_LLMS_LIST_CAP),
        RecipeRepository(db).list_published(limit=_LLMS_LIST_CAP),
    )
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
        *[
            f"- {entry['title']}: {_url(settings, '/recipes/' + entry['slug'])}"
            for entry in recipes
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


async def default_site_document(db: Database, settings: Settings, key: str) -> dict[str, Any]:
    """Single-key variant of `default_site_documents`, for the public
    per-document endpoint (`GET /site-documents/{key}`).

    That endpoint only ever needs one key, but `default_site_documents`
    unconditionally computes all three -- including `llms_txt`, whose default
    runs four D1 reads (categories/products/articles/recipes). Every
    robots.txt/sitemap.xml request was paying full llms.txt-generation cost
    as a side effect and discarding the result, which is why this became the
    single highest-latency, highest-volume route on the API (p95 in the
    seconds, tens of thousands of requests/day -- `robots.txt` alone is
    fetched by every crawler and bot on essentially every visit). Compute
    only what the caller actually asked for.
    """
    if key == "robots_txt":
        return {
            "key": "robots_txt",
            "content": default_robots_txt(settings),
            "content_type": SITE_DOCUMENT_TYPES["robots_txt"],
            "updated_at": "",
        }
    if key == "sitemap_xml":
        return {
            "key": "sitemap_xml",
            "content": sitemap_index_xml(settings),
            "content_type": SITE_DOCUMENT_TYPES["sitemap_xml"],
            "updated_at": "",
        }
    return {
        "key": "llms_txt",
        "content": await default_llms_txt(db, settings),
        "content_type": SITE_DOCUMENT_TYPES["llms_txt"],
        "updated_at": "",
    }

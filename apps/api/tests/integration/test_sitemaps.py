"""Sitemap generation against the real schema and seed.

These cover the failure that took the live sitemap down: the generators used
to reuse the storefront's listing queries, which assemble prices, inventory,
version bodies and ingredient lists per row. On the Worker that exceeded the
CPU limit, so `/sitemaps/products` returned 500 and `/sitemaps/recipes` timed
out — and because the storefront turned any failure into an empty urlset, the
site served a valid-looking sitemap that told crawlers those sections had no
pages at all.

Substring assertions alone never caught it: on a small local database the
expensive queries still return the right rows. The guard that matters is
`test_query_count_does_not_grow_with_catalogue_size` — it fails if per-row
work creeps back in, whatever the row count.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any
from xml.etree import ElementTree

import pytest
from fastapi.testclient import TestClient

from truegrit_api.config import get_settings
from truegrit_api.domain.sitemap import w3c_datetime
from truegrit_api.platform.database import SQLiteDatabase
from truegrit_api.services.site_documents import (
    SITEMAP_GENERATORS,
    SITEMAP_KINDS,
    STOREFRONT_LANDING_PATHS,
    sitemap_index_xml,
)

SITEMAP_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"


class CountingDatabase:
    """Database proxy that records how many queries pass through it."""

    def __init__(self, inner: SQLiteDatabase) -> None:
        self._inner = inner
        self.queries: list[str] = []

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        self.queries.append(sql)
        return await self._inner.fetch_all(sql, params)

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        self.queries.append(sql)
        return await self._inner.fetch_one(sql, params)

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        return await self._inner.execute(sql, params)

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        await self._inner.batch(statements)


def locs(xml: str) -> list[str]:
    """Parse as XML rather than string-matching, so a malformed document fails
    here instead of silently at a crawler."""
    root = ElementTree.fromstring(xml)
    assert root.tag == f"{SITEMAP_NS}urlset"
    return [element.text or "" for element in root.iter(f"{SITEMAP_NS}loc")]


def paths(xml: str) -> list[str]:
    origin = get_settings().public_storefront_url.rstrip("/")
    return [loc.removeprefix(origin) for loc in locs(xml)]


def add_products(db: SQLiteDatabase, count: int, *, indexing_policy: str = "index") -> None:
    for index in range(count):
        db._conn.execute(  # test-only direct access, mirroring conftest
            "INSERT INTO products (id, internal_name, name, slug, product_type, status,"
            " indexing_policy, created_at, created_by, updated_at, updated_by)"
            " VALUES (?, ?, ?, ?, 'simple', 'published', ?,"
            " '2026-07-01T00:00:00Z', 'usr_admin', '2026-07-02T00:00:00Z', 'usr_admin')",
            (
                f"prd_bulk_{indexing_policy}_{index}",
                f"Bulk {index}",
                f"Bulk {index}",
                f"bulk-{indexing_policy}-{index}",
                indexing_policy,
            ),
        )
    db._conn.commit()


@pytest.mark.anyio
@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
async def test_every_kind_renders_a_well_formed_urlset(db: SQLiteDatabase, kind: str) -> None:
    xml = await SITEMAP_GENERATORS[kind](db, get_settings())
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    locs(xml)  # raises if the document is not parseable XML


@pytest.mark.anyio
@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
async def test_every_kind_is_populated(db: SQLiteDatabase, kind: str) -> None:
    """The seed has content of every type, so a blank file here is the exact
    symptom the live site showed."""
    xml = await SITEMAP_GENERATORS[kind](db, get_settings())
    assert locs(xml), f"/sitemaps/{kind}.xml came back empty"


@pytest.mark.anyio
@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
async def test_lastmod_is_valid_w3c_datetime(db: SQLiteDatabase, kind: str) -> None:
    """D1 mixes `2026-07-23 01:40:00` (SQLite CURRENT_TIMESTAMP) with
    `2026-07-17T00:00:00Z` (the CMS). The space-separated form is not a valid
    W3C datetime and invalidates the file it appears in."""
    xml = await SITEMAP_GENERATORS[kind](db, get_settings())
    stamps = [
        element.text or "" for element in ElementTree.fromstring(xml).iter(f"{SITEMAP_NS}lastmod")
    ]
    for stamp in stamps:
        assert " " not in stamp, f"{kind}: raw SQLite timestamp leaked into <lastmod>"
        assert w3c_datetime(stamp) == stamp, f"{kind}: {stamp!r} is not a W3C datetime"


@pytest.mark.anyio
async def test_products_carry_lastmod(db: SQLiteDatabase) -> None:
    """Regression: the generator read `updated_at` off the storefront's
    assembled product card, which does not carry that column, so no product
    URL ever got a `<lastmod>` even when the endpoint succeeded."""
    xml = await SITEMAP_GENERATORS["products"](db, get_settings())
    root = ElementTree.fromstring(xml)
    urls = list(root.iter(f"{SITEMAP_NS}url"))
    assert urls
    assert all(url.find(f"{SITEMAP_NS}lastmod") is not None for url in urls)


@pytest.mark.anyio
async def test_query_count_does_not_grow_with_catalogue_size(db: SQLiteDatabase) -> None:
    """The guard on the outage itself.

    Adding products must not add queries. The old generator ran four queries
    plus per-row assembly for the whole catalogue at once, which is what blew
    the Worker CPU budget; this fails the moment that pattern returns.
    """
    baseline = CountingDatabase(db)
    await SITEMAP_GENERATORS["products"](baseline, get_settings())

    add_products(db, 200)
    loaded = CountingDatabase(db)
    xml = await SITEMAP_GENERATORS["products"](loaded, get_settings())

    assert len(loaded.queries) == len(baseline.queries) == 1
    assert len(locs(xml)) == len(locs(await SITEMAP_GENERATORS["products"](db, get_settings())))


@pytest.mark.anyio
@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
async def test_no_kind_does_per_row_work(db: SQLiteDatabase, kind: str) -> None:
    """Every sub-sitemap is one flat read. `pages` allows a second query only
    because it has none — its landing paths are a constant."""
    counting = CountingDatabase(db)
    await SITEMAP_GENERATORS[kind](counting, get_settings())
    assert len(counting.queries) == 1, f"{kind} issued {len(counting.queries)} queries"


@pytest.mark.anyio
async def test_noindex_content_is_excluded(db: SQLiteDatabase) -> None:
    """A URL in the sitemap whose page says `noindex` is a contradiction that
    spends crawl budget to reach a page the crawler is told to discard."""
    add_products(db, 3, indexing_policy="noindex")
    xml = await SITEMAP_GENERATORS["products"](db, get_settings())
    assert not [path for path in paths(xml) if "bulk-noindex" in path]


@pytest.mark.anyio
async def test_pages_include_code_backed_landing_routes(db: SQLiteDatabase) -> None:
    """`/shop`, `/blog`, `/farms` and friends are storefront routes with no CMS
    row, so no query can discover them. They were missing from the sitemap
    entirely while every policy page was listed."""
    xml = await SITEMAP_GENERATORS["pages"](db, get_settings())
    listed = paths(xml)
    for path in STOREFRONT_LANDING_PATHS:
        assert path in listed, f"{path} is missing from the pages sitemap"


@pytest.mark.anyio
async def test_pages_have_no_duplicate_urls(db: SQLiteDatabase) -> None:
    """A landing path that later gains a CMS page must not be listed twice."""
    xml = await SITEMAP_GENERATORS["pages"](db, get_settings())
    listed = paths(xml)
    assert len(listed) == len(set(listed))


@pytest.mark.anyio
async def test_newly_published_page_appears_without_a_code_change(db: SQLiteDatabase) -> None:
    """The headline contract: publish a page in the admin and the sitemap
    picks it up on the next request."""
    before = paths(await SITEMAP_GENERATORS["pages"](db, get_settings()))
    assert "/harvest-calendar" not in before

    db._conn.execute(
        "INSERT INTO pages (id, page_type, internal_name, title, slug, template_key, status,"
        " created_at, created_by, updated_at, updated_by)"
        " VALUES ('pag_harvest', 'content', 'Harvest calendar', 'Harvest calendar',"
        " 'harvest-calendar', 'cms_static', 'published',"
        " '2026-07-30T00:00:00Z', 'usr_admin', '2026-07-30T09:15:00Z', 'usr_admin')"
    )
    db._conn.commit()

    after = await SITEMAP_GENERATORS["pages"](db, get_settings())
    assert "/harvest-calendar" in paths(after)
    assert "<lastmod>2026-07-30T09:15:00Z</lastmod>" in after


@pytest.mark.anyio
async def test_unpublishing_a_page_removes_it(db: SQLiteDatabase) -> None:
    """The same contract in reverse — a sitemap that keeps advertising an
    unpublished URL sends crawlers to a 404."""
    db._conn.execute("UPDATE pages SET status = 'unpublished' WHERE slug = 'about'")
    db._conn.commit()
    assert "/about" not in paths(await SITEMAP_GENERATORS["pages"](db, get_settings()))


@pytest.mark.anyio
async def test_page_flipped_to_noindex_leaves_the_sitemap(db: SQLiteDatabase) -> None:
    db._conn.execute("UPDATE pages SET indexing_policy = 'noindex' WHERE slug = 'terms'")
    db._conn.commit()
    assert "/terms" not in paths(await SITEMAP_GENERATORS["pages"](db, get_settings()))


@pytest.mark.anyio
@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
async def test_urls_are_absolute_and_on_the_storefront_origin(
    db: SQLiteDatabase, kind: str
) -> None:
    """Crawlers reject a sitemap whose URLs sit on another host, and a relative
    <loc> is invalid outright."""
    origin = get_settings().public_storefront_url.rstrip("/")
    for loc in locs(await SITEMAP_GENERATORS[kind](db, get_settings())):
        assert loc.startswith(f"{origin}/")


def test_index_lists_every_kind() -> None:
    """The index and the generator table must not drift: a kind present in one
    and absent from the other is either an unreachable file or a 404 link."""
    xml = sitemap_index_xml(get_settings())
    root = ElementTree.fromstring(xml)
    assert root.tag == f"{SITEMAP_NS}sitemapindex"
    listed = {(element.text or "").rsplit("/", 1)[-1] for element in root.iter(f"{SITEMAP_NS}loc")}
    assert listed == {f"{kind}.xml" for kind in SITEMAP_KINDS}


@pytest.mark.parametrize("kind", sorted(SITEMAP_KINDS))
def test_endpoint_serves_xml_for_every_kind(client: TestClient, kind: str) -> None:
    """Through the HTTP layer the storefront actually calls. A non-200 here is
    what the storefront turns into a 503, and what used to become a blank
    sitemap."""
    response = client.get(f"/v1/public/sitemaps/{kind}")
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("application/xml")
    assert locs(response.text), f"/sitemaps/{kind} served an empty urlset"


def test_endpoint_rejects_an_unknown_kind(client: TestClient) -> None:
    assert client.get("/v1/public/sitemaps/nonsense").status_code == 404


def test_landing_paths_are_real_storefront_routes() -> None:
    """A landing path that no longer resolves would put a 404 in the sitemap.
    Checked against the storefront's route table, the single source of truth."""
    routes = (
        __import__("pathlib")
        .Path(__file__)
        .parents[3]
        .joinpath("storefront/app/routes.ts")
        .read_text(encoding="utf-8")
    )
    declared = set(re.findall(r'route\("([^"]+)"', routes))
    for path in STOREFRONT_LANDING_PATHS:
        assert path.lstrip("/") in declared, f"{path} is not a storefront route"

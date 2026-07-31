"""`<lastmod>` normalisation.

Timestamps reach the sitemap in whichever shape wrote them: SQLite's
`CURRENT_TIMESTAMP` gives `2026-07-23 01:40:00`, the CMS writes
`2026-07-17T00:00:00Z`. Only the second is a valid W3C datetime, and one
malformed value invalidates the entire sitemap file for a crawler.
"""

from __future__ import annotations

import pytest

from truegrit_api.domain.sitemap import SITEMAP_MAX_URLS, w3c_datetime


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        # SQLite CURRENT_TIMESTAMP — the form that was being emitted raw.
        ("2026-07-23 01:40:00", "2026-07-23T01:40:00Z"),
        # Already valid: passed through untouched, timezone preserved.
        ("2026-07-17T00:00:00Z", "2026-07-17T00:00:00Z"),
        ("2026-07-17T00:00:00+05:30", "2026-07-17T00:00:00+05:30"),
        # Offsets without the separating colon are legal ISO 8601 but not
        # valid W3C datetime, so they get one.
        ("2026-07-17T00:00:00+0530", "2026-07-17T00:00:00+05:30"),
        # Date-only is a complete W3C datetime on its own.
        ("2026-07-17", "2026-07-17"),
        # Seconds are optional in the source, required by our output shape.
        ("2026-07-23 01:40", "2026-07-23T01:40:00Z"),
        # Fractional seconds carry no meaning for crawlers; dropped.
        ("2026-07-23 01:40:00.123456", "2026-07-23T01:40:00Z"),
        ("  2026-07-23 01:40:00  ", "2026-07-23T01:40:00Z"),
    ],
)
def test_normalizes_stored_timestamps(stored: str, expected: str) -> None:
    assert w3c_datetime(stored) == expected


@pytest.mark.parametrize(
    "value",
    [None, "", "not-a-date", "17/07/2026", "2026-07", 20260717, 0, [], {}],
)
def test_drops_unusable_values(value: object) -> None:
    """An omitted <lastmod> is valid and merely lets the crawler judge
    freshness itself. A malformed one breaks the whole file, so anything
    unparseable must be dropped rather than echoed through."""
    assert w3c_datetime(value) is None


def test_url_cap_matches_the_protocol_limit() -> None:
    """sitemaps.org caps one file at 50,000 URLs. Exceeding it means sharding
    the kind behind the index, not raising this number."""
    assert SITEMAP_MAX_URLS == 50_000

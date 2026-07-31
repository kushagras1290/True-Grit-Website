"""Sitemap rules shared by the repositories that feed the sitemap and the
service that renders it.

Two things live here because both layers need them and neither owns the other:
the per-file URL cap from the sitemaps.org protocol, and `<lastmod>`
normalisation. Timestamps reach us in whichever shape wrote them — SQLite's
`CURRENT_TIMESTAMP` produces `2026-07-23 01:40:00` while the CMS writes
`2026-07-17T00:00:00Z` — and the space-separated form is not a valid W3C
datetime, so it has to be normalised at the point of rendering rather than
trusted from the column.
"""

from __future__ import annotations

import re

# sitemaps.org caps a single sitemap file at 50,000 URLs. Every generator
# stops here; passing it means the kind needs sharding behind the index
# (`products1.xml`, `products2.xml`, ...), not a bigger number.
SITEMAP_MAX_URLS = 50_000

# `YYYY-MM-DD` optionally followed by a time, with either the W3C `T`
# separator or SQLite's space, and an optional timezone suffix.
_TIMESTAMP_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:[T ](?P<time>\d{2}:\d{2}(?::\d{2})?)(?:\.\d+)?"
    r"(?P<zone>Z|[+-]\d{2}:?\d{2})?)?$"
)


def w3c_datetime(value: object) -> str | None:
    """Normalise a stored timestamp to the W3C datetime `<lastmod>` requires.

    Returns `None` for anything unparseable — an omitted `<lastmod>` is valid
    and simply tells a crawler to decide freshness for itself, whereas a
    malformed one invalidates the whole sitemap file, so a bad value must
    never be echoed through.
    """
    if not isinstance(value, str):
        return None
    match = _TIMESTAMP_RE.match(value.strip())
    if match is None:
        return None
    date = match.group("date")
    time = match.group("time")
    if time is None:
        return date
    if len(time) == 5:  # HH:MM — the spec's seconds are optional but D1 stores them
        time = f"{time}:00"
    zone = match.group("zone") or "Z"
    if zone != "Z" and ":" not in zone:
        zone = f"{zone[:3]}:{zone[3:]}"
    return f"{date}T{time}{zone}"

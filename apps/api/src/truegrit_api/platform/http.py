"""Minimal outbound HTTP for the local/dev runtime.

Only a JSON GET is needed today (fetching Google's JWKS). It uses the standard
library so the API keeps a zero-runtime-dependency footprint, and every call is
bounded by an explicit timeout. On Cloudflare Workers, outbound requests must go
through the platform `fetch`; swap this module's implementation there.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

_DEFAULT_TIMEOUT_SECONDS = 5.0
_MAX_RESPONSE_BYTES = 1_000_000


class HttpError(Exception):
    """An outbound HTTP request failed or returned an unusable response."""


def get_json(url: str, *, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> Any:
    """GET `url` and parse the JSON body. Raises HttpError on any failure."""
    request = urllib.request.Request(url, headers={"accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            if status != 200:
                raise HttpError(f"GET {url} returned {status}.")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HttpError(f"GET {url} failed: {exc}") from exc
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise HttpError(f"GET {url} response exceeded {_MAX_RESPONSE_BYTES} bytes.")
    try:
        return json.loads(raw.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise HttpError(f"GET {url} returned invalid JSON.") from exc


async def get_json_async(url: str) -> Any:
    """GET `url` and parse JSON, using the Cloudflare Workers `fetch` when
    available (the runtime has no raw sockets, so stdlib urllib fails there) and
    falling back to the synchronous `get_json` locally and in tests."""
    try:
        from js import fetch as js_fetch  # Cloudflare Workers runtime only
    except (ImportError, ModuleNotFoundError):
        return get_json(url)
    try:
        response = await js_fetch(url)
    except Exception as exc:  # a JS fetch rejection surfaces as a generic error
        raise HttpError(f"GET {url} failed: {exc}") from exc
    if not response.ok:
        raise HttpError(f"GET {url} returned {response.status}.")
    text = await response.text()
    try:
        return json.loads(str(text))
    except json.JSONDecodeError as exc:
        raise HttpError(f"GET {url} returned invalid JSON.") from exc

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


def _post_json_stdlib(url: str, payload: bytes, headers: dict[str, str]) -> Any:
    request = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=_DEFAULT_TIMEOUT_SECONDS) as response:
            if response.status not in (200, 201):
                raise HttpError(f"POST {url} returned {response.status}.")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HttpError(f"POST {url} failed: {exc}") from exc
    return json.loads(raw.decode("utf-8"))


async def post_json_async(url: str, *, body: Any, headers: dict[str, str] | None = None) -> Any:
    """POST a JSON body and parse the JSON response, using the Workers `fetch`
    when available and stdlib urllib as a local/test fallback."""
    request_headers = {"content-type": "application/json", "accept": "application/json"}
    if headers:
        request_headers.update(headers)
    payload = json.dumps(body)
    try:
        from js import Object  # Cloudflare Workers runtime only
        from js import fetch as js_fetch
        from pyodide.ffi import to_js
    except (ImportError, ModuleNotFoundError):
        return _post_json_stdlib(url, payload.encode("utf-8"), request_headers)
    options = to_js(
        {"method": "POST", "headers": request_headers, "body": payload},
        dict_converter=Object.fromEntries,
    )
    try:
        response = await js_fetch(url, options)
    except Exception as exc:
        raise HttpError(f"POST {url} failed: {exc}") from exc
    text = await response.text()
    if not response.ok:
        raise HttpError(f"POST {url} returned {response.status}: {str(text)[:200]}")
    try:
        return json.loads(str(text))
    except json.JSONDecodeError as exc:
        raise HttpError(f"POST {url} returned invalid JSON.") from exc

"""Google Sheets read/write for the currency-rates manual-tuning round trip.

Server-to-server only: a service account, no human OAuth sign-in flow.
Google's service-account grant needs an RS256-signed JWT assertion, and
Pyodide has no usable RSA-signing library in this Workers runtime, so
signing goes through the Workers-native Web Crypto API via the same
`js`-module bridge `platform/http.py` already uses for `fetch`. That makes
this module Workers-only -- there is no local-dev fallback, the same shape
`services/support_bot.py`'s `UnavailableChat` documents for Workers AI: some
integrations can only be exercised on a deployed Worker.
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any

from truegrit_api.config import Settings
from truegrit_api.platform.http import HttpError, get_json_async, post_form_async, put_json_async

_TOKEN_URL: str = "https://oauth2.googleapis.com/token"
_SHEETS_BASE: str = "https://sheets.googleapis.com/v4/spreadsheets"
_SCOPE: str = "https://www.googleapis.com/auth/spreadsheets"
_TOKEN_LIFETIME_SECONDS: int = 3600


class GoogleSheetsError(HttpError):
    """A Google Sheets call could not be completed."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _pem_to_der(pem: str) -> bytes:
    """Strip PEM armor and decode the base64 body to raw PKCS8 DER bytes."""
    lines = [line.strip() for line in pem.strip().splitlines()]
    body = "".join(line for line in lines if line and not line.startswith("-----"))
    try:
        return base64.b64decode(body)
    except (ValueError, TypeError) as exc:
        raise GoogleSheetsError("The Google Sheets private key is not valid PEM.") from exc


async def _sign_jwt(settings: Settings) -> str:
    """Build and RS256-sign a service-account JWT assertion via the
    Workers-native Web Crypto API. Raises GoogleSheetsError outside a
    deployed Worker -- there is no Python RSA fallback in this runtime."""
    try:
        from js import Object
        from js import crypto as js_crypto
        from pyodide.ffi import to_js
    except (ImportError, ModuleNotFoundError) as exc:
        raise GoogleSheetsError(
            "Google Sheets sync requires the Workers runtime; it cannot run in local dev."
        ) from exc

    now = int(time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    claims = {
        "iss": settings.google_sheets_client_email,
        "scope": _SCOPE,
        "aud": _TOKEN_URL,
        "iat": now,
        "exp": now + _TOKEN_LIFETIME_SECONDS,
    }
    signing_input = (
        f"{_b64url(json.dumps(header, separators=(',', ':')).encode('utf-8'))}."
        f"{_b64url(json.dumps(claims, separators=(',', ':')).encode('utf-8'))}"
    )

    key_der = _pem_to_der(settings.google_sheets_private_key)
    algorithm = to_js(
        {"name": "RSASSA-PKCS1-v1_5", "hash": "SHA-256"}, dict_converter=Object.fromEntries
    )
    try:
        crypto_key = await js_crypto.subtle.importKey(
            "pkcs8", to_js(key_der), algorithm, False, to_js(["sign"])
        )
        signature = await js_crypto.subtle.sign(
            to_js({"name": "RSASSA-PKCS1-v1_5"}, dict_converter=Object.fromEntries),
            crypto_key,
            to_js(signing_input.encode("utf-8")),
        )
    except Exception as exc:  # a WebCrypto rejection surfaces as a generic JS error
        raise GoogleSheetsError(f"Could not sign the Google Sheets assertion: {exc}") from exc
    signature_bytes = bytes(bytearray(signature.to_py()))
    return f"{signing_input}.{_b64url(signature_bytes)}"


async def _access_token(settings: Settings) -> str:
    """Not cached: Workers isolates are short-lived and shared-nothing, the
    same reasoning `services.payments._paypal_access_token` documents for its
    own token fetch -- one extra round trip per sync is the cheaper mistake."""
    assertion = await _sign_jwt(settings)
    try:
        result = await post_form_async(
            _TOKEN_URL,
            form={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": assertion,
            },
        )
    except HttpError as exc:
        raise GoogleSheetsError("Could not authenticate with Google Sheets.") from exc
    token = (result or {}).get("access_token")
    if not token:
        raise GoogleSheetsError("Google did not return an access token.")
    return str(token)


async def read_values(settings: Settings, *, cell_range: str) -> list[list[str]]:
    """Read a rectangular range (e.g. `"A1:D200"`) as rows of string cells.
    A row shorter than the widest row in the sheet comes back short, never
    padded -- callers must index defensively."""
    if not settings.google_sheets_configured:
        raise GoogleSheetsError("Google Sheets is not configured.")
    token = await _access_token(settings)
    url = f"{_SHEETS_BASE}/{settings.google_sheets_spreadsheet_id}/values/{cell_range}"
    try:
        result = await get_json_async(url, headers={"authorization": f"Bearer {token}"})
    except HttpError as exc:
        raise GoogleSheetsError("Could not read the Google Sheet.") from exc
    values = (result or {}).get("values")
    return [[str(cell) for cell in row] for row in values] if isinstance(values, list) else []


async def write_values(settings: Settings, *, cell_range: str, values: list[list[Any]]) -> None:
    """Overwrite a range with `values` (a list of rows). Cells beyond the
    given range are left untouched -- callers own how much of the sheet a
    write clears versus preserves."""
    if not settings.google_sheets_configured:
        raise GoogleSheetsError("Google Sheets is not configured.")
    token = await _access_token(settings)
    url = (
        f"{_SHEETS_BASE}/{settings.google_sheets_spreadsheet_id}/values/{cell_range}"
        "?valueInputOption=RAW"
    )
    try:
        await put_json_async(
            url, body={"values": values}, headers={"authorization": f"Bearer {token}"}
        )
    except HttpError as exc:
        raise GoogleSheetsError("Could not write to the Google Sheet.") from exc

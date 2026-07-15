"""Verify Facebook Login access tokens.

The storefront receives a user access token from the Facebook JavaScript SDK.
The API verifies that token with Meta's Graph API before linking it to a
customer account.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass
from time import time
from typing import Any
from urllib.parse import urlencode

from truegrit_api.errors import AuthenticationError
from truegrit_api.platform.http import HttpError, get_json_async

FACEBOOK_GRAPH_BASE = "https://graph.facebook.com"
FACEBOOK_GRAPH_VERSION = "v25.0"


class FacebookAuthError(AuthenticationError):
    """A Facebook access token is missing, invalid, or unusable for login."""


@dataclass(frozen=True)
class FacebookIdentity:
    subject: str
    email: str
    name: str


class FacebookTokenVerifier:
    """Verifies Facebook user access tokens against the Graph API."""

    def __init__(
        self,
        *,
        json_fetcher=get_json_async,
        clock=time,
        graph_version: str = FACEBOOK_GRAPH_VERSION,
    ) -> None:
        self._json_fetcher = json_fetcher
        self._clock = clock
        self._base_url = f"{FACEBOOK_GRAPH_BASE}/{graph_version}"

    async def verify(self, access_token: str, *, app_id: str, app_secret: str) -> FacebookIdentity:
        if not app_id or not app_secret:
            raise FacebookAuthError("Facebook sign-in is not configured.")
        token = access_token.strip()
        if not token:
            raise FacebookAuthError("Facebook sign-in token is missing.")

        debug = await self._get_json(
            f"{self._base_url}/debug_token?"
            + urlencode({"input_token": token, "access_token": f"{app_id}|{app_secret}"})
        )
        data = debug.get("data") if isinstance(debug, dict) else None
        if not isinstance(data, dict) or not data.get("is_valid"):
            raise FacebookAuthError("Facebook sign-in token is invalid.")
        if str(data.get("app_id", "")) != app_id:
            raise FacebookAuthError("Facebook sign-in token was issued for another app.")
        subject = str(data.get("user_id") or "").strip()
        if not subject:
            raise FacebookAuthError("Facebook sign-in token is missing account details.")
        expires_at = data.get("expires_at")
        if isinstance(expires_at, int | float) and expires_at <= self._clock():
            raise FacebookAuthError("Facebook sign-in token has expired.")

        profile = await self._get_json(
            f"{self._base_url}/me?"
            + urlencode({"fields": "id,name,email", "access_token": token})
        )
        if not isinstance(profile, dict) or str(profile.get("id", "")).strip() != subject:
            raise FacebookAuthError("Facebook sign-in token account could not be verified.")

        email = str(profile.get("email") or "").strip().lower()
        name = str(profile.get("name") or "").strip() or "Facebook member"
        if not email:
            raise FacebookAuthError("Facebook did not provide an email address for this account.")

        return FacebookIdentity(subject=subject, email=email, name=name)

    async def _get_json(self, url: str) -> Any:
        try:
            result = self._json_fetcher(url)
            return await result if inspect.isawaitable(result) else result
        except HttpError as exc:
            raise FacebookAuthError("Could not reach Facebook to verify sign-in.") from exc


_default_verifier = FacebookTokenVerifier()


async def verify_facebook_access_token(
    access_token: str, *, app_id: str, app_secret: str
) -> FacebookIdentity:
    """Verify a Facebook access token using the shared verifier."""
    return await _default_verifier.verify(access_token, app_id=app_id, app_secret=app_secret)

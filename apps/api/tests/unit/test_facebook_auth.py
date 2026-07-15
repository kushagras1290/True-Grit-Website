"""Unit tests for Facebook access token verification."""

from __future__ import annotations

import asyncio

import pytest

from truegrit_api.auth.facebook import (
    FacebookAuthError,
    FacebookIdentity,
    FacebookTokenVerifier,
)

APP_ID = "facebook-app-id"
APP_SECRET = "facebook-app-secret"
NOW = 1_720_000_000


def run_verify(fetcher, token: str = "user-token") -> FacebookIdentity:
    verifier = FacebookTokenVerifier(json_fetcher=fetcher, clock=lambda: NOW)
    return asyncio.run(verifier.verify(token, app_id=APP_ID, app_secret=APP_SECRET))


def facebook_fetcher(url: str):
    if "/debug_token?" in url:
        return {
            "data": {
                "app_id": APP_ID,
                "is_valid": True,
                "user_id": "fb-user-123",
                "expires_at": NOW + 3600,
            }
        }
    if "/me?" in url:
        return {"id": "fb-user-123", "name": "Facebook Member", "email": "fb@example.com"}
    raise AssertionError(f"unexpected URL: {url}")


def test_accepts_valid_facebook_token():
    identity = run_verify(facebook_fetcher)
    assert identity == FacebookIdentity(
        subject="fb-user-123", email="fb@example.com", name="Facebook Member"
    )


def test_rejects_unconfigured_facebook_login():
    verifier = FacebookTokenVerifier(json_fetcher=facebook_fetcher, clock=lambda: NOW)
    with pytest.raises(FacebookAuthError, match="not configured"):
        asyncio.run(verifier.verify("user-token", app_id="", app_secret=APP_SECRET))


def test_rejects_token_for_another_app():
    def fetcher(url: str):
        if "/debug_token?" in url:
            return {
                "data": {
                    "app_id": "other-app",
                    "is_valid": True,
                    "user_id": "fb-user-123",
                    "expires_at": NOW + 3600,
                }
            }
        return {"id": "fb-user-123", "name": "Facebook Member", "email": "fb@example.com"}

    with pytest.raises(FacebookAuthError, match="another app"):
        run_verify(fetcher)


def test_rejects_profile_without_email():
    def fetcher(url: str):
        if "/debug_token?" in url:
            return {
                "data": {
                    "app_id": APP_ID,
                    "is_valid": True,
                    "user_id": "fb-user-123",
                    "expires_at": NOW + 3600,
                }
            }
        return {"id": "fb-user-123", "name": "Facebook Member"}

    with pytest.raises(FacebookAuthError, match="email"):
        run_verify(fetcher)

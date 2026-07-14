"""Unit tests for settings-derived CORS origins and cookie security."""

from __future__ import annotations

from truegrit_api.config import Settings


def test_allowed_origins_includes_loopback_siblings():
    settings = Settings(
        public_storefront_url="http://localhost:5173",
        public_admin_url="http://localhost:5174",
    )
    origins = settings.allowed_origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5174" in origins
    assert "http://127.0.0.1:5174" in origins


def test_allowed_origins_maps_127_to_localhost():
    settings = Settings(
        public_storefront_url="http://127.0.0.1:5173",
        public_admin_url="http://127.0.0.1:5174",
    )
    assert "http://localhost:5173" in settings.allowed_origins


def test_allowed_origins_leaves_real_domains_untouched():
    settings = Settings(
        public_storefront_url="https://shop.example.com",
        public_admin_url="https://admin.example.com",
    )
    assert settings.allowed_origins == [
        "https://shop.example.com",
        "https://admin.example.com",
    ]


def test_cookie_secure_is_forced_for_samesite_none():
    assert Settings(session_cookie_samesite="none").cookie_secure is True


def test_cookie_secure_follows_environment_for_lax():
    assert Settings(app_env="development", session_cookie_samesite="lax").cookie_secure is False
    assert Settings(app_env="production", session_cookie_samesite="lax").cookie_secure is True

"""Unit tests for settings-derived CORS origins and cookie security."""

from __future__ import annotations

import re
from pathlib import Path

from truegrit_api.config import Settings

WRANGLER_CONFIG = Path(__file__).parents[2] / "wrangler.jsonc"


def test_allowed_origins_includes_loopback_siblings():
    settings = Settings(
        public_storefront_url="http://localhost:5173",
        public_admin_url="http://localhost:5174",
        public_process_url="http://localhost:5175",
        public_language_url="http://localhost:5176",
    )
    origins = settings.allowed_origins
    assert "http://localhost:5173" in origins
    assert "http://127.0.0.1:5173" in origins
    assert "http://localhost:5174" in origins
    assert "http://127.0.0.1:5174" in origins
    assert "http://localhost:5175" in origins
    assert "http://127.0.0.1:5175" in origins
    assert "http://localhost:5176" in origins
    assert "http://127.0.0.1:5176" in origins


def test_allowed_origins_maps_127_to_localhost():
    settings = Settings(
        public_storefront_url="http://127.0.0.1:5173",
        public_admin_url="http://127.0.0.1:5174",
        public_process_url="http://127.0.0.1:5175",
        public_language_url="http://127.0.0.1:5176",
    )
    assert "http://localhost:5173" in settings.allowed_origins


def test_allowed_origins_leaves_real_domains_untouched():
    settings = Settings(
        public_storefront_url="https://shop.example.com",
        public_admin_url="https://admin.example.com",
        public_process_url="https://process.example.com",
        public_language_url="https://lang.example.com",
    )
    assert settings.allowed_origins == [
        "https://shop.example.com",
        "https://admin.example.com",
        "https://process.example.com",
        "https://lang.example.com",
    ]


def test_cookie_secure_is_forced_for_samesite_none():
    assert Settings(session_cookie_samesite="none").cookie_secure is True


def test_cookie_secure_follows_environment_for_lax():
    assert Settings(app_env="development", session_cookie_samesite="lax").cookie_secure is False
    assert Settings(app_env="production", session_cookie_samesite="lax").cookie_secure is True


def test_password_writes_never_exceed_verification_budget():
    settings = Settings(pbkdf2_iterations=600_000, pbkdf2_verify_max_iterations=50_000)
    assert settings.pbkdf2_write_iterations == 50_000


def test_every_worker_environment_uses_cpu_safe_password_budget():
    config = WRANGLER_CONFIG.read_text(encoding="utf-8")
    for variable in ("PBKDF2_ITERATIONS", "PBKDF2_VERIFY_MAX_ITERATIONS"):
        values = [int(value) for value in re.findall(rf'"{variable}":\s*"(\d+)"', config)]
        assert values, f"{variable} is missing from wrangler.jsonc"
        assert all(value <= 50_000 for value in values), (
            f"{variable} exceeds the Python Worker CPU budget: {values}"
        )

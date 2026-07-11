"""Validated application configuration.

Cloudflare bindings are not ordinary environment variables; they are resolved in
the platform layer. Everything here is plain configuration, validated once.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    public_storefront_url: str = "http://localhost:5173"
    public_admin_url: str = "http://localhost:5174"
    default_market: str = "IN"
    default_currency: str = "INR"
    session_cookie_name: str = "tg_session"
    session_lifetime_hours: int = 72
    preview_token_lifetime_minutes: int = 30

    @property
    def allowed_origins(self) -> list[str]:
        return [self.public_storefront_url, self.public_admin_url]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

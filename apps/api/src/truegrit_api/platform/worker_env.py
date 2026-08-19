"""Bridge Cloudflare Worker bindings into pydantic settings safely."""

from __future__ import annotations

import os
from typing import Any

from truegrit_api.config import Settings, get_settings


def public_worker_origins(env: Any) -> set[str]:
    """Origins that may receive credentialed emergency Worker responses."""

    origins = {
        value
        for value in (
            getattr(env, "PUBLIC_ADMIN_URL", ""),
            getattr(env, "PUBLIC_STOREFRONT_URL", ""),
            getattr(env, "PUBLIC_PROCESS_URL", ""),
            getattr(env, "PUBLIC_LANGUAGE_URL", ""),
            getattr(env, "PUBLIC_SEO_URL", ""),
        )
        if value
    }
    if getattr(env, "PUBLIC_SEO_URL", ""):
        return origins
    deployed_seo_origins = {
        "development": "https://seotest.truegritin.com",
        "staging": "https://seostag.truegritin.com",
        "production": "https://seo.truegritin.com",
    }
    fallback = deployed_seo_origins.get(getattr(env, "APP_ENV", ""))
    if fallback and any("truegritin.com" in origin for origin in origins):
        origins.add(fallback)
    return origins


def bridge_worker_env(env: Any) -> None:
    """Refresh text bindings for the current request.

    Cloudflare may reuse an existing isolate after a secret-only deployment.
    Copying bindings only during application cold start therefore leaves
    pydantic's cached settings on the previous secret values. Refreshing the
    text bindings and clearing the settings cache makes secret rotation take
    effect without rebuilding the FastAPI application.
    """

    for field_name in Settings.model_fields:
        key = field_name.upper()
        try:
            value = getattr(env, key)
        except AttributeError:
            continue
        if isinstance(value, str):
            os.environ[key] = value
    get_settings.cache_clear()

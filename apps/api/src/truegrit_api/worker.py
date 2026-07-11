"""Cloudflare Python Workers entry point.

Verify the exact ASGI bridge against current Cloudflare documentation at deploy
time — Python Workers are beta and the adapter surface can change. Business
code stays portable either way (ADR-003).
"""

from __future__ import annotations

from typing import Any


async def on_fetch(request: Any, env: Any) -> Any:
    # Imported lazily so this module stays importable outside the Workers runtime.
    from workers import WorkerEntrypoint  # noqa: F401  (runtime-provided)

    from truegrit_api.main import create_app
    from truegrit_api.platform.d1 import D1Database

    app = create_app(db=D1Database(env.DB))

    import asgi  # runtime-provided ASGI bridge

    return await asgi.fetch(app, request, env)

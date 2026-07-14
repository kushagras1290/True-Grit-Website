"""Cloudflare Python Workers entry point.

Deployed with ``pywrangler`` (the ``workers-py`` CLI), which bundles FastAPI,
pydantic, and the Workers runtime SDK (the ``workers`` and ``asgi`` modules)
into the Worker. Only this thin adapter is Workers-specific; the FastAPI
application is portable business code (ADR-003).

The current ASGI bridge follows the official pattern documented at
https://developers.cloudflare.com/workers/languages/python/packages/fastapi/ —
verify it against those docs at deploy time, as Python Workers are in beta.
"""

from __future__ import annotations

from typing import Any

from workers import WorkerEntrypoint

import asgi

from truegrit_api.main import create_app
from truegrit_api.platform.d1 import D1Database

# Build the FastAPI application once per isolate. The D1 binding is resolved
# from ``env`` on first request (it is not available at module-import time) and
# reused for the isolate's lifetime.
_app: Any = None


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        global _app
        if _app is None:
            _app = create_app(db=D1Database(self.env.DB))
        return await asgi.fetch(_app, request, self.env)

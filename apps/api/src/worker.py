"""Cloudflare Python Workers entry point.

This module lives at ``src/worker.py`` (outside the ``truegrit_api`` package) on
purpose: Cloudflare bundles the directory that contains ``main`` as the module
root, so keeping the entry one level up makes ``truegrit_api`` a real importable
package inside the Worker. Placing the entry inside the package instead flattens
its contents to the bundle root and breaks every ``import truegrit_api.*``.

Deployed with ``pywrangler`` (the ``workers-py`` CLI), which bundles FastAPI,
pydantic, and the Workers runtime SDK (the ``workers`` and ``asgi`` modules)
into the Worker. Only this thin adapter is Workers-specific; the FastAPI
application is portable business code (ADR-003). The ASGI bridge follows
https://developers.cloudflare.com/workers/languages/python/packages/fastapi/.
"""

import os
from typing import Any

from workers import WorkerEntrypoint

import asgi

from truegrit_api.config import Settings
from truegrit_api.main import create_app
from truegrit_api.platform.d1 import D1Database
from truegrit_api.platform.media_store import R2MediaStore

# Build the FastAPI application once per isolate. The D1 binding is resolved
# from ``env`` on first request (it is not available at module-import time) and
# reused for the isolate's lifetime.
_app: Any = None


def _bridge_worker_env(env: Any) -> None:
    """Expose Worker ``vars``/secrets to pydantic settings.

    On Cloudflare Python Workers, configuration values live on the ``env``
    object, not the process environment — but ``Settings`` (pydantic-settings)
    reads ``os.environ``. Without this bridge every setting would silently fall
    back to its default (localhost CORS origins, Google sign-in disabled, etc.).
    Each Settings field is matched to an upper-cased Worker var; only string
    values are copied, so bindings (DB, R2, KV, Queues) are ignored.
    """
    for field_name in Settings.model_fields:
        key = field_name.upper()
        try:
            value = getattr(env, key)
        except AttributeError:
            continue
        if isinstance(value, str):
            os.environ[key] = value


class Default(WorkerEntrypoint):
    async def fetch(self, request: Any) -> Any:
        global _app
        if _app is None:
            _bridge_worker_env(self.env)
            _app = create_app(
                db=D1Database(self.env.DB),
                media=R2MediaStore(self.env.MEDIA_BUCKET),
            )
        return await asgi.fetch(_app, request, self.env)

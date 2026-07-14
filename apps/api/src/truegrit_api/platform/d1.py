"""Cloudflare D1 adapter — used only inside the Workers runtime.

Kept import-safe outside Workers: nothing here imports `js` at module load.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def _to_py(value: Any) -> Any:
    """Return a native Python value from a D1 result element.

    Depending on the Workers/Pyodide runtime, D1 results arrive either as
    Pyodide ``JsProxy`` objects (which expose ``.to_py()``) or as already
    converted Python ``list``/``dict`` values. Calling ``.to_py()`` blindly
    raises ``AttributeError`` on the latter, so convert only when needed.
    """
    to_py = getattr(value, "to_py", None)
    return to_py() if callable(to_py) else value


class D1Database:
    """Wraps the Worker `env.DB` binding behind the `Database` protocol."""

    def __init__(self, binding: Any):
        self._db = binding

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        result = await self._db.prepare(sql).bind(*params).all()
        rows = _to_py(result.results)
        return [dict(_to_py(row)) for row in rows]

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        row = await self._db.prepare(sql).bind(*params).first()
        if row is None:
            return None
        return dict(_to_py(row))

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        result = await self._db.prepare(sql).bind(*params).run()
        meta = _to_py(result.meta)
        return int(meta.get("changes", 0) or 0)

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        prepared = [self._db.prepare(sql).bind(*params) for sql, params in statements]
        await self._db.batch(prepared)

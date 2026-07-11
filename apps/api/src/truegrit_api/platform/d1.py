"""Cloudflare D1 adapter — used only inside the Workers runtime.

Kept import-safe outside Workers: nothing here imports `js` at module load.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any


class D1Database:
    """Wraps the Worker `env.DB` binding behind the `Database` protocol."""

    def __init__(self, binding: Any):
        self._db = binding

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        result = await self._db.prepare(sql).bind(*params).all()
        return [dict(row) for row in result.results.to_py()]

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        row = await self._db.prepare(sql).bind(*params).first()
        return dict(row.to_py()) if row is not None else None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        result = await self._db.prepare(sql).bind(*params).run()
        meta = result.meta.to_py()
        return int(meta.get("changes", 0))

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        prepared = [self._db.prepare(sql).bind(*params) for sql, params in statements]
        await self._db.batch(prepared)

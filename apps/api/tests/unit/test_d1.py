from __future__ import annotations

import asyncio
from typing import Any

from truegrit_api.platform.d1 import D1Database


class _Prepared:
    def __init__(self) -> None:
        self.params: tuple[Any, ...] = ()

    def bind(self, *params: Any) -> _Prepared:
        self.params = params
        return self

    async def all(self) -> Any:
        return type(
            "Result",
            (),
            {"results": [{"id": "one"}], "meta": {"rows_read": 1, "served_by_primary": False}},
        )()

    async def first(self) -> dict[str, str]:
        return {"id": "one"}

    async def run(self) -> Any:
        return type("Result", (), {"meta": {"changes": 1, "rows_written": 1}})()


class _Session:
    def prepare(self, sql: str) -> _Prepared:
        return _Prepared()

    async def batch(self, statements: list[_Prepared]) -> list[Any]:
        return [await statement.run() for statement in statements]


class _Binding:
    def __init__(self) -> None:
        self.constraints: list[str] = []

    def withSession(self, constraint: str) -> _Session:  # noqa: N802 - Workers API name
        self.constraints.append(constraint)
        return _Session()


def test_new_session_uses_explicit_consistency() -> None:
    async def scenario() -> None:
        binding = _Binding()

        database = D1Database(binding).new_session("first-unconstrained")
        rows = await database.fetch_all("SELECT id FROM products WHERE id = ?", ("one",))

        assert binding.constraints == ["first-primary", "first-unconstrained"]
        assert rows == [{"id": "one"}]

    asyncio.run(scenario())


def test_execute_and_batch_preserve_change_counts() -> None:
    async def scenario() -> None:
        database = D1Database(_Binding())

        assert await database.execute("UPDATE products SET status = ?", ("published",)) == 1
        assert await database.batch([("DELETE FROM products WHERE id = ?", ("one",))]) == [1]

    asyncio.run(scenario())

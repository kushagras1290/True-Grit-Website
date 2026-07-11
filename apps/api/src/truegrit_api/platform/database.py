"""Database access protocol and adapters.

Business code depends on the `Database` protocol only. On Cloudflare Workers the
D1 binding implements it (see `d1.py`); locally and in tests a SQLite adapter
built from the real migrations and seed provides identical SQL semantics, so
repository queries are exercised against the true schema.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Protocol


class Database(Protocol):
    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]: ...

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None: ...

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        """Run a write statement; returns the number of affected rows."""
        ...

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        """Run related writes atomically — all succeed or all roll back."""
        ...


class SQLiteDatabase:
    """Local/test implementation of the `Database` protocol on stdlib sqlite3."""

    def __init__(self, connection: sqlite3.Connection):
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON;")
        self._conn = connection
        self._lock = threading.Lock()

    @classmethod
    def from_migrations(cls, migrations_dir: Path, seed_file: Path | None = None) -> SQLiteDatabase:
        conn = sqlite3.connect(":memory:", check_same_thread=False)
        for migration in sorted(migrations_dir.glob("*.sql")):
            conn.executescript(migration.read_text(encoding="utf-8"))
        if seed_file is not None and seed_file.exists():
            conn.executescript(seed_file.read_text(encoding="utf-8"))
        conn.commit()
        return cls(conn)

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row is not None else None

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        with self._lock:
            cursor = self._conn.execute(sql, tuple(params))
            self._conn.commit()
            return cursor.rowcount

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> None:
        with self._lock:
            try:
                for sql, params in statements:
                    self._conn.execute(sql, tuple(params))
            except sqlite3.Error:
                self._conn.rollback()
                raise
            self._conn.commit()


def repo_root() -> Path:
    return Path(__file__).resolve().parents[5]


def build_local_database(seeded: bool = True) -> SQLiteDatabase:
    root = repo_root()
    return SQLiteDatabase.from_migrations(
        root / "database" / "migrations",
        root / "database" / "seeds" / "development.sql" if seeded else None,
    )

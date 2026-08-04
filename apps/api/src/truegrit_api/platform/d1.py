"""Cloudflare D1 adapter with request-scoped Sessions and query telemetry."""

from __future__ import annotations

import hashlib
import time
from collections.abc import Sequence
from typing import Any, Literal

from truegrit_api.logging import log_event

D1Consistency = Literal["first-primary", "first-unconstrained"]


def _to_py(value: Any) -> Any:
    """Return a native Python value from a D1 result element."""
    to_py = getattr(value, "to_py", None)
    return to_py() if callable(to_py) else value


def _query_identity(sql: str) -> tuple[str, str]:
    normalized = " ".join(sql.split())
    operation = normalized.partition(" ")[0].upper() if normalized else "UNKNOWN"
    fingerprint = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:12]
    return operation, fingerprint


def _meta_fields(meta_value: Any) -> dict[str, Any]:
    meta = _to_py(meta_value)
    if not isinstance(meta, dict):
        return {}
    return {
        key: meta[key]
        for key in (
            "changes",
            "duration",
            "rows_read",
            "rows_written",
            "served_by_primary",
            "served_by_region",
        )
        if key in meta
    }


class D1Database:
    """Wrap a D1 binding/session behind the portable ``Database`` protocol."""

    def __init__(
        self,
        binding: Any,
        *,
        consistency: D1Consistency = "first-primary",
        session: Any | None = None,
    ) -> None:
        self._binding = binding
        self._consistency = consistency
        self._db = session if session is not None else self._start_session(consistency)

    def _start_session(self, consistency: D1Consistency) -> Any:
        with_session = getattr(self._binding, "withSession", None)
        return with_session(consistency) if callable(with_session) else self._binding

    def new_session(self, consistency: D1Consistency) -> D1Database:
        """Create one sequentially-consistent D1 Session for a single request."""
        return D1Database(self._binding, consistency=consistency)

    def _log_query(
        self,
        sql: str,
        started_at: float,
        *,
        row_count: int | None = None,
        meta: Any = None,
    ) -> None:
        operation, fingerprint = _query_identity(sql)
        log_event(
            "info",
            "d1_query",
            operation=operation,
            query_fingerprint=fingerprint,
            consistency=self._consistency,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            row_count=row_count,
            **_meta_fields(meta),
        )

    def _log_error(self, sql: str, started_at: float, exc: Exception) -> None:
        operation, fingerprint = _query_identity(sql)
        message = str(exc).lower()
        log_event(
            "error",
            "d1_query_failed",
            operation=operation,
            query_fingerprint=fingerprint,
            consistency=self._consistency,
            duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
            overload="overload" in message or "too many requests" in message,
            error_type=type(exc).__name__,
        )

    async def fetch_all(self, sql: str, params: Sequence[Any] = ()) -> list[dict[str, Any]]:
        started_at = time.perf_counter()
        try:
            result = await self._db.prepare(sql).bind(*params).all()
            rows = _to_py(result.results)
            converted = [dict(_to_py(row)) for row in rows]
            self._log_query(sql, started_at, row_count=len(converted), meta=result.meta)
            return converted
        except Exception as exc:
            self._log_error(sql, started_at, exc)
            raise

    async def fetch_one(self, sql: str, params: Sequence[Any] = ()) -> dict[str, Any] | None:
        started_at = time.perf_counter()
        try:
            row = await self._db.prepare(sql).bind(*params).first()
            converted = None if row is None else dict(_to_py(row))
            self._log_query(sql, started_at, row_count=0 if converted is None else 1)
            return converted
        except Exception as exc:
            self._log_error(sql, started_at, exc)
            raise

    async def execute(self, sql: str, params: Sequence[Any] = ()) -> int:
        started_at = time.perf_counter()
        try:
            result = await self._db.prepare(sql).bind(*params).run()
            meta = _to_py(result.meta)
            changes = int(meta.get("changes", 0) or 0)
            self._log_query(sql, started_at, meta=meta)
            return changes
        except Exception as exc:
            self._log_error(sql, started_at, exc)
            raise

    async def batch(self, statements: Sequence[tuple[str, Sequence[Any]]]) -> list[int]:
        started_at = time.perf_counter()
        batch_identity = "\n".join(sql for sql, _ in statements)
        try:
            prepared = [self._db.prepare(sql).bind(*params) for sql, params in statements]
            results = _to_py(await self._db.batch(prepared))
            changes: list[int] = []
            rows_read = 0
            rows_written = 0
            for result in results:
                meta = _to_py(result.meta)
                changes.append(int(meta.get("changes", 0) or 0))
                rows_read += int(meta.get("rows_read", 0) or 0)
                rows_written += int(meta.get("rows_written", 0) or 0)
            operation, fingerprint = _query_identity(batch_identity)
            log_event(
                "info",
                "d1_batch",
                operation=operation,
                query_fingerprint=fingerprint,
                consistency=self._consistency,
                statement_count=len(statements),
                duration_ms=round((time.perf_counter() - started_at) * 1000, 3),
                rows_read=rows_read,
                rows_written=rows_written,
            )
            return changes
        except Exception as exc:
            self._log_error(batch_identity, started_at, exc)
            raise

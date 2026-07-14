"""Durable fixed-window rate limiting for authentication endpoints.

Brute-force and credential-stuffing protection must survive across Worker
isolates and deploys, so counters live in the database (D1/SQLite) rather than
in process memory. Each caller-derived key is one bucket; the window resets in
place via an atomic UPSERT. Callers pick the key (per-IP, per-email) and the
rule (attempts / window).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request

from truegrit_api.errors import RateLimitError
from truegrit_api.platform.database import Database

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class RateLimitRule:
    max_attempts: int
    window_seconds: int


def _iso(moment: datetime) -> str:
    return moment.strftime(_ISO_FORMAT)


def hash_identifier(value: str) -> str:
    """SHA-256 so rate-limit keys never store raw IPs or emails."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def client_ip(request: Request) -> str:
    """Best-effort client IP. Behind Cloudflare the trustworthy value is
    `CF-Connecting-IP`; fall back to the first `X-Forwarded-For` hop, then the
    socket peer. Never raises."""
    cf_ip = request.headers.get("cf-connecting-ip")
    if cf_ip and cf_ip.strip():
        return cf_ip.strip()
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        first_hop = forwarded.split(",")[0].strip()
        if first_hop:
            return first_hop
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


async def enforce_rate_limit(
    db: Database,
    *,
    key: str,
    rule: RateLimitRule,
    now: datetime | None = None,
) -> None:
    """Count one attempt against `key` and raise RateLimitError (HTTP 429) once
    it exceeds `rule.max_attempts` within `rule.window_seconds`. The attempt that
    trips the limit is itself counted and rejected."""
    if rule.max_attempts < 1:
        raise RateLimitError()
    moment = now or datetime.now(UTC)
    now_iso = _iso(moment)
    window_threshold_iso = _iso(moment - timedelta(seconds=rule.window_seconds))
    expires_iso = _iso(moment + timedelta(seconds=rule.window_seconds))
    # Fixed-window UPSERT: reset the bucket when its window has fully elapsed,
    # otherwise increment. Timestamps are fixed-width UTC, so `<=` on the text
    # column is a correct chronological comparison.
    await db.execute(
        """
        INSERT INTO auth_rate_limits (key, window_start, count, expires_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(key) DO UPDATE SET
          count = CASE
            WHEN auth_rate_limits.window_start <= ? THEN 1
            ELSE auth_rate_limits.count + 1
          END,
          window_start = CASE
            WHEN auth_rate_limits.window_start <= ? THEN excluded.window_start
            ELSE auth_rate_limits.window_start
          END,
          expires_at = excluded.expires_at
        """,
        (key, now_iso, expires_iso, window_threshold_iso, window_threshold_iso),
    )
    row = await db.fetch_one("SELECT count FROM auth_rate_limits WHERE key = ?", (key,))
    if row is not None and row["count"] > rule.max_attempts:
        raise RateLimitError()

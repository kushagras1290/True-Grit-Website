"""Durable fixed-window rate limiting for outbound email.

Same UPSERT algorithm as `auth/rate_limit.py`, against its own
`email_rate_limits` table rather than `auth_rate_limits`: email throttling and
login brute-force protection are different concerns that only happen to share
an algorithm, so mixing their counters would make either harder to reason
about or clean up independently.

Unlike the auth version, a throttled attempt must not look like a failure: a
disabled outbox category or a full window is a deliberate admin choice, not a
provider error, so this module never raises. Callers get a bool back and
decide what "not now" means for them (defer, skip, or refuse).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from truegrit_api.platform.database import Database

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


@dataclass(frozen=True)
class RateLimitRule:
    max_attempts: int
    window_seconds: int


def _iso(moment: datetime) -> str:
    return moment.strftime(_ISO_FORMAT)


async def check_and_count(
    db: Database, *, key: str, rule: RateLimitRule, now: datetime | None = None
) -> bool:
    """Count one attempt against `key`. Returns True and commits the count if
    it is still within `rule.max_attempts` for the current window; returns
    False -- without counting it again -- once the window is full.

    The row is written unconditionally on every call (an attempt that turns
    out to be over the limit still occupies its slot), matching the intuitive
    meaning of a rate limit: a rejected attempt was still an attempt.
    """
    if rule.max_attempts < 1:
        return False
    moment = now or datetime.now(UTC)
    now_iso = _iso(moment)
    window_threshold_iso = _iso(moment - timedelta(seconds=rule.window_seconds))
    expires_iso = _iso(moment + timedelta(seconds=rule.window_seconds))
    await db.execute(
        """
        INSERT INTO email_rate_limits (key, window_start, count, expires_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(key) DO UPDATE SET
          count = CASE
            WHEN email_rate_limits.window_start <= ? THEN 1
            ELSE email_rate_limits.count + 1
          END,
          window_start = CASE
            WHEN email_rate_limits.window_start <= ? THEN excluded.window_start
            ELSE email_rate_limits.window_start
          END,
          expires_at = excluded.expires_at
        """,
        (key, now_iso, expires_iso, window_threshold_iso, window_threshold_iso),
    )
    row = await db.fetch_one("SELECT count FROM email_rate_limits WHERE key = ?", (key,))
    return row is None or int(row["count"]) <= rule.max_attempts

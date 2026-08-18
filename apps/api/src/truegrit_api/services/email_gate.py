"""The single choke point every email send path checks before delivering.

Both the outbox dispatcher (`services/jobs.py`) and the three direct
staff-account send sites (`api/admin.py`) call `check_email_gate` before
sending anything, and `record_email_outcome` after -- one place decides
"is this category allowed and within its rate limit right now", and one
place writes what actually happened, so the admin activity log
(`email_send_log`) is complete regardless of which path a given email took.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from truegrit_api.config import Settings
from truegrit_api.platform.database import Database
from truegrit_api.services.email import send_email
from truegrit_api.services.email_rate_limit import RateLimitRule, check_and_count
from truegrit_api.services.email_settings import load_email_settings, preferred_provider
from truegrit_api.util.ids import new_id

_SECONDS_PER_HOUR = 3600
_SECONDS_PER_DAY = 86_400

_OUTCOME_BLOCKED_DISABLED = "blocked_disabled"
_OUTCOME_RATE_LIMITED = "rate_limited"
_OUTCOME_SENT = "sent"


@dataclass(frozen=True)
class EmailGateResult:
    allowed: bool
    outcome: str  # 'sent' (clear to proceed), 'blocked_disabled', or 'rate_limited'


async def check_email_gate(db: Database, category: str) -> EmailGateResult:
    """Decide whether an email in `category` may be sent right now.

    Checks are evaluated in order and stop at the first failure, so a
    rejected attempt does not also consume a slot in windows it never
    actually reached -- an attempt blocked by the global hourly cap must not
    also burn a count against the category's daily cap.
    """
    settings = await load_email_settings(db)
    if not settings.category_enabled.get(category, True):
        return EmailGateResult(allowed=False, outcome=_OUTCOME_BLOCKED_DISABLED)

    now = datetime.now(UTC)
    checks: list[tuple[str, RateLimitRule]] = [
        ("email:global:hourly", RateLimitRule(settings.global_hourly_limit, _SECONDS_PER_HOUR)),
        ("email:global:daily", RateLimitRule(settings.global_daily_limit, _SECONDS_PER_DAY)),
    ]
    category_limits = settings.category_limits.get(category)
    if category_limits is not None:
        if category_limits.hourly is not None:
            checks.append(
                (
                    f"email:category:{category}:hourly",
                    RateLimitRule(category_limits.hourly, _SECONDS_PER_HOUR),
                )
            )
        if category_limits.daily is not None:
            checks.append(
                (
                    f"email:category:{category}:daily",
                    RateLimitRule(category_limits.daily, _SECONDS_PER_DAY),
                )
            )

    for key, rule in checks:
        if not await check_and_count(db, key=key, rule=rule, now=now):
            return EmailGateResult(allowed=False, outcome=_OUTCOME_RATE_LIMITED)
    return EmailGateResult(allowed=True, outcome=_OUTCOME_SENT)


def _recipient_domain(recipient: str | None) -> str | None:
    if not recipient or "@" not in recipient:
        return None
    return recipient.rsplit("@", 1)[-1].strip().lower() or None


async def send_gated_email(
    db: Database,
    *,
    category: str,
    to: str,
    subject: str,
    body: str,
    settings: Settings,
    html_body: str | None = None,
) -> bool:
    """Gate-checked variant of `services.email.send_email` for the direct,
    non-outbox send sites (staff invite, staff password reset) -- checks
    `check_email_gate` first and always records the outcome, so those call
    sites don't each hand-roll the same gate/send/record sequence."""
    gate = await check_email_gate(db, category)
    if not gate.allowed:
        await record_email_outcome(
            db, category=category, provider="none", outcome=gate.outcome, recipient=to
        )
        return False
    provider = await preferred_provider(db)
    sent = send_email(to, subject, body, settings, html_body, preferred_provider=provider)
    await record_email_outcome(
        db,
        category=category,
        provider=provider or "auto",
        outcome=_OUTCOME_SENT if sent else "provider_error",
        recipient=to,
    )
    return sent


async def record_email_outcome(
    db: Database,
    *,
    category: str,
    provider: str,
    outcome: str,
    detail: str = "",
    recipient: str | None = None,
    outbox_event_id: str | None = None,
) -> None:
    """Append one row to the admin activity log. Never stores a raw recipient
    address -- domain only, the same privacy stance `hash_identifier` takes
    for rate-limit keys in `auth/rate_limit.py`."""
    await db.execute(
        """
        INSERT INTO email_send_log
          (id, category, provider, outcome, detail, recipient_domain, outbox_event_id, occurred_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            new_id("eml"),
            category,
            provider,
            outcome,
            detail[:500],
            _recipient_domain(recipient),
            outbox_event_id,
            datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        ),
    )

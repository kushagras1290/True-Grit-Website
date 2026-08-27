"""Notification helper for Workers AI daily free-neuron exhaustion."""

from __future__ import annotations

from datetime import UTC, datetime

from truegrit_api.config import Settings, get_settings
from truegrit_api.platform.database import Database
from truegrit_api.services.jobs import enqueue_email

_QUOTA_MARKERS = (
    "quota",
    "limit",
    "free neuron",
    "daily",
    "exceeded",
    "capacity",
    "too many requests",
    "429",
)


def looks_like_ai_quota_error(exc: BaseException) -> bool:
    message = str(exc).lower()
    return any(marker in message for marker in _QUOTA_MARKERS)


async def notify_ai_quota_exhausted(
    db: Database,
    exc: BaseException,
    *,
    settings: Settings | None = None,
) -> str | None:
    resolved = settings or get_settings()
    recipient = (resolved.contact_recipient_email or resolved.admin_login_email).strip()
    if not recipient or "@" not in recipient:
        return None
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    subject = "Cloudflare Workers AI free neurons exhausted"
    body = (
        "Cloudflare Workers AI appears to have exhausted its daily free-neuron allowance "
        f"for {today} UTC.\n\n"
        "Auto-translation jobs may fail until the quota resets or paid usage is enabled.\n\n"
        f"Provider error: {str(exc)[:500]}"
    )
    return await enqueue_email(
        db,
        dedupe_key=f"ai-quota:{today}",
        to=recipient,
        subject=subject,
        body=body,
        aggregate_type="app_setting",
        aggregate_id="ai.free_neuron",
        category="ai_quota",
    )

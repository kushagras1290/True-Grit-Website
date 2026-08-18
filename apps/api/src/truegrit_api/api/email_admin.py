"""Admin console for the email provider, category toggles, rate limits and
send activity -- the backend for the standalone `/email` admin page (kept
separate from Site Settings by design, mirroring how `farm_partnerships.py`
keeps its own concern out of the general-purpose `admin.py`)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, require_permission
from truegrit_api.auth.principal import Principal
from truegrit_api.config import get_settings
from truegrit_api.errors import ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.email import email_transport_name, send_email
from truegrit_api.services.email_gate import record_email_outcome
from truegrit_api.services.email_settings import (
    EMAIL_CATEGORIES,
    load_email_settings,
    preferred_provider,
    update_email_settings,
)

router = APIRouter(tags=["admin-email"])

_MAX_ACTIVITY_LIMIT = 200
_DEFAULT_ACTIVITY_LIMIT = 50
_ACTIVITY_OUTCOMES = ("sent", "blocked_disabled", "rate_limited", "provider_error")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class EmailCategoryUpdate(_CamelModel):
    enabled: bool | None = None
    hourly_limit: int | None = None
    daily_limit: int | None = None


class EmailSettingsUpdateRequest(_CamelModel):
    provider: str | None = None
    global_hourly_limit: int | None = None
    global_daily_limit: int | None = None
    categories: dict[str, EmailCategoryUpdate] | None = None


@router.get("/email/settings")
async def get_email_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    settings = get_settings()
    control = await load_email_settings(db)
    response = control.to_camel_dict()
    response["configuredProviders"] = {
        "resend": bool(settings.resend_api_key),
        "brevo": bool(settings.brevo_api_key),
        "smtp": bool(settings.smtp_host),
    }
    response["activeProvider"] = email_transport_name(settings, control.provider)
    return response


@router.put("/email/settings")
async def update_email_settings_endpoint(
    payload: EmailSettingsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    settings = get_settings()
    updates = payload.model_dump(exclude_unset=True)
    control = await update_email_settings(db, principal, _request_id(request), updates=updates)
    response = control.to_camel_dict()
    response["configuredProviders"] = {
        "resend": bool(settings.resend_api_key),
        "brevo": bool(settings.brevo_api_key),
        "smtp": bool(settings.smtp_host),
    }
    response["activeProvider"] = email_transport_name(settings, control.provider)
    return response


@router.get("/email/activity")
async def get_email_activity(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
    category: str | None = None,
    outcome: str | None = None,
    limit: int = _DEFAULT_ACTIVITY_LIMIT,
) -> Any:
    bounded_limit = max(1, min(limit, _MAX_ACTIVITY_LIMIT))
    conditions: list[str] = []
    params: list[Any] = []
    if category:
        if category not in EMAIL_CATEGORIES and category != "test":
            raise ValidationAppError("Unknown email category.")
        conditions.append("category = ?")
        params.append(category)
    if outcome:
        if outcome not in _ACTIVITY_OUTCOMES:
            raise ValidationAppError("Unknown outcome filter.")
        conditions.append("outcome = ?")
        params.append(outcome)
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    rows = await db.fetch_all(
        f"""
        SELECT id, category, provider, outcome, detail, recipient_domain, occurred_at
        FROM email_send_log
        {where_clause}
        ORDER BY occurred_at DESC
        LIMIT ?
        """,
        (*params, bounded_limit),
    )
    since = (datetime.now(UTC) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary_rows = await db.fetch_all(
        "SELECT outcome, COUNT(*) AS count FROM email_send_log"
        " WHERE occurred_at >= ? GROUP BY outcome",
        (since,),
    )
    summary = dict.fromkeys(_ACTIVITY_OUTCOMES, 0)
    for row in summary_rows:
        if row["outcome"] in summary:
            summary[row["outcome"]] = row["count"]
    return {
        "entries": [
            {
                "id": row["id"],
                "category": row["category"],
                "provider": row["provider"],
                "outcome": row["outcome"],
                "detail": row["detail"] or "",
                "recipientDomain": row["recipient_domain"],
                "occurredAt": row["occurred_at"],
            }
            for row in rows
        ],
        "summary24h": summary,
    }


@router.post("/email/test-send")
async def send_test_email(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    """Sends one real email to the requesting admin, bypassing the category
    toggle/rate limit gate -- an operator must be able to verify the active
    provider works even while testing with the relevant category switched
    off."""
    settings = get_settings()
    recipient = principal.contact_email
    if recipient is None:
        raise ValidationAppError("Your account has no email address to send a test to.")
    provider_preference = await preferred_provider(db)
    resolved_provider = email_transport_name(settings, provider_preference)
    sent = send_email(
        recipient,
        "True Grit email test",
        "This is a test email from the True Grit admin panel, sent via the"
        f" currently active provider ({resolved_provider}).",
        settings,
        preferred_provider=provider_preference,
    )
    await record_email_outcome(
        db,
        category="test",
        provider=resolved_provider,
        outcome="sent" if sent else "provider_error",
        recipient=recipient,
    )
    return {"sent": sent, "provider": resolved_provider, "to": recipient}

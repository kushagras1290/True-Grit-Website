"""Public farm partnership applications: growers apply to supply the market.

Unauthenticated by design -- a prospective supplier is not yet a customer, so a
sign-up wall here would filter out most of the people the form exists to reach
(see `services.farm_partnerships` for the full reasoning). Staff-side triage
lives in `api.admin`.

Openness is paid for with two layers of durable rate limiting rather than an
account:

* **Per IP**, the usual volumetric backstop.
* **Per contact**, counted from the applications table itself. IP-only limiting
  is close to useless for this audience: rural India is heavily NATed, so one
  co-operative's office and an entire village can share an address, and a limit
  loose enough not to punish them is loose enough to be worthless. Counting a
  grower's own email and phone catches the duplicate flood that actually
  happens -- someone submitting the same application five times because the
  first gave no visible response.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Final

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database, get_optional_customer
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.config import get_settings
from truegrit_api.domain.phone import normalize_phone
from truegrit_api.errors import RateLimitError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.partnerships import FarmPartnershipRequestRepository
from truegrit_api.services.email import send_email
from truegrit_api.services.email_templates import render_farm_partnership_received
from truegrit_api.services.farm_partnerships import create_request, is_enabled

router = APIRouter(tags=["storefront-farm-partnerships"])

# Ten applications an hour from one address. Generous enough that a shared
# office or a village hotspot is never the thing that blocks a real grower.
_IP_RULE: Final = RateLimitRule(max_attempts=10, window_seconds=3600)

# Three per grower per day, counted from the applications themselves. A fourth
# is not a partnership enquiry, it is a stuck submit button.
_PER_CONTACT_LIMIT: Final = 3
_PER_CONTACT_WINDOW_HOURS: Final = 24

_ISO_FORMAT: Final = "%Y-%m-%dT%H:%M:%SZ"


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class FarmPartnershipRequestPayload(_CamelModel):
    """Field bounds here are a cheap first gate; `services.farm_partnerships`
    re-validates every one of them with the message the applicant should see,
    because the service is also reachable from tests and future callers."""

    contact_name: str = Field(min_length=1, max_length=160)
    contact_email: str = Field(min_length=3, max_length=254)
    contact_phone: str = Field(min_length=1, max_length=24)
    farm_name: str = Field(min_length=1, max_length=200)
    region: str = Field(min_length=1, max_length=160)
    state: str | None = Field(default=None, max_length=120)
    city: str | None = Field(default=None, max_length=120)
    pincode: str | None = Field(default=None, max_length=16)
    established_year: int | None = Field(default=None, ge=1800, le=2200)
    land_area_acres: str | None = Field(default=None, max_length=120)
    certification: str | None = Field(default=None, max_length=400)
    primary_produce: str | None = Field(default=None, max_length=400)
    farming_practices: str | None = Field(default=None, max_length=4000)
    website_url: str | None = Field(default=None, max_length=500)
    message: str = Field(min_length=1, max_length=4000)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


async def _enforce_contact_quota(db: Database, *, email: str, phone: str) -> None:
    """Refuse a grower who has already filed `_PER_CONTACT_LIMIT` applications
    in the last day.

    Deliberately counted from `farm_partnership_requests` rather than from a
    rate-limit bucket: the bucket would also count attempts that failed
    validation, which would let a single mistyped phone number lock someone out
    of applying at all.
    """
    since = datetime.now(UTC) - timedelta(hours=_PER_CONTACT_WINDOW_HOURS)
    recent = await FarmPartnershipRequestRepository(db).count_recent_from_contact(
        email=email, phone=phone, since_iso=since.strftime(_ISO_FORMAT)
    )
    if recent >= _PER_CONTACT_LIMIT:
        raise RateLimitError(
            "We already have a recent application from you. We will be in touch —"
            " please give us a day before sending another.",
            {"retryAfterSeconds": _PER_CONTACT_WINDOW_HOURS * 3600},
        )


@router.get("/farm-partnerships/settings")
async def farm_partnership_settings(db: Annotated[Database, Depends(get_database)]) -> Any:
    """Lets the storefront render the form only when applications are open,
    instead of showing a form the API would refuse."""
    return {"enabled": await is_enabled(db)}


@router.post("/farm-partnerships")
async def submit_farm_partnership_request(
    payload: FarmPartnershipRequestPayload,
    request: Request,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_database)],
    customer: Annotated[Principal | None, Depends(get_optional_customer)],
) -> Any:
    settings = get_settings()
    if settings.rate_limit_enabled:
        await enforce_rate_limit(
            db,
            key=f"farm-partnership:ip:{hash_identifier(client_ip(request))}",
            rule=_IP_RULE,
        )
        # Normalised before counting so "+91 98765 43210" and "9876543210"
        # land in the same bucket — otherwise the quota is trivially evaded by
        # retyping the number differently.
        await _enforce_contact_quota(
            db,
            email=payload.contact_email.strip().lower(),
            phone=normalize_phone(payload.contact_phone),
        )

    result = await create_request(
        db,
        _request_id(request),
        submitter_user_id=customer.user_id if customer is not None else None,
        contact_name=payload.contact_name,
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        farm_name=payload.farm_name,
        region=payload.region,
        state=payload.state,
        city=payload.city,
        pincode=payload.pincode,
        established_year=payload.established_year,
        land_area_acres=payload.land_area_acres,
        certification=payload.certification,
        primary_produce=payload.primary_produce,
        farming_practices=payload.farming_practices,
        website_url=payload.website_url,
        message=payload.message,
    )

    # Both mails are backgrounded: an application must be recorded whether or
    # not mail is configured, and the applicant should not wait on SMTP to see
    # the confirmation screen.
    applicant_email = payload.contact_email.strip().lower()
    applicant_phone = normalize_phone(payload.contact_phone)

    to = settings.contact_recipient_email or settings.admin_login_email
    background.add_task(
        send_email,
        to,
        f"Farm application: {result['farmName']}",
        (
            f"{result['contactName']} has applied to supply True Grit.\n\n"
            f"Farm: {result['farmName']}\n"
            f"Region: {payload.region.strip()}\n"
            f"Email: {applicant_email}\n"
            f"Phone: {applicant_phone}\n\n"
            f"{payload.message.strip()}\n\n"
            f"Review it in the admin console under Farm requests."
        ),
        settings,
    )
    background.add_task(
        send_email,
        applicant_email,
        "We have your farm application",
        (
            f"Hi {result['contactName']},\n\n"
            f"Thank you for telling us about {result['farmName']}. Your application to"
            " supply True Grit has reached our sourcing team, and someone will call you"
            " on the number you gave us.\n\n"
            "The True Grit Team"
        ),
        settings,
        render_farm_partnership_received(result["contactName"], result["farmName"]),
    )
    return {"id": result["id"], "status": result["status"]}

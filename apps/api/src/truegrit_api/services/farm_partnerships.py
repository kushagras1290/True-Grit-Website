"""Farm partnership applications: growers apply, staff triage.

A grower fills in the storefront form at `/farms/partner`; staff with
`farm_requests.review` walk the application through the pipeline in the admin
console. See migration 0044 for the schema and for why this is not modelled on
`content_submissions`.

Three decisions shape this module:

* **No account is required.** A prospective supplier is not yet a customer, so
  demanding a sign-up would filter out most of the people the form exists to
  reach. `submitter_user_id` is therefore optional and set only when a
  signed-in visitor happens to apply. The route pays for that openness with
  durable per-IP and per-contact rate limiting (`auth.rate_limit`), which is
  where abuse belongs -- not behind a sign-up wall.

* **Approval decides, it does not onboard.** Unlike a blog submission, which
  approval promotes straight into `articles`, approving an application here
  writes a status and sends an email. Creating the `farms` row is a separate,
  deliberate act after contracts and certification, and `attach_farm` records
  the link once it exists.

* **The phone number is mandatory and normalised.** Follow-up is a call, so an
  application nobody can ring is worthless. `normalize_phone` runs before the
  value is stored, so the column is comparable with `users.phone_e164`.
"""

from __future__ import annotations

from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.domain.phone import normalize_phone
from truegrit_api.errors import (
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.contact import contactable_email
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

ENABLED_SETTING_KEY: Final = "farm_partnerships.enabled"

# Matches migration 0044. A missing or unparseable row resolves to the
# permissive value, so a corrupted settings table degrades to "the product as
# shipped" rather than silently closing applications.
_ENABLED_DEFAULT: Final = True
_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})

# An open application is one a decision can still be made on. 'approved' and
# 'rejected' are terminal: re-deciding one would rewrite a record the applicant
# has already been emailed about.
_OPEN_STATUSES: Final = frozenset({"submitted", "under_review", "contacted"})
_DECISIONS: Final = frozenset({"under_review", "contacted", "approved", "rejected"})

_MIN_NAME: Final = 2
_MAX_NAME: Final = 160
_MAX_EMAIL: Final = 254
_MIN_FARM_NAME: Final = 2
_MAX_FARM_NAME: Final = 200
_MIN_REGION: Final = 2
_MAX_REGION: Final = 160
_MAX_SHORT_TEXT: Final = 120
_MAX_MEDIUM_TEXT: Final = 400
_MIN_MESSAGE: Final = 20
_MAX_MESSAGE: Final = 4000
_MAX_URL: Final = 500
_MAX_NOTE: Final = 2000

# Wide bounds on purpose: a co-operative founded generations ago is a normal
# answer here, and the column CHECK in 0044 uses the same range.
_MIN_ESTABLISHED_YEAR: Final = 1800
_MAX_ESTABLISHED_YEAR: Final = 2200


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


async def is_enabled(db: Database) -> bool:
    """Whether the storefront is currently accepting applications."""
    row = await db.fetch_one("SELECT value FROM app_settings WHERE key = ?", (ENABLED_SETTING_KEY,))
    return _parse_bool(row["value"] if row else None, default=_ENABLED_DEFAULT)


async def assert_enabled(db: Database) -> None:
    """Enforced on the route, not only by hiding the storefront form: hiding a
    form stops the honest visitor, not a replayed POST."""
    if not await is_enabled(db):
        raise PermissionDeniedError("We are not accepting farm applications at the moment.")


async def set_enabled(
    db: Database, actor: Principal, request_id: str, *, enabled: bool
) -> dict[str, Any]:
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                "  updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (ENABLED_SETTING_KEY, "1" if enabled else "0", now, actor.user_id),
            ),
            audit_statement(
                action="settings.farm_partnerships_updated",
                entity_type="app_setting",
                entity_id=ENABLED_SETTING_KEY,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"enabled": enabled},
            ),
        ]
    )
    return {"enabled": enabled}


def _required_text(value: str | None, field: str, minimum: int, maximum: int) -> str:
    text = (value or "").strip()
    if len(text) < minimum or len(text) > maximum:
        raise ValidationAppError(f"{field} must be between {minimum} and {maximum} characters.")
    return text


def _optional_text(value: str | None, field: str, maximum: int) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > maximum:
        raise ValidationAppError(f"{field} must be {maximum} characters or fewer.")
    return text


def _validate_email(value: str) -> str:
    """Structural check only -- deliverability is proven by mail arriving, not
    by a regex. Kept deliberately loose so a valid but unusual address is not
    rejected at the door; the strict check lives on the account routes where a
    typo costs a customer their sign-in."""
    email = (value or "").strip().lower()
    if len(email) > _MAX_EMAIL:
        raise ValidationAppError("Enter a valid email address.")
    local, separator, domain = email.partition("@")
    if not separator or not local or "." not in domain or domain.startswith("."):
        raise ValidationAppError("Enter a valid email address.")
    if any(character.isspace() for character in email):
        raise ValidationAppError("Enter a valid email address.")
    return email


def _validate_website(value: str | None) -> str | None:
    """Accept only absolute http(s) URLs. A bare `javascript:` or `data:` value
    would be rendered as a link in the admin console, so the scheme allowlist is
    the whole point of this function."""
    url = (value or "").strip()
    if not url:
        return None
    if len(url) > _MAX_URL:
        raise ValidationAppError("Website address is too long.")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValidationAppError("Website must start with http:// or https://")
    return url


def _validate_established_year(value: int | None) -> int | None:
    if value is None:
        return None
    if value < _MIN_ESTABLISHED_YEAR or value > _MAX_ESTABLISHED_YEAR:
        raise ValidationAppError(
            f"Year established must be between {_MIN_ESTABLISHED_YEAR} and {_MAX_ESTABLISHED_YEAR}."
        )
    return value


async def create_request(
    db: Database,
    request_id: str,
    *,
    submitter_user_id: str | None,
    contact_name: str,
    contact_email: str,
    contact_phone: str,
    farm_name: str,
    region: str,
    state: str | None,
    city: str | None,
    pincode: str | None,
    established_year: int | None,
    land_area_acres: str | None,
    certification: str | None,
    primary_produce: str | None,
    farming_practices: str | None,
    website_url: str | None,
    message: str,
) -> dict[str, Any]:
    """Validate and record one application. Returns the new id and status.

    Raises `ValidationAppError` on any bad field and `PermissionDeniedError`
    when applications are switched off. Rate limiting happens on the route,
    before this is called.
    """
    await assert_enabled(db)

    name = _required_text(contact_name, "Your name", _MIN_NAME, _MAX_NAME)
    email = _validate_email(contact_email)
    # Raises ValidationAppError itself, with a message that tells the applicant
    # exactly which format is expected.
    phone = normalize_phone(contact_phone)
    farm = _required_text(farm_name, "Farm name", _MIN_FARM_NAME, _MAX_FARM_NAME)
    where = _required_text(region, "Region or district", _MIN_REGION, _MAX_REGION)
    story = _required_text(message, "Tell us about your farm", _MIN_MESSAGE, _MAX_MESSAGE)

    now = utc_now_iso()
    entry_id = new_id("fpr")
    await db.batch(
        [
            (
                "INSERT INTO farm_partnership_requests"
                " (id, status, contact_name, contact_email, contact_phone, farm_name, region,"
                "  state, city, pincode, established_year, land_area_acres, certification,"
                "  primary_produce, farming_practices, website_url, message, submitter_user_id,"
                "  created_at, updated_at)"
                " VALUES (?, 'submitted', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry_id,
                    name,
                    email,
                    phone,
                    farm,
                    where,
                    _optional_text(state, "State", _MAX_SHORT_TEXT),
                    _optional_text(city, "City or town", _MAX_SHORT_TEXT),
                    _optional_text(pincode, "PIN code", 16),
                    _validate_established_year(established_year),
                    _optional_text(land_area_acres, "Land area", _MAX_SHORT_TEXT),
                    _optional_text(certification, "Certification", _MAX_MEDIUM_TEXT),
                    _optional_text(primary_produce, "What you grow", _MAX_MEDIUM_TEXT),
                    _optional_text(farming_practices, "Farming practices", _MAX_MESSAGE),
                    _validate_website(website_url),
                    story,
                    submitter_user_id,
                    now,
                    now,
                ),
            ),
            audit_statement(
                action="farm_partnership_request.created",
                entity_type="farm_partnership_request",
                entity_id=entry_id,
                actor_id=submitter_user_id,
                request_id=request_id,
                created_at=now,
                source="api",
                after={"farmName": farm, "region": where},
            ),
        ]
    )
    return {"id": entry_id, "status": "submitted", "farmName": farm, "contactName": name}


async def decide_request(
    db: Database,
    actor: Principal,
    request_id: str,
    entry_id: str,
    *,
    decision: str,
    note: str | None = None,
) -> dict[str, Any]:
    """Move an open application to `decision`.

    'rejected' requires a note, because the applicant is emailed it and "no"
    with no reason is the one outcome that generates a second application.
    Terminal states cannot be re-decided.
    """
    if decision not in _DECISIONS:
        raise ValidationAppError("Unsupported decision.")
    current = await db.fetch_one(
        "SELECT * FROM farm_partnership_requests WHERE id = ?", (entry_id,)
    )
    if current is None:
        raise NotFoundError("Farm application not found.")
    if current["status"] not in _OPEN_STATUSES:
        raise ConflictError(
            f"This application is already {current['status']} and cannot be changed."
        )
    note = (note or "").strip()[:_MAX_NOTE] or None
    if decision == "rejected" and not note:
        raise ValidationAppError("A note is required when declining an application.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE farm_partnership_requests SET status = ?, reviewer_notes = ?,"
                " reviewed_by = ?, reviewed_at = ?, updated_at = ? WHERE id = ?",
                (decision, note, actor.user_id, now, now, entry_id),
            ),
            audit_statement(
                action=f"farm_partnership_request.{decision}",
                entity_type="farm_partnership_request",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": decision, "note": note},
            ),
        ]
    )
    return {
        "id": entry_id,
        "status": decision,
        "note": note,
        "contactName": current["contact_name"],
        "contactEmail": contactable_email(current["contact_email"]),
        "farmName": current["farm_name"],
    }


async def attach_farm(
    db: Database, actor: Principal, request_id: str, entry_id: str, farm_id: str
) -> dict[str, Any]:
    """Record which `farms` row an approved application became.

    Only approved applications can be linked: attaching a farm to a rejected or
    still-open application would assert an onboarding that did not happen.
    """
    current = await db.fetch_one(
        "SELECT id, status, linked_farm_id FROM farm_partnership_requests WHERE id = ?",
        (entry_id,),
    )
    if current is None:
        raise NotFoundError("Farm application not found.")
    if current["status"] != "approved":
        raise ConflictError("Only an approved application can be linked to a farm.")
    farm = await db.fetch_one("SELECT id FROM farms WHERE id = ?", (farm_id,))
    if farm is None:
        raise NotFoundError("Farm not found.")

    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE farm_partnership_requests SET linked_farm_id = ?, updated_at = ?"
                " WHERE id = ?",
                (farm_id, now, entry_id),
            ),
            audit_statement(
                action="farm_partnership_request.linked",
                entity_type="farm_partnership_request",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                before={"linkedFarmId": current["linked_farm_id"]},
                after={"linkedFarmId": farm_id},
            ),
        ]
    )
    return {"id": entry_id, "linkedFarmId": farm_id}


async def delete_request(
    db: Database, actor: Principal, request_id: str, entry_id: str
) -> dict[str, Any]:
    """Permanent removal, for spam. Distinct from rejection, which keeps the
    record and tells the applicant."""
    current = await db.fetch_one(
        "SELECT id FROM farm_partnership_requests WHERE id = ?", (entry_id,)
    )
    if current is None:
        raise NotFoundError("Farm application not found.")
    now = utc_now_iso()
    await db.batch(
        [
            ("DELETE FROM farm_partnership_requests WHERE id = ?", (entry_id,)),
            audit_statement(
                action="farm_partnership_request.deleted",
                entity_type="farm_partnership_request",
                entity_id=entry_id,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
            ),
        ]
    )
    return {"id": entry_id, "deleted": True}

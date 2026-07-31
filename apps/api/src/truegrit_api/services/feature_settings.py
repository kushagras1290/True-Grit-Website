"""Runtime switches for sign-in methods, taking payments, and the blog banner.

Every switch lives in ``app_settings`` (migration 0040) so an operator can flip
it from the admin console — no redeploy, no env-var edit, no code change.

Two rules keep the switches honest:

* **A switch can only take something away.** Availability is always
  ``switch AND server-is-configured``: ``auth.google.enabled`` cannot conjure a
  Google button without ``GOOGLE_CLIENT_ID``, and ``commerce.payments.enabled``
  cannot invent a gateway. Same reasoning as ``Settings.enabled_payment_methods``
  — configure first, reveal deliberately.
* **A broken row can never brick sign-in.** Values are text; anything that does
  not parse falls back to the default in ``_BOOLEAN_DEFAULTS``, so a hand-edited
  or truncated row degrades to the shipped behaviour rather than an exception on
  the login path.

Read through :func:`load_storefront_settings` (raw switches, for the admin
console) or :func:`resolve_public_settings` (switches ANDed with configuration,
for the storefront and for enforcement).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Final

from truegrit_api.auth.principal import Principal
from truegrit_api.config import Settings
from truegrit_api.errors import PermissionDeniedError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services.audit import audit_statement
from truegrit_api.util.timeutil import utc_now_iso

KEY_GOOGLE: Final = "auth.google.enabled"
KEY_FACEBOOK: Final = "auth.facebook.enabled"
KEY_PHONE_OTP: Final = "auth.phone_otp.enabled"
KEY_PASSWORD: Final = "auth.password.enabled"
KEY_REGISTRATION: Final = "auth.registration.enabled"
KEY_PAYMENTS: Final = "commerce.payments.enabled"
KEY_PAYMENTS_NOTICE: Final = "commerce.payments_disabled_notice"
KEY_BLOG_BANNER_URL: Final = "banner.blog.image_url"
KEY_BLOG_BANNER_ALT: Final = "banner.blog.image_alt"

# Defaults must match migration 0040. They are what a missing or unparseable row
# resolves to, which is why every one of them is the permissive value: a
# corrupted settings table degrades to "the product as shipped", never to a
# storefront nobody can sign in to.
_BOOLEAN_DEFAULTS: Final[dict[str, bool]] = {
    KEY_GOOGLE: True,
    KEY_FACEBOOK: True,
    KEY_PHONE_OTP: True,
    KEY_PASSWORD: True,
    KEY_REGISTRATION: True,
    KEY_PAYMENTS: True,
}

_DEFAULT_PAYMENTS_NOTICE: Final = (
    "We are not taking orders at the moment. Leave your details and we will get"
    " in touch as soon as ordering reopens."
)

_MAX_NOTICE_LENGTH: Final = 600
_MAX_IMAGE_URL_LENGTH: Final = 1000
_MAX_IMAGE_ALT_LENGTH: Final = 200

_TRUE_VALUES: Final = frozenset({"1", "true", "yes", "on"})
_FALSE_VALUES: Final = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True)
class StorefrontSettings:
    """The stored switches, exactly as an operator set them.

    Deliberately *not* combined with server configuration: the admin console has
    to show the operator what they chose, not what the environment happens to
    allow. Use :func:`resolve_public_settings` for the effective state.
    """

    google_sign_in: bool
    facebook_sign_in: bool
    phone_otp_sign_in: bool
    password_sign_in: bool
    registration: bool
    payments: bool
    payments_disabled_notice: str
    blog_banner_image_url: str
    blog_banner_image_alt: str

    def to_camel_dict(self) -> dict[str, Any]:
        return {
            "googleSignIn": self.google_sign_in,
            "facebookSignIn": self.facebook_sign_in,
            "phoneOtpSignIn": self.phone_otp_sign_in,
            "passwordSignIn": self.password_sign_in,
            "registration": self.registration,
            "payments": self.payments,
            "paymentsDisabledNotice": self.payments_disabled_notice,
            "blogBannerImageUrl": self.blog_banner_image_url,
            "blogBannerImageAlt": self.blog_banner_image_alt,
        }


def _parse_bool(raw: str | None, *, default: bool) -> bool:
    if raw is None:
        return default
    value = raw.strip().lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False
    return default


def _validate_image_url(value: str, field: str) -> str:
    """Accept a site-relative path or an absolute http(s) URL, nothing else.

    Mirrors the admin's own image-URL rule (`imageUrlSchema` in site-control):
    a protocol-relative `//host` would let a banner be swapped by whoever
    controls that host, and a `javascript:` URL has no business in an <img>.
    """
    trimmed = value.strip()
    if not trimmed:
        return ""
    if len(trimmed) > _MAX_IMAGE_URL_LENGTH:
        raise ValidationAppError(f"{field} is too long.")
    if trimmed.startswith("//"):
        raise ValidationAppError(f"{field} must be a site path or an http(s) URL.")
    if trimmed.startswith("/") or trimmed.startswith("https://") or trimmed.startswith("http://"):
        return trimmed
    raise ValidationAppError(f"{field} must be a site path or an http(s) URL.")


async def _read_values(db: Database) -> dict[str, str]:
    rows = await db.fetch_all("SELECT key, value FROM app_settings")
    return {row["key"]: row["value"] for row in rows}


async def load_storefront_settings(db: Database) -> StorefrontSettings:
    """The stored switches. One query — these are read on hot paths."""
    values = await _read_values(db)
    notice = (values.get(KEY_PAYMENTS_NOTICE) or "").strip() or _DEFAULT_PAYMENTS_NOTICE
    return StorefrontSettings(
        google_sign_in=_parse_bool(values.get(KEY_GOOGLE), default=_BOOLEAN_DEFAULTS[KEY_GOOGLE]),
        facebook_sign_in=_parse_bool(
            values.get(KEY_FACEBOOK), default=_BOOLEAN_DEFAULTS[KEY_FACEBOOK]
        ),
        phone_otp_sign_in=_parse_bool(
            values.get(KEY_PHONE_OTP), default=_BOOLEAN_DEFAULTS[KEY_PHONE_OTP]
        ),
        password_sign_in=_parse_bool(
            values.get(KEY_PASSWORD), default=_BOOLEAN_DEFAULTS[KEY_PASSWORD]
        ),
        registration=_parse_bool(
            values.get(KEY_REGISTRATION), default=_BOOLEAN_DEFAULTS[KEY_REGISTRATION]
        ),
        payments=_parse_bool(values.get(KEY_PAYMENTS), default=_BOOLEAN_DEFAULTS[KEY_PAYMENTS]),
        payments_disabled_notice=notice[:_MAX_NOTICE_LENGTH],
        blog_banner_image_url=(values.get(KEY_BLOG_BANNER_URL) or "").strip(),
        blog_banner_image_alt=(values.get(KEY_BLOG_BANNER_ALT) or "").strip(),
    )


@dataclass(frozen=True)
class PublicStorefrontSettings:
    """What the storefront is told: switches ANDed with server configuration.

    ``google_sign_in`` false here means "do not render the button", whether that
    is because the owner turned it off or because no client id is configured —
    the browser does not need to tell those apart, and neither does enforcement.
    """

    google_sign_in: bool
    facebook_sign_in: bool
    phone_otp_sign_in: bool
    password_sign_in: bool
    registration: bool
    payments: bool
    payments_disabled_notice: str
    blog_banner_image_url: str
    blog_banner_image_alt: str

    @property
    def any_sign_in_available(self) -> bool:
        return (
            self.google_sign_in
            or self.facebook_sign_in
            or self.phone_otp_sign_in
            or self.password_sign_in
        )

    def to_camel_dict(self) -> dict[str, Any]:
        return {
            "auth": {
                "google": self.google_sign_in,
                "facebook": self.facebook_sign_in,
                "phoneOtp": self.phone_otp_sign_in,
                "password": self.password_sign_in,
                "registration": self.registration,
            },
            "payments": {
                "enabled": self.payments,
                "disabledNotice": self.payments_disabled_notice,
            },
            "banners": {
                "blogImageUrl": self.blog_banner_image_url,
                "blogImageAlt": self.blog_banner_image_alt,
            },
        }


def resolve_public_settings(
    stored: StorefrontSettings, settings: Settings
) -> PublicStorefrontSettings:
    """Combine operator intent with what this deployment can actually do.

    Registration additionally requires *some* credential the browser can create
    an account with: with both password sign-in and phone passcodes off there is
    no registration flow left to offer, so the flag is forced false rather than
    advertising a form that cannot be submitted.
    """
    password_sign_in = stored.password_sign_in
    phone_otp = stored.phone_otp_sign_in and settings.sms_enabled
    registration = stored.registration and (password_sign_in or phone_otp)
    return PublicStorefrontSettings(
        google_sign_in=stored.google_sign_in and settings.google_sign_in_enabled,
        facebook_sign_in=stored.facebook_sign_in and settings.facebook_sign_in_enabled,
        phone_otp_sign_in=phone_otp,
        password_sign_in=password_sign_in,
        registration=registration,
        payments=stored.payments and bool(settings.enabled_payment_methods),
        payments_disabled_notice=stored.payments_disabled_notice,
        blog_banner_image_url=stored.blog_banner_image_url,
        blog_banner_image_alt=stored.blog_banner_image_alt,
    )


async def load_public_settings(db: Database, settings: Settings) -> PublicStorefrontSettings:
    return resolve_public_settings(await load_storefront_settings(db), settings)


async def assert_sign_in_method_enabled(db: Database, method: str) -> None:
    """Refuse a sign-in route the owner has switched off.

    Deliberately checks the *stored* switch only, never the ANDed value: "the
    owner disallowed this" and "this deployment is not configured for it" are
    different failures with different fixes, and each provider's own verifier
    already reports the second one. Folding them together here would turn a
    misconfigured Google client id into a misleading "unavailable".

    Enforced on the API, not only in the storefront UI: hiding a button stops
    the honest customer, not the one replaying a captured request.
    """
    stored = await load_storefront_settings(db)
    allowed = {
        "google": stored.google_sign_in,
        "facebook": stored.facebook_sign_in,
        "phone": stored.phone_otp_sign_in,
        "password": stored.password_sign_in,
    }
    if not allowed.get(method, False):
        raise PermissionDeniedError("This sign-in method is currently unavailable.")


async def assert_payments_enabled(db: Database) -> None:
    if not (await load_storefront_settings(db)).payments:
        raise PermissionDeniedError("We are not taking orders at the moment.")


async def update_storefront_settings(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    updates: dict[str, Any],
) -> StorefrontSettings:
    """Persist the changed switches and record one audit entry for the change.

    Only keys present in ``updates`` are written, so a PATCH that toggles
    payments cannot silently reset the sign-in switches to whatever the client
    last happened to render.
    """
    field_to_key: dict[str, str] = {
        "google_sign_in": KEY_GOOGLE,
        "facebook_sign_in": KEY_FACEBOOK,
        "phone_otp_sign_in": KEY_PHONE_OTP,
        "password_sign_in": KEY_PASSWORD,
        "registration": KEY_REGISTRATION,
        "payments": KEY_PAYMENTS,
    }

    now = utc_now_iso()
    pending: list[tuple[str, str]] = []
    changed: dict[str, Any] = {}

    for field, key in field_to_key.items():
        if field not in updates:
            continue
        value = bool(updates[field])
        pending.append((key, "1" if value else "0"))
        changed[field] = value

    if "payments_disabled_notice" in updates:
        notice = str(updates["payments_disabled_notice"]).strip()
        if len(notice) > _MAX_NOTICE_LENGTH:
            raise ValidationAppError(
                f"The message shown when payments are off must be"
                f" {_MAX_NOTICE_LENGTH} characters or fewer."
            )
        resolved = notice or _DEFAULT_PAYMENTS_NOTICE
        pending.append((KEY_PAYMENTS_NOTICE, resolved))
        changed["payments_disabled_notice"] = resolved

    if "blog_banner_image_url" in updates:
        url = _validate_image_url(str(updates["blog_banner_image_url"]), "Blog banner image")
        pending.append((KEY_BLOG_BANNER_URL, url))
        changed["blog_banner_image_url"] = url

    if "blog_banner_image_alt" in updates:
        alt = str(updates["blog_banner_image_alt"]).strip()[:_MAX_IMAGE_ALT_LENGTH]
        pending.append((KEY_BLOG_BANNER_ALT, alt))
        changed["blog_banner_image_alt"] = alt

    if not pending:
        return await load_storefront_settings(db)

    statements: list[tuple[str, Sequence[Any]]] = [
        (
            "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
            " ON CONFLICT(key) DO UPDATE SET"
            "  value = excluded.value, updated_at = excluded.updated_at,"
            "  updated_by = excluded.updated_by",
            (key, value, now, actor.user_id),
        )
        for key, value in pending
    ]
    statements.append(
        audit_statement(
            action="settings.storefront_updated",
            entity_type="app_setting",
            entity_id="storefront",
            actor_id=actor.user_id,
            request_id=request_id,
            created_at=now,
            after=changed,
        )
    )
    await db.batch(statements)
    return await load_storefront_settings(db)

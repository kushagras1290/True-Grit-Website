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
from truegrit_api.domain.blocks import DEFAULT_MAX_HERO_SLIDES, HERO_SLIDES_HARD_LIMIT
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
KEY_PROMOTIONS: Final = "commerce.promotions.enabled"
KEY_RECOMMENDATIONS: Final = "commerce.recommendations.enabled"
KEY_SUBSCRIPTIONS: Final = "commerce.subscriptions.enabled"
KEY_SUBSCRIPTION_DISCOUNT_PERCENT: Final = "commerce.subscriptions.discount_percent"
KEY_DIET_CERT_FILTERS: Final = "commerce.diet_cert_filters.enabled"
KEY_GIFT_CARDS: Final = "commerce.gift_cards.enabled"
KEY_LOYALTY: Final = "commerce.loyalty.enabled"
KEY_LOYALTY_POINTS_PER_100: Final = "commerce.loyalty.points_per_100"
KEY_LOYALTY_REFERRAL_REWARD: Final = "commerce.loyalty.referral_reward_points"
KEY_LOYALTY_POINT_VALUE_MINOR: Final = "commerce.loyalty.points_value_minor"
KEY_PICKUP: Final = "commerce.pickup.enabled"
KEY_PREORDERS: Final = "commerce.preorders.enabled"
KEY_DELIVERY_ZONES: Final = "commerce.delivery_zones.enabled"
KEY_B2B: Final = "commerce.b2b.enabled"
KEY_REFUND_ORCHESTRATOR: Final = "commerce.refund_orchestrator.enabled"
KEY_DELIVERY_FEE_MINOR: Final = "commerce.delivery_fee_minor"
KEY_FREE_DELIVERY_THRESHOLD_MINOR: Final = "commerce.free_delivery_threshold_minor"
KEY_BLOG_BANNER_URL: Final = "banner.blog.image_url"
KEY_BLOG_BANNER_ALT: Final = "banner.blog.image_alt"
KEY_FARMS_BANNER_URL: Final = "banner.farms.image_url"
KEY_FARMS_BANNER_ALT: Final = "banner.farms.image_alt"
KEY_HERO_MAX_SLIDES: Final = "homepage.hero.max_slides"
KEY_CURATED_MAX_ITEMS: Final = "homepage.curated.max_items"

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
    # Off by default (migration 0060) -- unlike the switches above, this one
    # does not gate core functionality nobody could use without it. It is a
    # marketing feature an operator turns on deliberately once a promotion is
    # actually configured, not a permissive fallback for a corrupted row.
    KEY_PROMOTIONS: False,
    # On by default, unlike promotions -- recommendations need no setup (they
    # are computed live from real order data, never a list an operator must
    # first stock), so shipping them on is what "looks like the site is
    # promoting its products" out of the box, not a feature waiting to be
    # switched on.
    KEY_RECOMMENDATIONS: True,
    # Off by default, same reasoning as KEY_PROMOTIONS -- not needed at
    # launch (user's explicit call), but built for real and switchable the
    # moment it is wanted, rather than a stub.
    KEY_SUBSCRIPTIONS: False,
    # On by default, same reasoning as KEY_RECOMMENDATIONS -- the filters
    # read real product data (tags/certifications an admin already assigned),
    # need no separate setup, and are pure narrowing of what is already
    # public, so there is no reason to ship them off.
    KEY_DIET_CERT_FILTERS: True,
    # Off by default, same reasoning as KEY_PROMOTIONS -- real stored value
    # an owner issues deliberately once they want to offer it, not a
    # permissive fallback for a corrupted row (migration 0082).
    KEY_GIFT_CARDS: False,
    KEY_LOYALTY: False,
    KEY_PICKUP: False,
    KEY_PREORDERS: False,
    KEY_DELIVERY_ZONES: False,
    KEY_B2B: False,
    # Off by default, same reasoning as KEY_PROMOTIONS -- an automated
    # pipeline that can move real refund money and email customers
    # unattended is a deliberate business decision an operator switches on,
    # never a permissive fallback for a corrupted row (migration 0113).
    KEY_REFUND_ORCHESTRATOR: False,
}

DEFAULT_SUBSCRIPTION_DISCOUNT_PERCENT: Final = 5
# A sanity ceiling, the same role CURATED_MAX_ITEMS_HARD_LIMIT plays for
# curated rows -- guards against a fat-fingered entry turning the incentive
# into a giveaway.
SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT: Final = 50

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
    promotions: bool
    recommendations: bool
    subscriptions: bool
    diet_cert_filters: bool
    gift_cards: bool
    loyalty: bool
    pickup: bool
    preorders: bool
    delivery_zones: bool
    b2b: bool
    refund_orchestrator: bool
    blog_banner_image_url: str
    blog_banner_image_alt: str
    farms_banner_image_url: str
    farms_banner_image_alt: str

    def to_camel_dict(self) -> dict[str, Any]:
        return {
            "googleSignIn": self.google_sign_in,
            "facebookSignIn": self.facebook_sign_in,
            "phoneOtpSignIn": self.phone_otp_sign_in,
            "passwordSignIn": self.password_sign_in,
            "registration": self.registration,
            "payments": self.payments,
            "paymentsDisabledNotice": self.payments_disabled_notice,
            "promotions": self.promotions,
            "recommendations": self.recommendations,
            "subscriptions": self.subscriptions,
            "dietCertFilters": self.diet_cert_filters,
            "giftCards": self.gift_cards,
            "loyalty": self.loyalty,
            "pickup": self.pickup,
            "preorders": self.preorders,
            "deliveryZones": self.delivery_zones,
            "b2b": self.b2b,
            "refundOrchestrator": self.refund_orchestrator,
            "blogBannerImageUrl": self.blog_banner_image_url,
            "blogBannerImageAlt": self.blog_banner_image_alt,
            "farmsBannerImageUrl": self.farms_banner_image_url,
            "farmsBannerImageAlt": self.farms_banner_image_alt,
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


async def _write_setting(
    db: Database,
    actor: Principal,
    request_id: str,
    *,
    key: str,
    value: str,
    action: str,
    changed: dict[str, Any],
) -> None:
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET"
                "  value = excluded.value, updated_at = excluded.updated_at,"
                "  updated_by = excluded.updated_by",
                (key, value, now, actor.user_id),
            ),
            audit_statement(
                action=action,
                entity_type="app_setting",
                entity_id=key,
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after=changed,
            ),
        ]
    )


async def load_hero_max_slides(db: Database) -> int:
    """How many banner slides Homepage Settings will let an owner curate.

    Stored rather than hardcoded so growing the carousel past the shipped
    twelve is an admin change, not a deploy. Read defensively: a missing,
    non-numeric or out-of-range row resolves to the shipped default instead of
    raising, because the value is read on the page that would otherwise be the
    only place to fix it.
    """
    values = await _read_values(db)
    return clamp_hero_max_slides(values.get(KEY_HERO_MAX_SLIDES))


def clamp_hero_max_slides(raw: str | int | None) -> int:
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_MAX_HERO_SLIDES
    if parsed < 1:
        return 1
    return min(parsed, HERO_SLIDES_HARD_LIMIT)


async def set_hero_max_slides(
    db: Database, actor: Principal, request_id: str, *, value: int
) -> int:
    """Persist the carousel cap, refusing anything the block model could not store."""
    if value < 1 or value > HERO_SLIDES_HARD_LIMIT:
        raise ValidationAppError(
            f"The banner carousel limit must be between 1 and {HERO_SLIDES_HARD_LIMIT} slides."
        )
    await _write_setting(
        db,
        actor,
        request_id,
        key=KEY_HERO_MAX_SLIDES,
        value=str(value),
        action="settings.homepage_updated",
        changed={"hero_max_slides": value},
    )
    return value


DEFAULT_CURATED_MAX_ITEMS: Final = 12
# A sanity ceiling, not a realistic value -- the same role HERO_SLIDES_HARD_LIMIT
# plays for the carousel, guarding against a fat-fingered entry turning a
# curated row into an unmanageable wall of products.
CURATED_MAX_ITEMS_HARD_LIMIT: Final = 50


async def load_curated_max_items(db: Database) -> int:
    """How many products an owner may curate into a fixed-pick homepage row
    (Fresh Favourites, Featured Categories) or the search-page Highlights box.

    One shared cap for all three: they are the same shape of feature (pick up
    to N items, in order), so a single adjustable ceiling is a smaller admin
    surface than three near-identical settings. Stored rather than hardcoded,
    the same reasoning as `load_hero_max_slides` -- growing past the shipped
    twelve is an admin change, not a deploy. Read defensively: a missing,
    non-numeric or out-of-range row resolves to the shipped default.
    """
    values = await _read_values(db)
    return clamp_curated_max_items(values.get(KEY_CURATED_MAX_ITEMS))


def clamp_curated_max_items(raw: str | int | None) -> int:
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_CURATED_MAX_ITEMS
    if parsed < 1:
        return 1
    return min(parsed, CURATED_MAX_ITEMS_HARD_LIMIT)


async def set_curated_max_items(
    db: Database, actor: Principal, request_id: str, *, value: int
) -> int:
    if value < 1 or value > CURATED_MAX_ITEMS_HARD_LIMIT:
        raise ValidationAppError(
            f"The curated list limit must be between 1 and {CURATED_MAX_ITEMS_HARD_LIMIT} items."
        )
    await _write_setting(
        db,
        actor,
        request_id,
        key=KEY_CURATED_MAX_ITEMS,
        value=str(value),
        action="settings.homepage_updated",
        changed={"curated_max_items": value},
    )
    return value


DEFAULT_DELIVERY_FEE_MINOR: Final = 4_900  # ₹49
DEFAULT_FREE_DELIVERY_THRESHOLD_MINOR: Final = 150_000  # ₹1,500
# A sanity ceiling, not a realistic value -- guards against a fat-fingered
# entry (an extra zero) turning every checkout into a four- or five-figure
# delivery charge, the same role `HERO_SLIDES_HARD_LIMIT` plays for the
# carousel.
_MAX_DELIVERY_CHARGE_MINOR: Final = 100_000_00  # ₹1,00,000


@dataclass(frozen=True)
class DeliverySettings:
    fee_minor: int
    free_threshold_minor: int


@dataclass(frozen=True)
class LoyaltySettings:
    points_per_100: int
    referral_reward_points: int
    point_value_minor: int


def _parse_non_negative_int(raw: str | None, *, default: int, maximum: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if 0 <= value <= maximum else default


async def load_loyalty_settings(db: Database) -> LoyaltySettings:
    values = await _read_values(db)
    return LoyaltySettings(
        points_per_100=_parse_non_negative_int(
            values.get(KEY_LOYALTY_POINTS_PER_100), default=10, maximum=10_000
        ),
        referral_reward_points=_parse_non_negative_int(
            values.get(KEY_LOYALTY_REFERRAL_REWARD), default=100, maximum=1_000_000
        ),
        point_value_minor=max(
            1,
            _parse_non_negative_int(
                values.get(KEY_LOYALTY_POINT_VALUE_MINOR), default=100, maximum=1_000_000
            ),
        ),
    )


def _parse_delivery_amount(raw: str | None, *, default: int) -> int:
    try:
        value = int(str(raw).strip())
    except (TypeError, ValueError):
        return default
    return value if 0 <= value <= _MAX_DELIVERY_CHARGE_MINOR else default


async def load_delivery_settings(db: Database) -> DeliverySettings:
    """The delivery fee and the free-delivery subtotal threshold checkout
    charges against. Stored rather than hardcoded, the same reasoning as
    `load_hero_max_slides`: a seasonal delivery-fee change or a raised
    free-delivery bar becomes an admin edit, not a deploy. Read defensively --
    a missing, non-numeric or out-of-range row resolves to the shipped
    default, the same degrade-safe behaviour every setting here has.
    """
    values = await _read_values(db)
    return DeliverySettings(
        fee_minor=_parse_delivery_amount(
            values.get(KEY_DELIVERY_FEE_MINOR), default=DEFAULT_DELIVERY_FEE_MINOR
        ),
        free_threshold_minor=_parse_delivery_amount(
            values.get(KEY_FREE_DELIVERY_THRESHOLD_MINOR),
            default=DEFAULT_FREE_DELIVERY_THRESHOLD_MINOR,
        ),
    )


async def set_delivery_settings(
    db: Database, actor: Principal, request_id: str, *, fee_minor: int, free_threshold_minor: int
) -> DeliverySettings:
    if not 0 <= fee_minor <= _MAX_DELIVERY_CHARGE_MINOR:
        raise ValidationAppError("Delivery fee must be a realistic non-negative amount.")
    if not 0 <= free_threshold_minor <= _MAX_DELIVERY_CHARGE_MINOR:
        raise ValidationAppError(
            "The free-delivery threshold must be a realistic non-negative amount."
        )
    now = utc_now_iso()
    await db.batch(
        [
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                "  updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (KEY_DELIVERY_FEE_MINOR, str(fee_minor), now, actor.user_id),
            ),
            (
                "INSERT INTO app_settings (key, value, updated_at, updated_by) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(key) DO UPDATE SET value = excluded.value,"
                "  updated_at = excluded.updated_at, updated_by = excluded.updated_by",
                (KEY_FREE_DELIVERY_THRESHOLD_MINOR, str(free_threshold_minor), now, actor.user_id),
            ),
            audit_statement(
                action="settings.delivery_updated",
                entity_type="app_setting",
                entity_id="delivery",
                actor_id=actor.user_id,
                request_id=request_id,
                created_at=now,
                after={"feeMinor": fee_minor, "freeThresholdMinor": free_threshold_minor},
            ),
        ]
    )
    return DeliverySettings(fee_minor=fee_minor, free_threshold_minor=free_threshold_minor)


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
        promotions=_parse_bool(
            values.get(KEY_PROMOTIONS), default=_BOOLEAN_DEFAULTS[KEY_PROMOTIONS]
        ),
        recommendations=_parse_bool(
            values.get(KEY_RECOMMENDATIONS), default=_BOOLEAN_DEFAULTS[KEY_RECOMMENDATIONS]
        ),
        subscriptions=_parse_bool(
            values.get(KEY_SUBSCRIPTIONS), default=_BOOLEAN_DEFAULTS[KEY_SUBSCRIPTIONS]
        ),
        diet_cert_filters=_parse_bool(
            values.get(KEY_DIET_CERT_FILTERS), default=_BOOLEAN_DEFAULTS[KEY_DIET_CERT_FILTERS]
        ),
        gift_cards=_parse_bool(
            values.get(KEY_GIFT_CARDS), default=_BOOLEAN_DEFAULTS[KEY_GIFT_CARDS]
        ),
        loyalty=_parse_bool(values.get(KEY_LOYALTY), default=_BOOLEAN_DEFAULTS[KEY_LOYALTY]),
        pickup=_parse_bool(values.get(KEY_PICKUP), default=_BOOLEAN_DEFAULTS[KEY_PICKUP]),
        preorders=_parse_bool(values.get(KEY_PREORDERS), default=_BOOLEAN_DEFAULTS[KEY_PREORDERS]),
        delivery_zones=_parse_bool(
            values.get(KEY_DELIVERY_ZONES), default=_BOOLEAN_DEFAULTS[KEY_DELIVERY_ZONES]
        ),
        b2b=_parse_bool(values.get(KEY_B2B), default=_BOOLEAN_DEFAULTS[KEY_B2B]),
        refund_orchestrator=_parse_bool(
            values.get(KEY_REFUND_ORCHESTRATOR), default=_BOOLEAN_DEFAULTS[KEY_REFUND_ORCHESTRATOR]
        ),
        blog_banner_image_url=(values.get(KEY_BLOG_BANNER_URL) or "").strip(),
        blog_banner_image_alt=(values.get(KEY_BLOG_BANNER_ALT) or "").strip(),
        farms_banner_image_url=(values.get(KEY_FARMS_BANNER_URL) or "").strip(),
        farms_banner_image_alt=(values.get(KEY_FARMS_BANNER_ALT) or "").strip(),
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
    promotions: bool
    recommendations: bool
    subscriptions: bool
    diet_cert_filters: bool
    gift_cards: bool
    loyalty: bool
    pickup: bool
    preorders: bool
    delivery_zones: bool
    b2b: bool
    refund_orchestrator: bool
    blog_banner_image_url: str
    blog_banner_image_alt: str
    farms_banner_image_url: str
    farms_banner_image_alt: str

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
            "promotions": {
                "enabled": self.promotions,
            },
            "recommendations": {
                "enabled": self.recommendations,
            },
            "subscriptions": {
                "enabled": self.subscriptions,
            },
            "dietCertFilters": {
                "enabled": self.diet_cert_filters,
            },
            "giftCards": {
                "enabled": self.gift_cards,
            },
            "loyalty": {"enabled": self.loyalty},
            "pickup": {"enabled": self.pickup},
            "preorders": {"enabled": self.preorders},
            "deliveryZones": {"enabled": self.delivery_zones},
            "b2b": {"enabled": self.b2b},
            "refundOrchestrator": {"enabled": self.refund_orchestrator},
            "banners": {
                "blogImageUrl": self.blog_banner_image_url,
                "blogImageAlt": self.blog_banner_image_alt,
                "farmsImageUrl": self.farms_banner_image_url,
                "farmsImageAlt": self.farms_banner_image_alt,
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
        # No server configuration gates this the way a payment gateway key
        # does -- the stored switch is the whole answer.
        promotions=stored.promotions,
        # Also just the stored switch, same reasoning as promotions -- nothing
        # here depends on server configuration either.
        recommendations=stored.recommendations,
        # Same reasoning again: no server configuration gates COD (it is
        # always available), so the stored switch is the whole answer.
        subscriptions=stored.subscriptions,
        # No server configuration gates this either -- it reads tags/
        # certifications an admin already assigned through the ordinary
        # product editor.
        diet_cert_filters=stored.diet_cert_filters,
        # No server configuration gates this either -- unlike a payment
        # gateway, issuing/redeeming a gift card needs no external API key.
        gift_cards=stored.gift_cards,
        loyalty=stored.loyalty,
        pickup=stored.pickup,
        preorders=stored.preorders,
        delivery_zones=stored.delivery_zones,
        b2b=stored.b2b,
        # No server configuration gates this either -- unlike a payment
        # gateway, deciding and refunding through Razorpay needs no separate
        # external key beyond what checkout already requires.
        refund_orchestrator=stored.refund_orchestrator,
        blog_banner_image_url=stored.blog_banner_image_url,
        blog_banner_image_alt=stored.blog_banner_image_alt,
        farms_banner_image_url=stored.farms_banner_image_url,
        farms_banner_image_alt=stored.farms_banner_image_alt,
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


async def promotions_enabled(db: Database) -> bool:
    """Whether the sitewide coupons/promotions feature is switched on --
    checked before honouring a coupon code at checkout and before the public
    featured-promotion endpoint (homepage banner, checkout box) returns
    anything. Unlike the payments switch (`services.checkout._resolve_line`),
    absence is not fatal: a disabled feature simply has nothing to show, it
    does not block checkout."""
    return (await load_storefront_settings(db)).promotions


async def recommendations_enabled(db: Database) -> bool:
    """Whether the sitewide product-recommendations feature is switched on --
    checked before the bestsellers/also-bought public endpoints return
    anything, and before the storefront renders any of the strips woven into
    the homepage, product, cart, category, search and shop pages. Absence is
    not fatal, the same reasoning as `promotions_enabled`: a disabled feature
    just has nothing to show."""
    return (await load_storefront_settings(db)).recommendations


async def subscriptions_enabled(db: Database) -> bool:
    """Whether the sitewide "Subscribe & Save" feature is switched on --
    checked before a customer can create a subscription and before the
    renewal job (services/subscriptions.py `run_due_renewals`) processes
    anything. Off by default (launch decision, not a technical limit): a
    disabled feature simply lets no one subscribe and renews nothing, it
    never blocks ordinary checkout."""
    return (await load_storefront_settings(db)).subscriptions


async def gift_cards_enabled(db: Database) -> bool:
    """Whether the sitewide gift-cards feature is switched on -- checked
    before honouring a gift card code at checkout, the same gate
    `promotions_enabled` is for coupons. Off by default: a disabled feature
    simply refuses a gift card code (a customer trying one gets a clear
    "not available" error, the same as a coupon code while promotions are
    off), it never blocks ordinary checkout."""
    return (await load_storefront_settings(db)).gift_cards


async def loyalty_enabled(db: Database) -> bool:
    return (await load_storefront_settings(db)).loyalty


async def pickup_enabled(db: Database) -> bool:
    return (await load_storefront_settings(db)).pickup


async def preorders_enabled(db: Database) -> bool:
    return (await load_storefront_settings(db)).preorders


async def delivery_zones_enabled(db: Database) -> bool:
    return (await load_storefront_settings(db)).delivery_zones


async def b2b_enabled(db: Database) -> bool:
    return (await load_storefront_settings(db)).b2b


async def refund_orchestrator_enabled(db: Database) -> bool:
    """Whether the automated refund-orchestrator pipeline is switched on --
    checked before `services.returns.create_return_request` enqueues an
    evaluation job. Off by default: a disabled switch simply leaves every
    return request exactly as it works today, triaged and resolved by hand
    -- it never blocks the ordinary return-request flow."""
    return (await load_storefront_settings(db)).refund_orchestrator


async def load_subscription_discount_percent(db: Database) -> int:
    """The percent-off applied to every subscription renewal order -- the
    incentive that makes "Subscribe & Save" a saving, not just a schedule.
    Stored rather than hardcoded, the same reasoning `load_hero_max_slides`
    documents. Read defensively: a missing, non-numeric or out-of-range row
    resolves to the shipped default."""
    values = await _read_values(db)
    return clamp_subscription_discount_percent(values.get(KEY_SUBSCRIPTION_DISCOUNT_PERCENT))


def clamp_subscription_discount_percent(raw: str | int | None) -> int:
    try:
        parsed = int(str(raw).strip())
    except (TypeError, ValueError):
        return DEFAULT_SUBSCRIPTION_DISCOUNT_PERCENT
    if parsed < 0:
        return 0
    return min(parsed, SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT)


async def set_subscription_discount_percent(
    db: Database, actor: Principal, request_id: str, *, value: int
) -> int:
    if value < 0 or value > SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT:
        raise ValidationAppError(
            f"The subscription discount must be between 0 and"
            f" {SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT} percent."
        )
    await _write_setting(
        db,
        actor,
        request_id,
        key=KEY_SUBSCRIPTION_DISCOUNT_PERCENT,
        value=str(value),
        action="settings.storefront_updated",
        changed={"subscription_discount_percent": value},
    )
    return value


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
        "promotions": KEY_PROMOTIONS,
        "recommendations": KEY_RECOMMENDATIONS,
        "subscriptions": KEY_SUBSCRIPTIONS,
        "diet_cert_filters": KEY_DIET_CERT_FILTERS,
        "gift_cards": KEY_GIFT_CARDS,
        "loyalty": KEY_LOYALTY,
        "pickup": KEY_PICKUP,
        "preorders": KEY_PREORDERS,
        "delivery_zones": KEY_DELIVERY_ZONES,
        "b2b": KEY_B2B,
        "refund_orchestrator": KEY_REFUND_ORCHESTRATOR,
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

    if "farms_banner_image_url" in updates:
        url = _validate_image_url(str(updates["farms_banner_image_url"]), "Farms banner image")
        pending.append((KEY_FARMS_BANNER_URL, url))
        changed["farms_banner_image_url"] = url

    if "farms_banner_image_alt" in updates:
        alt = str(updates["farms_banner_image_alt"]).strip()[:_MAX_IMAGE_ALT_LENGTH]
        pending.append((KEY_FARMS_BANNER_ALT, alt))
        changed["farms_banner_image_alt"] = alt

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

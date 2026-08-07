"""Admin endpoints. Every route enforces a permission — UI hiding is not authorization."""

from __future__ import annotations

import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import (
    get_current_staff,
    get_database,
    get_translator,
    require_permission,
)
from truegrit_api.auth.dependencies import (
    require_owner as _require_owner,
)
from truegrit_api.auth.passwords import (
    hash_password,
    password_hash_iterations,
    verify_password_async,
)
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.auth.sessions import end_session, hash_token, start_session
from truegrit_api.config import Settings, get_settings
from truegrit_api.domain.blocks import (
    HERO_SLIDES_HARD_LIMIT,
    MAX_BLOCKS,
    validate_blocks,
    validate_href,
)
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import (
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.platform.translation import Translator
from truegrit_api.repositories.admin import AdminRepository
from truegrit_api.repositories.bundles import BundleRepository
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    ArticleRepository,
    AuditRepository,
    CategoryRepository,
    ContentCommentRepository,
    ContentSubmissionRepository,
    DiscussionRepository,
    RecipeRepository,
    ReturnRequestRepository,
    ReviewRepository,
    RouteSeoRepository,
    SiteDocumentRepository,
)
from truegrit_api.repositories.partnerships import FarmPartnershipRequestRepository
from truegrit_api.repositories.promotions import PromotionRepository
from truegrit_api.repositories.subscriptions import SubscriptionRepository
from truegrit_api.services import analytics as analytics_service
from truegrit_api.services import articles as article_service
from truegrit_api.services import bundles as bundle_service
from truegrit_api.services import content_comments as content_comment_service
from truegrit_api.services import discussions as discussion_service
from truegrit_api.services import entity_translation as entity_translation_service
from truegrit_api.services import farm_partnerships as farm_partnership_service
from truegrit_api.services import gift_cards as gift_card_service
from truegrit_api.services import promotions as promotion_service
from truegrit_api.services import recipes as recipe_service
from truegrit_api.services import reviews as review_service
from truegrit_api.services import submissions as submission_service
from truegrit_api.services import subscriptions as subscription_service
from truegrit_api.services import translation as translation_service
from truegrit_api.services.access import (
    adopt_bootstrap_owner,
    change_own_password,
    create_farm_owner,
    create_role,
    create_user,
    delete_role,
    delete_users,
    invite_user,
    reset_farm_owner_password,
    set_role_permissions,
    set_user_roles,
    set_user_status,
    update_role,
)
from truegrit_api.services.announcements import (
    delete_country_announcement,
    list_announcements,
    save_announcement,
)
from truegrit_api.services.appearance import (
    AMBIENT_EFFECT_KEYS,
    CURSOR_TRAIL_KEYS,
    GLOBAL_SCOPE,
    THEME_TOKEN_KEYS,
    clear_country_effects,
    delete_theme_scope,
    is_country_scope,
    list_theme_scopes,
    load_appearance,
    save_effects,
    save_theme_scope,
)
from truegrit_api.services.appearance import validate_tokens as validate_theme_tokens
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.catalogue import (
    archive_category,
    archive_product,
    create_category,
    create_product,
    replace_product_images,
    set_category_release,
    set_highlighted_products,
    set_product_links,
    set_product_release,
    update_category,
    update_product,
)
from truegrit_api.services.contact import contactable_email, display_contact
from truegrit_api.services.email import email_transport_name, send_email
from truegrit_api.services.email_templates import (
    render_farm_partnership_approved,
    render_farm_partnership_rejected,
    render_submission_approved,
    render_submission_changes_requested,
    render_submission_rejected,
)
from truegrit_api.services.feature_settings import (
    CURATED_MAX_ITEMS_HARD_LIMIT,
    SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT,
    load_curated_max_items,
    load_delivery_settings,
    load_hero_max_slides,
    load_public_settings,
    load_storefront_settings,
    load_subscription_discount_percent,
    set_curated_max_items,
    set_delivery_settings,
    set_hero_max_slides,
    set_subscription_discount_percent,
    update_storefront_settings,
)
from truegrit_api.services.homepage_geo import (
    list_country_overrides as list_homepage_country_overrides,
)
from truegrit_api.services.homepage_geo import (
    set_country_override as set_homepage_country_override,
)
from truegrit_api.services.homepage_geo import validate_country as validate_homepage_country
from truegrit_api.services.inventory import adjust_inventory, clear_inventory_levels
from truegrit_api.services.jobs import enqueue_email
from truegrit_api.services.media import (
    delete_media,
    list_media,
    save_image_bytes,
    save_image_upload,
    update_media,
)
from truegrit_api.services.orders import issue_refund, update_order_status
from truegrit_api.services.password_reset import (
    confirm_password_reset,
    request_password_reset,
    request_staff_invitation_email,
    request_staff_password_reset_for_user,
)
from truegrit_api.services.price_adjustments import MAX_PERCENT as PRICE_ADJUSTMENT_MAX_PERCENT
from truegrit_api.services.price_adjustments import MIN_PERCENT as PRICE_ADJUSTMENT_MIN_PERCENT
from truegrit_api.services.price_adjustments import (
    delete_rule as delete_price_adjustment,
)
from truegrit_api.services.price_adjustments import (
    list_rules as list_price_adjustments,
)
from truegrit_api.services.price_adjustments import (
    save_rule as save_price_adjustment,
)
from truegrit_api.services.publishing import (
    publish_article,
    publish_category,
    publish_product,
    publish_recipe,
)
from truegrit_api.services.reports import list_reports, run_report
from truegrit_api.services.returns import decide_return_request, resolve_return_request
from truegrit_api.services.revenue import (
    farm_revenue_detail,
    farm_revenue_summary,
    issue_farm_payout,
    list_payouts,
    set_default_commission,
    set_farm_commission,
)
from truegrit_api.services.site_documents import SITE_DOCUMENT_TYPES, default_site_documents
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


class _CamelModel(BaseModel):
    """Request bodies use camelCase JSON but snake_case Python fields."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


async def _assert_product_scope(db: Database, product_id: str, principal: Principal) -> None:
    """A farm-owner sub-admin may only touch products of their own farm. Missing
    or foreign products raise NotFound so ownership is never leaked."""
    if principal.farm_id is None:
        return
    row = await db.fetch_one("SELECT farm_id FROM products WHERE id = ?", (product_id,))
    if row is None or row["farm_id"] != principal.farm_id:
        raise NotFoundError("Product not found.")


async def _assert_variant_scope(db: Database, variant_id: str, principal: Principal) -> None:
    if principal.farm_id is None:
        return
    row = await db.fetch_one(
        "SELECT p.farm_id FROM product_variants v JOIN products p ON p.id = v.product_id"
        " WHERE v.id = ?",
        (variant_id,),
    )
    if row is None or row["farm_id"] != principal.farm_id:
        raise NotFoundError("Variant not found.")


router = APIRouter(tags=["admin"])


class LoginRequest(BaseModel):
    email: str
    password: str


class PasswordChangeRequest(_CamelModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


# The account the `.env` bootstrap credential adopts when no staff row carries
# ADMIN_LOGIN_EMAIL yet — the founding owner, by creation order.
_FIRST_SUPER_ADMIN_SQL = """
    SELECT u.id, u.display_name, u.email
    FROM users u
    JOIN user_roles ur ON ur.user_id = u.id
    JOIN roles r ON r.id = ur.role_id
    WHERE u.user_type = 'staff'
      AND u.status = 'active'
      AND r.key = 'super_admin'
    ORDER BY u.created_at ASC
    LIMIT 1
"""


def _env_credential_matches(settings: Settings, email: str, password: str) -> bool:
    """Constant-time check of the `.env` bootstrap owner credential.

    The shipped default is refused in production: an unedited `.env` must never
    be a working owner login on a live store.
    """
    if settings.app_env == "production" and settings.admin_login_password == "admin123":
        return False
    return hmac.compare_digest(
        email, settings.admin_login_email.strip().lower()
    ) and hmac.compare_digest(password, settings.admin_login_password)


def _hash_exceeds_budget(encoded: str | None, settings: Settings) -> bool:
    iterations = password_hash_iterations(encoded)
    return iterations is not None and iterations > settings.pbkdf2_verify_max_iterations


async def _stored_password_hash(db: Database, user_id: str) -> str | None:
    row = await db.fetch_one(
        "SELECT password_hash FROM user_credentials WHERE user_id = ?", (user_id,)
    )
    return row["password_hash"] if row is not None else None


# Mirrors the identical dummy-hash pattern in `api/customer_auth.py`: an
# unknown email must still pay for a `verify_password_async` call, not return
# on an early `if user is None`, or response latency alone tells an attacker
# which staff emails exist.
_dummy_staff_hash: str | None = None


def _dummy_password_hash() -> str:
    global _dummy_staff_hash
    if _dummy_staff_hash is None:
        _dummy_staff_hash = hash_password(new_id("nope"), iterations=1)
    return _dummy_staff_hash


@router.post("/auth/login")
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    if settings.rate_limit_enabled:
        window = settings.rate_limit_window_seconds
        await enforce_rate_limit(
            db,
            key=f"admin-login:ip:{hash_identifier(client_ip(request))}",
            rule=RateLimitRule(settings.rate_limit_login_per_ip, window),
        )
        await enforce_rate_limit(
            db,
            key=f"admin-login:acct:{hash_identifier(payload.email.strip().lower())}",
            rule=RateLimitRule(settings.rate_limit_login_per_account, window),
        )
    email = payload.email.strip().lower()
    user = await db.fetch_one(
        """
        SELECT id, display_name, email
        FROM users
        WHERE email = ?
          AND user_type = 'staff'
          AND status = 'active'
        """,
        (email,),
    )

    # The account's own stored password is the only thing that authenticates.
    # This is how every staff user signs in, farm-owner sub-admins included.
    # An unknown email still runs a real `verify_password_async` against a
    # dummy hash rather than short-circuiting here — the two paths take
    # comparable time, so response latency cannot be used to enumerate which
    # staff emails exist (mirrors `api/customer_auth.py`'s login route).
    stored_hash = (
        await _stored_password_hash(db, user["id"]) if user is not None else None
    ) or _dummy_password_hash()
    credential_ok = (
        await verify_password_async(
            payload.password, stored_hash, max_iterations=settings.pbkdf2_verify_max_iterations
        )
        and user is not None
    )

    # The `.env` credential is a bootstrap, not a permanent key: it opens the
    # owner account only while that account has no password of its own. The first
    # sign-in adopts it — ADMIN_LOGIN_EMAIL becomes the account's address and
    # ADMIN_LOGIN_PASSWORD becomes its stored hash — and from then on editing
    # `.env` changes nothing, because a password the console can rotate has to be
    # the only one that works. To hand the account back to `.env`, delete its row
    # from user_credentials.
    if not credential_ok and _env_credential_matches(settings, email, payload.password):
        owner = user if user is not None else await db.fetch_one(_FIRST_SUPER_ADMIN_SQL)
        owner_hash = await _stored_password_hash(db, owner["id"]) if owner is not None else None
        if owner is not None and (owner_hash is None or _hash_exceeds_budget(owner_hash, settings)):
            await adopt_bootstrap_owner(
                db,
                _request_id(request),
                user_id=owner["id"],
                email=email,
                password=payload.password,
            )
            user = owner
            credential_ok = True

    if user is None or not credential_ok:
        raise AuthenticationError("Invalid admin email or password.")

    await start_session(
        db, response, user_id=user["id"], settings=settings, user_agent_summary="admin-login"
    )
    return {"ok": True}


@router.post("/auth/logout")
async def logout(
    request: Request,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    await end_session(db, request, response, settings=get_settings())
    return {"ok": True}


@router.post("/auth/change-password")
async def change_password_endpoint(
    payload: PasswordChangeRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    """Rotate your own password. Any staff user, no permission needed — an
    account's own credential is not something an admin should have to delegate."""
    settings = get_settings()
    if settings.rate_limit_enabled:
        # Rate limited despite being authenticated: it verifies a password, so a
        # stolen session must not become an offline-speed guessing oracle.
        await enforce_rate_limit(
            db,
            key=f"admin-password-change:{hash_identifier(principal.user_id)}",
            rule=RateLimitRule(
                settings.rate_limit_login_per_account, settings.rate_limit_window_seconds
            ),
        )
    session_token = request.cookies.get(settings.session_cookie_name)
    return await change_own_password(
        db,
        principal,
        _request_id(request),
        current_password=payload.current_password,
        new_password=payload.new_password,
        keep_session_token_hash=hash_token(session_token) if session_token else None,
    )


@router.get("/me")
async def me(
    principal: Annotated[Principal, Depends(get_current_staff)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    farm_name = None
    if principal.farm_id is not None:
        farm = await db.fetch_one("SELECT name FROM farms WHERE id = ?", (principal.farm_id,))
        farm_name = farm["name"] if farm else None
    super_admin = await db.fetch_one(
        """
        SELECT 1
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = ? AND r.key = 'super_admin'
        LIMIT 1
        """,
        (principal.user_id,),
    )
    return {
        "id": principal.user_id,
        "displayName": principal.display_name,
        "email": principal.email,
        "permissions": sorted(principal.permissions),
        "farmId": principal.farm_id,
        "farmName": farm_name,
        "isSuperAdmin": super_admin is not None,
    }


@router.get("/notifications")
async def admin_notifications(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    """Live, role-aware work queue for the admin header.

    Notifications are derived from current state, so resolving the underlying
    order/return/submission immediately removes the item without maintaining a
    second read/unread ledger that can become stale.
    """
    owner = await db.fetch_one(
        "SELECT 1 FROM user_roles ur JOIN roles r ON r.id = ur.role_id"
        " WHERE ur.user_id = ? AND r.key = 'super_admin' LIMIT 1",
        (principal.user_id,),
    )
    see_all = owner is not None
    items: list[dict[str, Any]] = []

    async def add(
        *,
        permission: str,
        key: str,
        title: str,
        message: str,
        href: str,
        sql: str,
        params: tuple[Any, ...] = (),
        severity: str = "warning",
    ) -> None:
        if not see_all and permission not in principal.permissions:
            return
        row = await db.fetch_one(sql, params)
        count = int(row["count"] if row else 0)
        if count:
            items.append(
                {
                    "id": key,
                    "title": title,
                    "message": message,
                    "count": count,
                    "href": href,
                    "severity": severity,
                }
            )

    farm_id = principal.farm_id
    farm_filter = (
        " AND EXISTS (SELECT 1 FROM order_items oi JOIN products p ON p.id = oi.product_id"
        " WHERE oi.order_id = o.id AND p.farm_id = ?)"
        if farm_id
        else ""
    )
    farm_params: tuple[Any, ...] = (farm_id,) if farm_id else ()
    await add(
        permission="orders.view",
        key="orders",
        title="Orders need fulfilment",
        message="Confirmed or processing orders still need fulfilment.",
        href="/orders",
        sql="SELECT COUNT(*) AS count FROM orders o"
        " WHERE o.order_status IN ('confirmed','processing')"
        " AND o.fulfilment_status NOT IN ('fulfilled','cancelled')" + farm_filter,
        params=farm_params,
    )
    await add(
        permission="returns.view",
        key="returns",
        title="Returns need review",
        message="Return requests are waiting for a decision.",
        href="/returns",
        sql="SELECT COUNT(*) AS count FROM return_requests rr JOIN orders o ON o.id = rr.order_id"
        " WHERE rr.status IN ('requested','under_review')" + farm_filter,
        params=farm_params,
    )
    await add(
        permission="submissions.view",
        key="submissions",
        title="Submissions need review",
        message="Community submissions are awaiting review.",
        href="/submissions",
        sql="SELECT COUNT(*) AS count FROM content_submissions"
        " WHERE status IN ('submitted','under_review')",
    )
    await add(
        permission="farm_requests.view",
        key="farm-requests",
        title="Farm applications need review",
        message="Growers have applied to supply the market.",
        href="/farm-requests",
        sql="SELECT COUNT(*) AS count FROM farm_partnership_requests"
        " WHERE status IN ('submitted','under_review','contacted')",
    )
    await add(
        permission="users.view",
        key="contacts",
        title="New contact messages",
        message="Customer contact messages have not been handled.",
        href="/contact-attempts",
        sql="SELECT COUNT(*) AS count FROM contact_messages WHERE status = 'new'",
    )
    await add(
        permission="products.view",
        key="products",
        title="Products not yet enabled",
        message="Products are still in a draft or review state.",
        href="/products",
        sql="SELECT COUNT(*) AS count FROM products WHERE archived_at IS NULL"
        " AND status IN ('draft','in_review','approved','scheduled')"
        " AND (? IS NULL OR farm_id = ?)",
        params=(farm_id, farm_id),
        severity="info",
    )
    if see_all or "inventory.view" in principal.permissions:
        inventory_rows = await db.fetch_all(
            """SELECT v.id FROM product_variants v JOIN products p ON p.id = v.product_id
               LEFT JOIN inventory_levels il ON il.variant_id = v.id
               WHERE p.status = 'published' AND p.archived_at IS NULL
                 AND (? IS NULL OR p.farm_id = ?)
               GROUP BY v.id HAVING COALESCE(SUM(il.on_hand - il.reserved), 0)
                 <= COALESCE(MAX(il.reorder_threshold), 0)""",
            (farm_id, farm_id),
        )
        if inventory_rows:
            items.append(
                {
                    "id": "inventory",
                    "title": "Inventory needs attention",
                    "message": (
                        "Enabled variants are out of stock or below their reorder threshold."
                    ),
                    "count": len(inventory_rows),
                    "href": "/inventory",
                    "severity": "danger",
                }
            )

    return {"items": items, "total": sum(item["count"] for item in items)}


def _validate_image_url(value: str) -> str:
    if value.startswith("/") and not value.startswith("//"):
        return value
    if value.startswith(("https://", "http://")):
        return value
    raise ValueError(f"Unsafe image URL: {value!r}")


class SiteControlHeroSlide(_CamelModel):
    image_url: str = Field(min_length=1, max_length=1000)
    image_alt: str = Field(default="", max_length=200)
    href: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=80)
    enabled: bool = True

    @field_validator("image_url")
    @classmethod
    def _safe_image_url(cls, value: str) -> str:
        return _validate_image_url(value)

    @field_validator("href")
    @classmethod
    def _safe_href(cls, value: str) -> str:
        return validate_href(value)


class SiteControlUpdate(_CamelModel):
    hero_eyebrow: str | None = Field(default=None, max_length=120)
    hero_heading: str | None = Field(default=None, max_length=160)
    hero_text: str | None = Field(default=None, max_length=500)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)
    # Bounded by the block model's structural ceiling, not by the operator's
    # own limit: that one lives in `app_settings` and is enforced below, where
    # a breach can be reported as "you allow N slides" rather than as a schema
    # error against a number nobody set.
    hero_slides: list[SiteControlHeroSlide] | None = Field(
        default=None, max_length=HERO_SLIDES_HARD_LIMIT
    )
    hero_max_slides: int | None = Field(default=None, ge=1, le=HERO_SLIDES_HARD_LIMIT)
    primary_action_label: str | None = Field(default=None, max_length=80)
    primary_action_href: str | None = Field(default=None, max_length=200)
    secondary_action_label: str | None = Field(default=None, max_length=80)
    secondary_action_href: str | None = Field(default=None, max_length=200)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)
    featured_categories: list[str] | None = Field(
        default=None, max_length=CURATED_MAX_ITEMS_HARD_LIMIT
    )
    fresh_favourites: list[str] | None = Field(
        default=None, max_length=CURATED_MAX_ITEMS_HARD_LIMIT
    )

    @field_validator("hero_image_url")
    @classmethod
    def _safe_hero_image_url(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return _validate_image_url(value)

    @field_validator("primary_action_href", "secondary_action_href")
    @classmethod
    def _safe_action_href(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return validate_href(value)


class SiteDocumentUpdate(_CamelModel):
    robots_txt: str | None = Field(default=None, max_length=20_000)
    sitemap_xml: str | None = Field(default=None, max_length=200_000)
    llms_txt: str | None = Field(default=None, max_length=40_000)


class CmsPageUpdateRequest(_CamelModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    slug: str | None = Field(default=None, max_length=120)
    status: str | None = Field(default=None, max_length=24)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)
    indexing_policy: str | None = Field(default=None, max_length=16)
    blocks: list[dict[str, Any]] | None = Field(default=None, max_length=100)
    change_summary: str | None = Field(default=None, max_length=300)


ARCHIVE_VIEW_PERMISSIONS = {
    "products.view",
    "categories.view",
    "users.view",
    "pages.view",
    "articles.view",
    "recipes.view",
}


def _can_view_archive(principal: Principal) -> bool:
    return any(principal.has(permission) for permission in ARCHIVE_VIEW_PERMISSIONS)


def _archive_row(kind: str, row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "kind": kind,
        "name": row["name"],
        "slug": row["slug"],
        "status": row["status"],
        "archivedAt": row["archived_at"] or row["updated_at"],
        "updatedAt": row["updated_at"],
        "updatedBy": row["updated_by"] or "-",
        "detail": row["detail"] or "",
    }


class ImageUploadRequest(_CamelModel):
    filename: str = Field(min_length=1, max_length=180)
    content_type: str = Field(min_length=1, max_length=80)
    data_base64: str = Field(min_length=1)


def _normalize_hero_slides(slides: Any) -> list[dict[str, Any]]:
    if not isinstance(slides, list):
        return []
    normalized = []
    # Read up to the structural ceiling, never the operator's configured cap.
    # Truncating to the cap here would hide already-saved banners from Homepage
    # Settings, and the next save would then write the shortened list back as
    # the truth -- lowering the limit would silently delete slides.
    for slide in slides[:HERO_SLIDES_HARD_LIMIT]:
        if not isinstance(slide, dict):
            continue
        image_url = str(slide.get("imageUrl") or "")
        if not image_url:
            continue
        normalized.append(
            {
                "imageUrl": image_url,
                "imageAlt": str(slide.get("imageAlt") or ""),
                "href": str(slide.get("href") or "/shop"),
                "label": str(slide.get("label") or "Explore"),
                "enabled": bool(slide.get("enabled", True)),
            }
        )
    return normalized


def _home_hero(page: dict[str, Any]) -> dict[str, Any]:
    content = json.loads(page["content_json"])
    for block in content.get("blocks", []):
        if block.get("type") == "hero":
            return block
    return {
        "props": {
            "eyebrow": "",
            "heading": page["title"],
            "text": "",
            "imageUrl": "",
            "imageAlt": "",
            "slides": [],
            "primaryAction": {"label": "Shop now", "href": "/shop"},
            "secondaryAction": None,
        }
    }


def _home_favourites(page: dict[str, Any]) -> dict[str, Any]:
    content = json.loads(page["content_json"])
    for block in content.get("blocks", []):
        if block.get("type") == "product_collection":
            return block
    return {
        "id": "blk_favourites",
        "type": "product_collection",
        "version": 1,
        "enabled": True,
        "props": {
            "eyebrow": "Fresh favourites",
            "heading": "Fresh favourites",
            "productSlugs": [],
        },
    }


def _home_categories(page: dict[str, Any]) -> dict[str, Any]:
    content = json.loads(page["content_json"])
    for block in content.get("blocks", []):
        if block.get("type") == "category_collection":
            return block
    return {
        "id": "blk_categories",
        "type": "category_collection",
        "version": 1,
        "enabled": True,
        "props": {"heading": "Shop by category", "categorySlugs": []},
    }


@router.get("/site-control")
async def get_site_control(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    page = await db.fetch_one(
        """
        SELECT p.id, p.title, p.seo_title, p.seo_description, p.seo_keywords,
               v.content_json
        FROM pages p
        JOIN page_versions v ON v.id = p.published_version_id
        WHERE p.slug = 'home' AND p.archived_at IS NULL
        """
    )
    if page is None:
        raise NotFoundError("Homepage not found.")
    hero = _home_hero(page)["props"]
    slides = _normalize_hero_slides(hero.get("slides"))
    primary_slide = slides[0] if slides else {}
    primary = hero.get("primaryAction") or {}
    secondary = hero.get("secondaryAction") or {}
    return {
        "heroEyebrow": hero.get("eyebrow") or "",
        "heroHeading": hero.get("heading") or page["title"],
        "heroText": hero.get("text") or "",
        "heroImageUrl": primary_slide.get("imageUrl") or hero.get("imageUrl") or "",
        "heroImageAlt": primary_slide.get("imageAlt") or hero.get("imageAlt") or page["title"],
        "heroSlides": slides,
        "primaryActionLabel": primary.get("label") or "",
        "primaryActionHref": primary.get("href") or "",
        "secondaryActionLabel": secondary.get("label") or "",
        "secondaryActionHref": secondary.get("href") or "",
        "seoTitle": page["seo_title"] or "",
        "seoDescription": page["seo_description"] or "",
        "seoKeywords": page["seo_keywords"] or "",
        "featuredCategories": _home_categories(page)["props"].get("categorySlugs", []),
        "freshFavourites": _home_favourites(page)["props"].get("productSlugs", []),
        "heroMaxSlides": await load_hero_max_slides(db),
        # The console shows this so an operator raising the cap can see how far
        # it is allowed to go without guessing at a 422.
        "heroSlidesHardLimit": HERO_SLIDES_HARD_LIMIT,
    }


@router.patch("/site-control")
async def update_site_control(
    payload: SiteControlUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    page = await db.fetch_one(
        """
        SELECT p.id, p.published_version_id, v.content_json
        FROM pages p
        JOIN page_versions v ON v.id = p.published_version_id
        WHERE p.slug = 'home' AND p.archived_at IS NULL
        """
    )
    if page is None:
        raise NotFoundError("Homepage not found.")

    # Applied before the slides are checked, so raising the cap and adding the
    # extra slides can happen in one save. Lowering it never truncates what is
    # already stored -- it only stops the next save from growing past the new
    # number, which is reported below rather than silently dropping banners.
    hero_slide_limit = (
        await set_hero_max_slides(
            db, principal, _request_id(request), value=payload.hero_max_slides
        )
        if payload.hero_max_slides is not None
        else await load_hero_max_slides(db)
    )
    if payload.hero_slides is not None and len(payload.hero_slides) > hero_slide_limit:
        raise ValidationAppError(
            f"The banner carousel is limited to {hero_slide_limit} slides."
            " Raise the limit in Homepage Settings to add more."
        )

    content: dict[str, Any] = json.loads(page["content_json"])
    blocks: list[dict[str, Any]] = content.setdefault("blocks", [])
    hero: dict[str, Any] | None = next(
        (block for block in blocks if block.get("type") == "hero"), None
    )
    if hero is None:
        hero = {"id": "blk_hero", "type": "hero", "version": 1, "enabled": True, "props": {}}
        blocks.insert(0, hero)
    props: dict[str, Any] = hero.setdefault("props", {})

    fields = payload.model_dump(exclude_unset=True)
    for source, target in (
        ("hero_eyebrow", "eyebrow"),
        ("hero_heading", "heading"),
        ("hero_text", "text"),
        ("hero_image_url", "imageUrl"),
        ("hero_image_alt", "imageAlt"),
    ):
        if source in fields:
            props[target] = fields[source] or ""
    if "hero_slides" in fields:
        props["slides"] = [
            {
                "imageUrl": slide["image_url"],
                "imageAlt": slide["image_alt"],
                "href": slide["href"],
                "label": slide["label"],
                "enabled": slide["enabled"],
            }
            for slide in fields["hero_slides"]
        ]
        if props["slides"]:
            props["imageUrl"] = props["slides"][0]["imageUrl"]
            props["imageAlt"] = props["slides"][0]["imageAlt"]
    if "hero_image_url" in fields or "hero_image_alt" in fields:
        slides = props.setdefault("slides", [])
        if not isinstance(slides, list):
            slides = []
            props["slides"] = slides
        if not slides:
            slides.append(
                {
                    "imageUrl": props.get("imageUrl") or "",
                    "imageAlt": props.get("imageAlt") or "",
                    "href": (props.get("primaryAction") or {}).get("href") or "/shop",
                    "label": (props.get("primaryAction") or {}).get("label") or "Explore",
                    "enabled": True,
                }
            )
        first = slides[0]
        if isinstance(first, dict):
            if "hero_image_url" in fields:
                first["imageUrl"] = fields["hero_image_url"] or ""
            if "hero_image_alt" in fields:
                first["imageAlt"] = fields["hero_image_alt"] or ""
    if "primary_action_label" in fields or "primary_action_href" in fields:
        current = props.get("primaryAction") or {}
        props["primaryAction"] = {
            "label": fields.get("primary_action_label", current.get("label", "")) or "",
            "href": fields.get("primary_action_href", current.get("href", "")) or "",
        }
    if "secondary_action_label" in fields or "secondary_action_href" in fields:
        current = props.get("secondaryAction") or {}
        label = fields.get("secondary_action_label", current.get("label", "")) or ""
        href = fields.get("secondary_action_href", current.get("href", "")) or ""
        props["secondaryAction"] = {"label": label, "href": href} if label and href else None

    if "featured_categories" in fields or "fresh_favourites" in fields:
        curated_max_items = await load_curated_max_items(db)
        if (
            payload.featured_categories is not None
            and len(payload.featured_categories) > curated_max_items
        ):
            raise ValidationAppError(
                f"Featured categories are limited to {curated_max_items} items."
                " Raise the limit in Site Control to add more."
            )
        if (
            payload.fresh_favourites is not None
            and len(payload.fresh_favourites) > curated_max_items
        ):
            raise ValidationAppError(
                f"Fresh favourites are limited to {curated_max_items} items."
                " Raise the limit in Site Control to add more."
            )

    if "featured_categories" in fields:
        category_block: dict[str, Any] | None = next(
            (block for block in blocks if block.get("type") == "category_collection"), None
        )
        if category_block is None:
            category_block = {
                "id": "blk_categories",
                "type": "category_collection",
                "version": 1,
                "enabled": True,
                "props": {"heading": "Shop by category", "categorySlugs": []},
            }
            blocks.append(category_block)
        category_props: dict[str, Any] = category_block.setdefault("props", {})
        category_props["categorySlugs"] = list(dict.fromkeys(fields["featured_categories"]))

    if "fresh_favourites" in fields:
        fav_block: dict[str, Any] | None = next(
            (block for block in blocks if block.get("type") == "product_collection"), None
        )
        if fav_block is None:
            fav_block = {
                "id": "blk_favourites",
                "type": "product_collection",
                "version": 1,
                "enabled": True,
                "props": {
                    "eyebrow": "Fresh favourites",
                    "heading": "Fresh favourites",
                    "productSlugs": [],
                },
            }
            blocks.append(fav_block)
        fav_props: dict[str, Any] = fav_block.setdefault("props", {})
        fav_props["productSlugs"] = fields["fresh_favourites"]
        # The storefront renderer slices productSlugs to props.limit. That cap
        # only makes sense for a rule-driven feed; a manually curated list must
        # never be truncated below what the admin actually chose, so keep it in
        # lockstep with the saved list instead of leaving a stale seed value
        # (e.g. limit: 5) behind that silently drops later additions.
        fav_props["limit"] = len(fields["fresh_favourites"])

    now = utc_now_iso()
    await db.execute(
        "UPDATE page_versions SET content_json = ? WHERE id = ?",
        (json.dumps(content, separators=(",", ":")), page["published_version_id"]),
    )
    await db.execute(
        """
        UPDATE pages
        SET seo_title = COALESCE(?, seo_title),
            seo_description = COALESCE(?, seo_description),
            seo_keywords = COALESCE(?, seo_keywords),
            updated_at = ?,
            updated_by = ?
        WHERE id = ?
        """,
        (
            fields.get("seo_title"),
            fields.get("seo_description"),
            fields.get("seo_keywords"),
            now,
            principal.user_id,
            page["id"],
        ),
    )
    return await get_site_control(db, principal)


# ---------------------------------------------------------------------------
# Homepage sections
#
# The homepage is a list of blocks in `page_versions.content_json`. Site
# Control edits the *contents* of the three curated ones (banner, category row,
# product row); these routes edit the *list itself* -- what is shown, in what
# order, and what extra sections exist.
#
# Every write re-validates the whole block list through the same registry the
# CMS page editor uses (ADR-005), so a section added here can never be a shape
# the storefront does not know how to render.
# ---------------------------------------------------------------------------

# Human names for the section list. Falls back to the raw type for a block a
# future build introduces before this map catches up.
HOMEPAGE_SECTION_LABELS: dict[str, str] = {
    "hero": "Banner carousel",
    "category_collection": "Category row",
    "product_collection": "Product row",
    "page_links": "Page snippets",
    "farmer_story": "Farmer quote",
    "faq": "Questions and answers",
    "rich_text": "Text block",
    "newsletter": "Newsletter signup",
    "reviews_showcase": "Customer reviews",
    "promotion_banner": "Promotions banner",
    "recommendations": "Recommended products",
}

# Sections an owner may add from Homepage Settings. Deliberately the
# self-contained ones: the catalogue-backed rows already have dedicated
# curators on the same page, and a second copy of either would only compete
# with them for the same slugs.
ADDABLE_HOMEPAGE_SECTION_TYPES: tuple[str, ...] = (
    "page_links",
    "rich_text",
    "faq",
    "farmer_story",
    "newsletter",
    "reviews_showcase",
    "promotion_banner",
    "recommendations",
)

# Starting content for a new section. Written so the block validates on save
# and reads as an obvious placeholder in the editor -- it never reaches a
# customer, because new sections are created switched off.
_NEW_SECTION_PROPS: dict[str, dict[str, Any]] = {
    "page_links": {
        "heading": "More from True Grit",
        "intro": "",
        "items": [
            {
                "label": "Shop the market",
                "description": "Every organic product we carry, in one place.",
                "href": "/shop",
                "enabled": True,
            }
        ],
    },
    "rich_text": {"paragraphs": ["Replace this with the copy for the new section."]},
    "faq": {
        "heading": "Common questions",
        "items": [{"question": "Replace this question.", "answer": "Replace this answer."}],
    },
    "farmer_story": {
        "farmSlug": "",
        "quote": "Replace this with the grower's words.",
        "attribution": "Grower name, farm name",
    },
    "newsletter": {
        "heading": "A slower, better way to eat.",
        "consentText": "One considered letter a month. No noise, unsubscribe anytime.",
    },
    "reviews_showcase": {
        "heading": "What customers are saying",
        "subheading": "",
        "source": "rule",
        "reviewIds": [],
        "limit": 8,
        "minRating": 4,
    },
    "promotion_banner": {
        "source": "rule",
        "promotionId": None,
    },
    "recommendations": {
        "heading": "Customer favourites",
        "subheading": "Picked by shoppers",
        "limit": 8,
    },
}

# Sections Site Control's own editors bind to. Only the first block of each
# type is claimed -- a second product row added later is an ordinary custom
# section and stays removable. Disabling a claimed section is always allowed;
# deleting one would silently discard a curated slug list the other page still
# believes it owns.
_CLAIMED_SECTION_TYPES: tuple[str, ...] = ("hero", "category_collection", "product_collection")


def _claimed_section_ids(blocks: list[dict[str, Any]]) -> set[str]:
    claimed: set[str] = set()
    for block_type in _CLAIMED_SECTION_TYPES:
        first = next((block for block in blocks if block.get("type") == block_type), None)
        if first is not None and isinstance(first.get("id"), str):
            claimed.add(first["id"])
    return claimed


def _section_summary(block: dict[str, Any]) -> str:
    """One line describing what is actually inside the section."""
    props = block.get("props") or {}
    block_type = block.get("type")
    if block_type == "hero":
        slides = props.get("slides")
        count = len(slides) if isinstance(slides, list) else 0
        return f"{count} banner slide{'' if count == 1 else 's'}"
    if block_type == "category_collection":
        slugs = props.get("categorySlugs")
        count = len(slugs) if isinstance(slugs, list) else 0
        return f"{count} categor{'y' if count == 1 else 'ies'}"
    if block_type == "product_collection":
        slugs = props.get("productSlugs")
        count = len(slugs) if isinstance(slugs, list) else 0
        return f"{count} product{'' if count == 1 else 's'}"
    if block_type == "page_links":
        items = props.get("items")
        count = len(items) if isinstance(items, list) else 0
        return f"{count} page snippet{'' if count == 1 else 's'}"
    if block_type == "faq":
        items = props.get("items")
        count = len(items) if isinstance(items, list) else 0
        return f"{count} question{'' if count == 1 else 's'}"
    if block_type == "rich_text":
        paragraphs = props.get("paragraphs")
        count = len(paragraphs) if isinstance(paragraphs, list) else 0
        return f"{count} paragraph{'' if count == 1 else 's'}"
    if block_type == "farmer_story":
        return str(props.get("attribution") or "No attribution")
    if block_type == "newsletter":
        return str(props.get("heading") or "Newsletter signup")
    if block_type == "reviews_showcase":
        if props.get("source") == "manual":
            ids = props.get("reviewIds")
            count = len(ids) if isinstance(ids, list) else 0
            return f"{count} featured review{'' if count == 1 else 's'}"
        return f"Top-rated reviews, {props.get('minRating', 4)}+ stars"
    if block_type == "promotion_banner":
        return (
            "One specific promotion"
            if props.get("source") == "manual"
            else "Best active promotion, resolved automatically"
        )
    if block_type == "recommendations":
        limit = props.get("limit", 8)
        return f"Top {limit} best sellers, computed live from orders"
    return ""


def _section_payload(block: dict[str, Any], claimed: set[str]) -> dict[str, Any]:
    block_type = str(block.get("type") or "")
    block_id = str(block.get("id") or "")
    props = block.get("props") or {}
    return {
        "id": block_id,
        "type": block_type,
        "label": HOMEPAGE_SECTION_LABELS.get(block_type, block_type or "Unknown section"),
        "heading": str(props.get("heading") or ""),
        "summary": _section_summary(block),
        "enabled": bool(block.get("enabled", True)),
        # False for the three sections Site Control's own editors own. The
        # console greys out their delete button rather than letting the request
        # fail after the fact.
        "removable": block_id not in claimed,
        "props": props,
    }


class HomepageSectionCreate(_CamelModel):
    type: str = Field(min_length=1, max_length=40)


class HomepageSectionUpdate(_CamelModel):
    enabled: bool | None = None
    props: dict[str, Any] | None = None


class HomepageSectionOrder(_CamelModel):
    ids: list[str] = Field(min_length=1, max_length=MAX_BLOCKS)


async def _homepage_version(db: Database) -> dict[str, Any]:
    page = await db.fetch_one(
        """
        SELECT p.id, p.published_version_id, v.content_json
        FROM pages p
        JOIN page_versions v ON v.id = p.published_version_id
        WHERE p.slug = 'home' AND p.archived_at IS NULL
        """
    )
    if page is None:
        raise NotFoundError("Homepage not found.")
    return page


def _homepage_blocks(page: dict[str, Any]) -> list[dict[str, Any]]:
    content = json.loads(page["content_json"])
    blocks = content.get("blocks")
    if not isinstance(blocks, list):
        return []
    return [block for block in blocks if isinstance(block, dict)]


async def _write_homepage_blocks(
    db: Database,
    page: dict[str, Any],
    blocks: list[dict[str, Any]],
    principal: Principal,
) -> list[dict[str, Any]]:
    """Validate, persist, and return the saved sections.

    Validation covers the whole list rather than the one block being touched:
    a partial check would let the storefront receive a page this build cannot
    render because of a block nobody edited today.
    """
    validated = validate_blocks(blocks)
    normalized = [
        block.model_dump(mode="json", by_alias=True, exclude_none=True) for block in validated
    ]
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE page_versions SET content_json = ? WHERE id = ?",
                (
                    json.dumps({"blocks": normalized}, separators=(",", ":")),
                    page["published_version_id"],
                ),
            ),
            (
                "UPDATE pages SET updated_at = ?, updated_by = ? WHERE id = ?",
                (now, principal.user_id, page["id"]),
            ),
        ]
    )
    claimed = _claimed_section_ids(normalized)
    return [_section_payload(block, claimed) for block in normalized]


def _find_section(blocks: list[dict[str, Any]], section_id: str) -> int:
    for index, block in enumerate(blocks):
        if block.get("id") == section_id:
            return index
    raise NotFoundError("Homepage section not found.")


@router.get("/homepage/sections")
async def list_homepage_sections(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    blocks = _homepage_blocks(await _homepage_version(db))
    claimed = _claimed_section_ids(blocks)
    return {
        "sections": [_section_payload(block, claimed) for block in blocks],
        "addableTypes": [
            {"type": block_type, "label": HOMEPAGE_SECTION_LABELS[block_type]}
            for block_type in ADDABLE_HOMEPAGE_SECTION_TYPES
        ],
    }


@router.post("/homepage/sections")
async def create_homepage_section(
    payload: HomepageSectionCreate,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    if payload.type not in ADDABLE_HOMEPAGE_SECTION_TYPES:
        raise ValidationAppError(f"Cannot add a {payload.type!r} section from Homepage Settings.")
    page = await _homepage_version(db)
    blocks = _homepage_blocks(page)
    if len(blocks) >= MAX_BLOCKS:
        raise ValidationAppError(f"The homepage already has the maximum of {MAX_BLOCKS} sections.")
    blocks.append(
        {
            "id": new_id("blk"),
            "type": payload.type,
            "version": 1,
            # Switched off on purpose: a new section starts as placeholder copy,
            # and placeholder copy must never reach a customer because someone
            # was interrupted between adding it and writing it.
            "enabled": False,
            "props": json.loads(json.dumps(_NEW_SECTION_PROPS[payload.type])),
        }
    )
    return {"sections": await _write_homepage_blocks(db, page, blocks, principal)}


@router.patch("/homepage/sections/{section_id}")
async def update_homepage_section(
    section_id: str,
    payload: HomepageSectionUpdate,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    page = await _homepage_version(db)
    blocks = _homepage_blocks(page)
    index = _find_section(blocks, section_id)
    fields = payload.model_dump(exclude_unset=True)
    if "enabled" in fields and payload.enabled is not None:
        blocks[index]["enabled"] = payload.enabled
    if "props" in fields and payload.props is not None:
        # Type and id stay put: this route edits a section's contents, never
        # what kind of section it is.
        blocks[index]["props"] = payload.props
    return {"sections": await _write_homepage_blocks(db, page, blocks, principal)}


@router.delete("/homepage/sections/{section_id}")
async def delete_homepage_section(
    section_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    page = await _homepage_version(db)
    blocks = _homepage_blocks(page)
    index = _find_section(blocks, section_id)
    if section_id in _claimed_section_ids(blocks):
        raise ValidationAppError(
            "This section is edited elsewhere in Homepage Settings and cannot be deleted."
            " Untick it to hide it from customers instead."
        )
    blocks.pop(index)
    return {"sections": await _write_homepage_blocks(db, page, blocks, principal)}


@router.post("/homepage/sections/order")
async def reorder_homepage_sections(
    payload: HomepageSectionOrder,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    page = await _homepage_version(db)
    blocks = _homepage_blocks(page)
    by_id = {str(block.get("id")): block for block in blocks}
    # An exact-set check, not a "reorder what I recognise". A short list would
    # otherwise delete every section the caller left out, which is a very
    # expensive way to spell "drag".
    if len(payload.ids) != len(set(payload.ids)) or set(payload.ids) != set(by_id):
        raise ValidationAppError("The new order must list every homepage section exactly once.")
    return {
        "sections": await _write_homepage_blocks(
            db, page, [by_id[section_id] for section_id in payload.ids], principal
        )
    }


class HomepageCountryOverrideUpdate(_CamelModel):
    enabled: bool


@router.get("/homepage/country-overrides")
async def get_homepage_country_overrides(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"overrides": await list_homepage_country_overrides(db)}


@router.put("/homepage/country-overrides/{country}/{section_id}")
async def put_homepage_country_override(
    country: str,
    section_id: str,
    payload: HomepageCountryOverrideUpdate,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
    request: Request,
) -> Any:
    resolved = validate_homepage_country(country)
    # The section must actually exist on the homepage today -- an override
    # keyed to a stale or mistyped id would silently do nothing forever.
    blocks = _homepage_blocks(await _homepage_version(db))
    _find_section(blocks, section_id)
    await set_homepage_country_override(
        db,
        principal,
        _request_id(request),
        country=resolved,
        block_id=section_id,
        enabled=payload.enabled,
    )
    return {"overrides": await list_homepage_country_overrides(db)}


@router.delete("/homepage/country-overrides/{country}/{section_id}")
async def delete_homepage_country_override(
    country: str,
    section_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
    request: Request,
) -> Any:
    resolved = validate_homepage_country(country)
    await set_homepage_country_override(
        db,
        principal,
        _request_id(request),
        country=resolved,
        block_id=section_id,
        enabled=None,
    )
    return {"overrides": await list_homepage_country_overrides(db)}


# ---------------------------------------------------------------------------
# Price adjustments: a signed markup or discount, scopable by country, by a
# single product, by a whole category, or combined with country. See
# `services/price_adjustments.py` for resolution order and why a markup never
# shows a fabricated "was" price.
# ---------------------------------------------------------------------------


class PriceAdjustmentUpdate(_CamelModel):
    scope: str = Field(default="global", min_length=1, max_length=16)
    product_id: str | None = Field(default=None, max_length=64)
    category_id: str | None = Field(default=None, max_length=64)
    percent: int = Field(ge=PRICE_ADJUSTMENT_MIN_PERCENT, le=PRICE_ADJUSTMENT_MAX_PERCENT)
    active: bool = True


@router.get("/price-adjustments")
async def get_price_adjustments(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"rules": await list_price_adjustments(db)}


@router.put("/price-adjustments")
async def put_price_adjustment(
    payload: PriceAdjustmentUpdate,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
    request: Request,
) -> Any:
    await save_price_adjustment(
        db,
        principal,
        _request_id(request),
        scope=payload.scope,
        product_id=payload.product_id,
        category_id=payload.category_id,
        percent=payload.percent,
        active=payload.active,
    )
    return {"rules": await list_price_adjustments(db)}


@router.delete("/price-adjustments/{rule_id}")
async def remove_price_adjustment(
    rule_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
    request: Request,
) -> Any:
    await delete_price_adjustment(db, principal, _request_id(request), rule_id=rule_id)
    return {"rules": await list_price_adjustments(db)}


# ---------------------------------------------------------------------------
# Appearance: colours and ambient effects
#
# Colours are per scope -- 'global' plus a row per page that wants its own look
# -- so they get list/save/delete routes. Effects are site-wide and live on the
# global row, so they get one PUT. Both read back through the same public
# payload the storefront uses, which is how the console's preview and the live
# site are guaranteed to agree.
# ---------------------------------------------------------------------------


class ThemeScopeUpdate(_CamelModel):
    scope: str = Field(min_length=1, max_length=200)
    # Values are checked against a colour allow-list in the service: these
    # strings end up interpolated into a stylesheet, so "it is a string" is not
    # enough to let one through.
    tokens: dict[str, Any] = Field(default_factory=dict)


class EffectsUpdate(_CamelModel):
    ambient: dict[str, Any] = Field(default_factory=dict)
    cursor: dict[str, Any] = Field(default_factory=dict)
    # Omitted or "global" saves the site-wide default; "country:XX" saves that
    # country's override. Never a page path -- effects are a whole-visit
    # decision, not something that makes sense to swap mid-browse.
    scope: str = Field(default=GLOBAL_SCOPE, min_length=1, max_length=40)


# A scope arrives on the URL without its leading slash (`appearance/theme/shop`
# maps to the page `/shop`), because a doubled slash is not something a client
# should have to get right for a delete to work. `global` and `country:XX` are
# the two exceptions: each must reach the service layer exactly as typed, or
# the literal word "global" would be reinterpreted as the page path "/global"
# and "country:IN" as "/country:IN" -- neither of which is the scope the
# caller meant, and the "site-wide palette cannot be deleted" guard would never
# fire for the one request it exists to catch.
def _resolve_url_scope(scope: str) -> str:
    if scope == GLOBAL_SCOPE or is_country_scope(scope) or scope.startswith("/"):
        return scope
    return f"/{scope}"


@router.get("/appearance")
async def get_appearance(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    appearance = await load_appearance(db)
    return {
        **appearance,
        "scopes": await list_theme_scopes(db),
        # Shipped alongside the values so the console can render a swatch grid
        # and a page/country picker without a second source of truth to drift
        # from.
        "tokenKeys": list(THEME_TOKEN_KEYS),
        "ambientEffects": list(AMBIENT_EFFECT_KEYS),
        "cursorTrails": list(CURSOR_TRAIL_KEYS),
    }


@router.put("/appearance/theme")
async def put_theme_scope(
    payload: ThemeScopeUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await save_theme_scope(
        db,
        principal,
        _request_id(request),
        scope=payload.scope,
        tokens=validate_theme_tokens(payload.tokens),
    )
    return await get_appearance(db, principal)


@router.delete("/appearance/theme/{scope:path}")
async def remove_theme_scope(
    scope: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await delete_theme_scope(db, principal, _request_id(request), scope=_resolve_url_scope(scope))
    return await get_appearance(db, principal)


@router.put("/appearance/effects")
async def put_effects(
    payload: EffectsUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await save_effects(
        db,
        principal,
        _request_id(request),
        effects={"ambient": payload.ambient, "cursor": payload.cursor},
        scope=payload.scope,
    )
    return await get_appearance(db, principal)


@router.delete("/appearance/effects/{scope:path}")
async def remove_country_effects(
    scope: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    """Clear one country's effects override, reverting it to the global default.

    Never touches that country's colours (if it has any) -- see
    `clear_country_effects` for why the two must be independently clearable.
    """
    await clear_country_effects(
        db, principal, _request_id(request), scope=_resolve_url_scope(scope)
    )
    return await get_appearance(db, principal)


# ---------------------------------------------------------------------------
# Announcement banner: site-wide, or one per visitor country
# ---------------------------------------------------------------------------


class AnnouncementUpdate(_CamelModel):
    scope: str = Field(default="global", min_length=1, max_length=16)
    active: bool = False
    message: str = Field(default="", max_length=220)
    path: str = Field(default="", max_length=200)


@router.get("/announcements")
async def get_announcements(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"scopes": await list_announcements(db)}


@router.put("/announcements")
async def put_announcement(
    payload: AnnouncementUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await save_announcement(
        db,
        principal,
        _request_id(request),
        scope=payload.scope,
        active=payload.active,
        message=payload.message,
        path=payload.path,
    )
    return {"scopes": await list_announcements(db)}


@router.delete("/announcements/{scope}")
async def remove_announcement(
    scope: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await delete_country_announcement(db, principal, _request_id(request), scope=scope)
    return {"scopes": await list_announcements(db)}


async def _site_document_payload(db: Database, rows: list[dict[str, Any]]) -> dict[str, str]:
    defaults = await default_site_documents(db, get_settings())
    by_key = {key: row["content"] for key, row in defaults.items()}
    by_key.update({row["key"]: row["content"] for row in rows})
    return {
        "robotsTxt": by_key.get("robots_txt", ""),
        "sitemapXml": by_key.get("sitemap_xml", ""),
        "llmsTxt": by_key.get("llms_txt", ""),
    }


@router.get("/site-documents")
async def get_site_documents(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    await _require_owner(db, principal)
    rows = await SiteDocumentRepository(db).list()
    return await _site_document_payload(db, rows)


@router.patch("/site-documents")
async def update_site_documents(
    payload: SiteDocumentUpdate,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await _require_owner(db, principal)
    fields = payload.model_dump(exclude_unset=True)
    key_map = {
        "robots_txt": ("robots_txt", SITE_DOCUMENT_TYPES["robots_txt"]),
        "sitemap_xml": ("sitemap_xml", SITE_DOCUMENT_TYPES["sitemap_xml"]),
        "llms_txt": ("llms_txt", SITE_DOCUMENT_TYPES["llms_txt"]),
    }
    now = utc_now_iso()
    statements: list[tuple[str, tuple[Any, ...]]] = []
    for field, (key, content_type) in key_map.items():
        if field not in fields:
            continue
        statements.append(
            (
                """
                INSERT INTO site_documents (key, content, content_type, updated_at, updated_by)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                  content = excluded.content,
                  content_type = excluded.content_type,
                  updated_at = excluded.updated_at,
                  updated_by = excluded.updated_by
                """,
                (key, fields[field] or "", content_type, now, principal.user_id),
            )
        )
    if statements:
        statements.append(
            audit_statement(
                action="site_documents.updated",
                entity_type="site_documents",
                entity_id="global",
                actor_id=principal.user_id,
                request_id=_request_id(request),
                created_at=now,
                after={"keys": [key_map[field][0] for field in fields if field in key_map]},
            )
        )
        await db.batch(statements)
    rows = await SiteDocumentRepository(db).list()
    return await _site_document_payload(db, rows)


def _route_seo_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": row["path"],
        "seoTitle": row["seo_title"],
        "seoDescription": row["seo_description"],
        "seoKeywords": row["seo_keywords"],
        "indexingPolicy": row["indexing_policy"],
        "updatedAt": row["updated_at"],
    }


class RouteSeoUpdate(_CamelModel):
    path: str = Field(min_length=1, max_length=200)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)
    indexing_policy: str = Field(default="index", max_length=16)

    @field_validator("path")
    @classmethod
    def _leading_slash(cls, value: str) -> str:
        value = value.strip()
        if not value.startswith("/") or value.startswith("//"):
            raise ValueError("Path must start with a single '/'.")
        return value


@router.get("/route-seo")
async def list_route_seo_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    rows = await RouteSeoRepository(db).list()
    return {"items": [_route_seo_payload(row) for row in rows]}


@router.patch("/route-seo")
async def update_route_seo_endpoint(
    payload: RouteSeoUpdate,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    if payload.indexing_policy not in ("index", "noindex"):
        raise ValidationAppError("Unsupported indexing policy.")
    now = utc_now_iso()
    await db.execute(
        """
        INSERT INTO route_seo_overrides
          (path, seo_title, seo_description, seo_keywords, indexing_policy, updated_at, updated_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          seo_title = excluded.seo_title,
          seo_description = excluded.seo_description,
          seo_keywords = excluded.seo_keywords,
          indexing_policy = excluded.indexing_policy,
          updated_at = excluded.updated_at,
          updated_by = excluded.updated_by
        """,
        (
            payload.path,
            (payload.seo_title or "").strip() or None,
            (payload.seo_description or "").strip() or None,
            (payload.seo_keywords or "").strip() or None,
            payload.indexing_policy,
            now,
            principal.user_id,
        ),
    )
    row = await RouteSeoRepository(db).get(payload.path)
    return _route_seo_payload(row) if row else {"path": payload.path}


async def _page_detail(db: Database, page_id: str) -> dict[str, Any] | None:
    page = await db.fetch_one(
        """
        SELECT p.id, p.slug, p.title, p.page_type, p.template_key, p.status,
               p.seo_title, p.seo_description, p.seo_keywords, p.indexing_policy,
               p.updated_at, p.published_version_id,
               COALESCE(v.content_json, latest.content_json, '{"blocks":[]}') AS content_json
        FROM pages p
        LEFT JOIN page_versions v ON v.id = p.published_version_id
        LEFT JOIN (
          SELECT pv.page_id, pv.content_json
          FROM page_versions pv
          JOIN (
            SELECT page_id, MAX(version_number) AS version_number
            FROM page_versions
            GROUP BY page_id
          ) mx ON mx.page_id = pv.page_id AND mx.version_number = pv.version_number
        ) latest ON latest.page_id = p.id
        WHERE p.id = ? AND p.archived_at IS NULL
        """,
        (page_id,),
    )
    if page is None:
        return None
    content = json.loads(page["content_json"] or '{"blocks":[]}')
    blocks = content.get("blocks", [])
    if not isinstance(blocks, list):
        blocks = []
    return {
        "id": page["id"],
        "slug": page["slug"],
        "title": page["title"],
        "pageType": page["page_type"],
        "templateKey": page["template_key"],
        "status": page["status"],
        "seoTitle": page["seo_title"] or "",
        "seoDescription": page["seo_description"] or "",
        "seoKeywords": page["seo_keywords"] or "",
        "indexingPolicy": page["indexing_policy"],
        "updatedAt": page["updated_at"],
        "blockCount": len(blocks),
        "blocks": blocks,
    }


@router.get("/pages")
async def list_cms_pages(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pages.view"))],
) -> Any:
    rows = await db.fetch_all(
        """
        SELECT p.id, p.slug, p.title, p.page_type, p.template_key, p.status,
               p.seo_title, p.seo_description, p.seo_keywords, p.indexing_policy,
               p.updated_at, COALESCE(v.content_json, '{"blocks":[]}') AS content_json
        FROM pages p
        LEFT JOIN page_versions v ON v.id = p.published_version_id
        WHERE p.archived_at IS NULL
        ORDER BY CASE WHEN p.slug = 'home' THEN 0 ELSE 1 END, p.slug
        """
    )
    items = []
    for row in rows:
        content = json.loads(row["content_json"] or '{"blocks":[]}')
        blocks = content.get("blocks", [])
        items.append(
            {
                "id": row["id"],
                "slug": row["slug"],
                "title": row["title"],
                "pageType": row["page_type"],
                "templateKey": row["template_key"],
                "status": row["status"],
                "seoTitle": row["seo_title"] or "",
                "seoDescription": row["seo_description"] or "",
                "seoKeywords": row["seo_keywords"] or "",
                "indexingPolicy": row["indexing_policy"],
                "updatedAt": row["updated_at"],
                "blockCount": len(blocks) if isinstance(blocks, list) else 0,
            }
        )
    return {"items": items}


@router.get("/pages/{page_id}")
async def get_cms_page(
    page_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pages.view"))],
) -> Any:
    page = await _page_detail(db, page_id)
    if page is None:
        raise NotFoundError("Page not found.")
    return page


@router.patch("/pages/{page_id}")
async def update_cms_page(
    page_id: str,
    payload: CmsPageUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("pages.edit"))],
) -> Any:
    current = await db.fetch_one(
        "SELECT * FROM pages WHERE id = ? AND archived_at IS NULL",
        (page_id,),
    )
    if current is None:
        raise NotFoundError("Page not found.")
    fields = payload.model_dump(exclude_unset=True)
    updates: dict[str, Any] = {}
    if "title" in fields and payload.title is not None:
        updates["title"] = payload.title.strip()
    if "slug" in fields and payload.slug is not None:
        slug = validate_slug(payload.slug.strip())
        existing = await db.fetch_one(
            "SELECT id FROM pages WHERE slug = ? AND id != ?", (slug, page_id)
        )
        if existing is not None:
            raise ValidationAppError("A page with that slug already exists.")
        updates["slug"] = slug
    if "status" in fields and payload.status is not None:
        if payload.status not in {"draft", "published", "unpublished", "archived"}:
            raise ValidationAppError("Unsupported page status.")
        updates["status"] = payload.status
    if "indexing_policy" in fields and payload.indexing_policy is not None:
        if payload.indexing_policy not in {"index", "noindex"}:
            raise ValidationAppError("Unsupported indexing policy.")
        updates["indexing_policy"] = payload.indexing_policy
    for key in ("seo_title", "seo_description", "seo_keywords"):
        if key in fields:
            updates[key] = fields[key] or None

    now = utc_now_iso()
    statements: list[tuple[str, tuple[Any, ...]]] = []
    next_status = updates.get("status", current["status"])
    if payload.blocks is not None:
        # Validated the same way articles/recipes are — never trust raw block
        # JSON straight from the request onto disk (ADR-005). This was
        # previously skipped for pages; unknown/unsafe blocks were only ever
        # caught by the storefront's defensive renderer, not rejected here.
        validated_blocks = validate_blocks(payload.blocks)
        blocks_json = [
            block.model_dump(mode="json", by_alias=True, exclude_none=True)
            for block in validated_blocks
        ]
        next_version_row = await db.fetch_one(
            "SELECT COALESCE(MAX(version_number), 0) + 1 AS version_number"
            " FROM page_versions WHERE page_id = ?",
            (page_id,),
        )
        version_id = new_id("pgv")
        workflow_state = "published" if next_status == "published" else "draft"
        statements.append(
            (
                """
                INSERT INTO page_versions (
                  id, page_id, version_number, content_json, change_summary,
                  workflow_state, created_at, created_by, published_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    page_id,
                    int(next_version_row["version_number"]),
                    json.dumps({"blocks": blocks_json}, separators=(",", ":")),
                    payload.change_summary or "Updated from admin CMS editor.",
                    workflow_state,
                    now,
                    principal.user_id,
                    now if workflow_state == "published" else None,
                ),
            )
        )
        if workflow_state == "published":
            updates["published_version_id"] = version_id
    if updates:
        updates["updated_at"] = now
        updates["updated_by"] = principal.user_id
        assignments = ", ".join(f"{key} = ?" for key in updates)
        statements.append(
            (f"UPDATE pages SET {assignments} WHERE id = ?", (*updates.values(), page_id))
        )
    if statements:
        statements.append(
            audit_statement(
                action="page.updated",
                entity_type="page",
                entity_id=page_id,
                actor_id=principal.user_id,
                request_id=_request_id(request),
                created_at=now,
                before={"status": current["status"], "slug": current["slug"]},
                after={
                    "status": next_status,
                    "slug": updates.get("slug", current["slug"]),
                    "blocksUpdated": payload.blocks is not None,
                },
            )
        )
        await db.batch(statements)
    page = await _page_detail(db, page_id)
    if page is None:
        raise NotFoundError("Page not found.")
    return page


# ---------------------------------------------------------------------------
# Per-locale page content (migration 0067) -- the homepage and static pages
# both use `pages`/`page_versions`, so this one mechanism translates both.
# `pages.edit` gates it, the same permission that gates the English content
# these translations are alongside.
# ---------------------------------------------------------------------------


def _page_translation_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "locale": row["locale"],
        "content": json.loads(row["content_json"]),
        "autoTranslated": bool(row["auto_translated"]),
        "updatedAt": row["updated_at"],
    }


class PageTranslationSaveRequest(_CamelModel):
    blocks: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_BLOCKS)


@router.get("/pages/{page_id}/translations")
async def list_page_translations_endpoint(
    page_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pages.view"))],
) -> Any:
    rows = await translation_service.list_page_translations(db, page_id)
    return {
        "items": [
            {
                "locale": row["locale"],
                "autoTranslated": bool(row["auto_translated"]),
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]
    }


@router.get("/pages/{page_id}/translations/{locale}")
async def get_page_translation_endpoint(
    page_id: str,
    locale: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pages.view"))],
) -> Any:
    row = await translation_service.get_page_translation(db, page_id, locale)
    if row is None:
        # No translation yet is not an error -- the editor's own empty state
        # (and the storefront's English fallback) both expect this, not a 404.
        page = await _page_detail(db, page_id)
        if page is None:
            raise NotFoundError("Page not found.")
        return {
            "locale": locale,
            "content": {"blocks": page["blocks"]},
            "autoTranslated": False,
            "updatedAt": None,
        }
    return _page_translation_payload(row)


@router.put("/pages/{page_id}/translations/{locale}")
async def save_page_translation_endpoint(
    page_id: str,
    locale: str,
    payload: PageTranslationSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("pages.edit"))],
) -> Any:
    saved = await translation_service.save_page_translation(
        db,
        principal,
        _request_id(request),
        page_id,
        locale,
        {"blocks": payload.blocks},
        auto_translated=False,
    )
    return _page_translation_payload(saved)


@router.post("/pages/{page_id}/translations/{locale}/auto-translate")
async def auto_translate_page_endpoint(
    page_id: str,
    locale: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    translator: Annotated[Translator, Depends(get_translator)],
    principal: Annotated[Principal, Depends(require_permission("pages.edit"))],
) -> Any:
    saved = await translation_service.auto_translate_page(
        db, principal, _request_id(request), translator, page_id, locale
    )
    return _page_translation_payload(saved)


@router.delete("/pages/{page_id}/translations/{locale}")
async def delete_page_translation_endpoint(
    page_id: str,
    locale: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("pages.edit"))],
) -> Any:
    await translation_service.delete_page_translation(db, page_id, locale)
    return {"pageId": page_id, "locale": locale, "deleted": True}


# ---------------------------------------------------------------------------
# Per-locale field overrides for database-sourced content (migration 0068) --
# navigation labels, category names/descriptions, product names/descriptions,
# and article/recipe titles/excerpts. One generic set of routes for every
# entity type `services.entity_translation.TRANSLATABLE_FIELDS` knows about,
# mirroring the service itself -- five near-identical route groups would just
# be this same logic copied five times. The permission required varies by
# entity type (a category editor should not need `pages.edit` to translate a
# category), so it is resolved from `_ENTITY_TRANSLATION_PERMISSIONS` and
# checked at request time rather than via a route-fixed `require_permission`.
# ---------------------------------------------------------------------------

_ENTITY_TRANSLATION_PERMISSIONS: dict[str, tuple[str, str]] = {
    # No dedicated navigation permission exists (migration/seed-managed only,
    # no admin CRUD) -- gated on `pages.*` since the nav translations panel
    # lives alongside the page translations panel in Site Control.
    "navigation_item": ("pages.view", "pages.edit"),
    "category": ("categories.view", "categories.edit"),
    "product": ("products.view", "products.edit"),
    "article": ("articles.view", "articles.edit"),
    "recipe": ("recipes.view", "recipes.edit"),
}


def _require_entity_translation_permission(
    entity_type: str, principal: Principal, *, edit: bool
) -> None:
    permissions = _ENTITY_TRANSLATION_PERMISSIONS.get(entity_type)
    if permissions is None:
        raise NotFoundError(f"'{entity_type}' does not support translations yet.")
    required = permissions[1] if edit else permissions[0]
    if not principal.has(required):
        raise PermissionDeniedError()


def _camel_fields(fields: dict[str, str]) -> dict[str, str]:
    """`fields` is a free-form map, not a Pydantic model, so `_CamelModel`'s
    alias generator never touches its keys -- converted explicitly here (and
    the reverse in `services.entity_translation.save_entity_translation`) so
    the admin UI reads and writes `shortDescription` like every other field
    in this API, never the Python-internal `short_description`."""
    return {to_camel(key): value for key, value in fields.items()}


def _entity_translation_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "locale": row["locale"],
        "fields": _camel_fields(row["fields"]),
        "autoTranslated": bool(row["auto_translated"]),
        "updatedAt": row["updated_at"],
    }


class EntityTranslationSaveRequest(_CamelModel):
    fields: dict[str, str] = Field(default_factory=dict)


@router.get("/translations/{entity_type}/{entity_id}")
async def list_entity_translations_endpoint(
    entity_type: str,
    entity_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    _require_entity_translation_permission(entity_type, principal, edit=False)
    rows = await entity_translation_service.list_entity_translations(db, entity_type, entity_id)
    return {
        "items": [
            {
                "locale": row["locale"],
                "autoTranslated": bool(row["auto_translated"]),
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ]
    }


@router.get("/translations/{entity_type}/{entity_id}/{locale}")
async def get_entity_translation_endpoint(
    entity_type: str,
    entity_id: str,
    locale: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    _require_entity_translation_permission(entity_type, principal, edit=False)
    row = await entity_translation_service.get_entity_translation(
        db, entity_type, entity_id, locale
    )
    if row is None:
        # No translation yet is not an error -- the editor's own empty state
        # (and the storefront's English fallback) both expect this, not a 404.
        fields = await entity_translation_service.get_source_fields(db, entity_type, entity_id)
        return {
            "locale": locale,
            "fields": _camel_fields(fields),
            "autoTranslated": False,
            "updatedAt": None,
        }
    return _entity_translation_payload(row)


@router.put("/translations/{entity_type}/{entity_id}/{locale}")
async def save_entity_translation_endpoint(
    entity_type: str,
    entity_id: str,
    locale: str,
    payload: EntityTranslationSaveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    _require_entity_translation_permission(entity_type, principal, edit=True)
    saved = await entity_translation_service.save_entity_translation(
        db,
        principal,
        _request_id(request),
        entity_type,
        entity_id,
        locale,
        payload.fields,
        auto_translated=False,
    )
    return _entity_translation_payload(saved)


@router.post("/translations/{entity_type}/{entity_id}/{locale}/auto-translate")
async def auto_translate_entity_endpoint(
    entity_type: str,
    entity_id: str,
    locale: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    translator: Annotated[Translator, Depends(get_translator)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    _require_entity_translation_permission(entity_type, principal, edit=True)
    saved = await entity_translation_service.auto_translate_entity(
        db, principal, _request_id(request), translator, entity_type, entity_id, locale
    )
    return _entity_translation_payload(saved)


@router.delete("/translations/{entity_type}/{entity_id}/{locale}")
async def delete_entity_translation_endpoint(
    entity_type: str,
    entity_id: str,
    locale: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    _require_entity_translation_permission(entity_type, principal, edit=True)
    await entity_translation_service.delete_entity_translation(db, entity_type, entity_id, locale)
    return {"entityType": entity_type, "entityId": entity_id, "locale": locale, "deleted": True}


# ---------------------------------------------------------------------------
# Articles (blog) — authored by `blogger`, reviewed/published by `articles.approve`/`.publish`
# ---------------------------------------------------------------------------


class ArticleCreateRequest(_CamelModel):
    title: str = Field(min_length=3, max_length=180)
    slug: str | None = Field(default=None, max_length=96)
    excerpt: str | None = Field(default=None, max_length=300)


class ArticleUpdateRequest(_CamelModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    slug: str | None = Field(default=None, max_length=96)
    excerpt: str | None = Field(default=None, max_length=300)
    hero_media_id: str | None = Field(default=None, max_length=64)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)
    reading_minutes: int | None = Field(default=None, ge=1, le=60)
    author_user_id: str | None = Field(default=None, max_length=64)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=300)
    indexing_policy: str | None = Field(default=None, max_length=16)
    blocks: list[dict[str, Any]] | None = Field(default=None, max_length=40)
    pull_quote: str | None = Field(default=None, max_length=400)

    @field_validator("hero_image_url")
    @classmethod
    def _safe_hero_image_url(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return _validate_image_url(value)


class ChangesRequestedRequest(_CamelModel):
    note: str = Field(min_length=1, max_length=500)


def _article_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "slug": row["slug"],
        "status": row["status"],
        "authorName": row["author_name"],
        "updatedAt": row["updated_at"],
        "publishedAt": row["published_at"],
        "hasDraftChanges": row["latest_version_number"] != row["published_version_number"],
    }


def _article_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "slug": row["slug"],
        "excerpt": row["excerpt"],
        "readingMinutes": row["reading_minutes"],
        "status": row["status"],
        "authorUserId": row["author_user_id"],
        "heroMediaId": row["hero_media_id"],
        "heroImageUrl": row["hero_image_url"],
        "heroImageAlt": row["hero_image_alt"],
        "seoTitle": row["seo_title"],
        "seoDescription": row["seo_description"],
        "seoKeywords": row["seo_keywords"],
        "canonicalUrl": row["canonical_url"],
        "indexingPolicy": row["indexing_policy"],
        "updatedAt": row["updated_at"],
        "blocks": row["blocks"],
        "pullQuote": row["pull_quote"],
    }


@router.get("/articles")
async def list_articles_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    scope = None if principal.has("articles.approve") else principal.user_id
    rows = await ArticleRepository(db).list_admin(
        author_user_id=scope, limit=limit, offset=offset, search=search
    )
    return {"items": [_article_summary(row) for row in rows], "limit": limit, "offset": offset}


@router.post("/articles")
async def create_article_endpoint(
    payload: ArticleCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.create"))],
) -> Any:
    return await article_service.create_article(
        db,
        principal,
        _request_id(request),
        title=payload.title,
        slug=payload.slug,
        excerpt=payload.excerpt,
    )


@router.get("/articles/{article_id}")
async def get_article_endpoint(
    article_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.view"))],
) -> Any:
    row = await ArticleRepository(db).get_admin_detail(article_id)
    if row is None:
        raise NotFoundError("Article not found.")
    article_service.assert_owns_or_reviews(row, principal)
    return _article_detail(row)


@router.patch("/articles/{article_id}")
async def update_article_endpoint(
    article_id: str,
    payload: ArticleUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.edit"))],
) -> Any:
    fields = payload.model_dump(exclude_unset=True)
    await article_service.update_article(
        db, principal, _request_id(request), article_id, fields=fields
    )
    row = await ArticleRepository(db).get_admin_detail(article_id)
    if row is None:
        raise NotFoundError("Article not found.")
    return _article_detail(row)


@router.post("/articles/{article_id}/submit-for-review")
async def submit_article_endpoint(
    article_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.edit"))],
) -> Any:
    return await article_service.submit_article(db, principal, _request_id(request), article_id)


@router.post("/articles/{article_id}/approve")
async def approve_article_endpoint(
    article_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.approve"))],
) -> Any:
    return await article_service.approve_article(db, principal, _request_id(request), article_id)


@router.post("/articles/{article_id}/request-changes")
async def request_article_changes_endpoint(
    article_id: str,
    payload: ChangesRequestedRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.approve"))],
) -> Any:
    return await article_service.request_article_changes(
        db, principal, _request_id(request), article_id, payload.note
    )


@router.post("/articles/{article_id}/publish")
async def publish_article_endpoint(
    article_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.publish"))],
) -> Any:
    return await publish_article(db, article_id, principal, _request_id(request))


@router.post("/articles/{article_id}/unpublish")
async def unpublish_article_endpoint(
    article_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.publish"))],
) -> Any:
    return await article_service.unpublish_article(db, principal, _request_id(request), article_id)


class ArticleBulkDeleteRequest(_CamelModel):
    article_ids: list[str] = Field(min_length=1, max_length=100)


@router.delete("/articles/{article_id}")
async def delete_article_endpoint(
    article_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.edit"))],
) -> Any:
    return await article_service.archive_article(db, principal, _request_id(request), article_id)


@router.post("/articles/bulk-delete")
async def bulk_delete_articles_endpoint(
    payload: ArticleBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("articles.edit"))],
) -> Any:
    deleted: list[str] = []
    for article_id in payload.article_ids:
        await article_service.archive_article(db, principal, _request_id(request), article_id)
        deleted.append(article_id)
    return {"deletedIds": deleted, "count": len(deleted)}


# ---------------------------------------------------------------------------
# Recipes — authored by `chef`, reviewed/published by `recipes.approve`/`.publish`
# ---------------------------------------------------------------------------


class RecipeCreateRequest(_CamelModel):
    title: str = Field(min_length=3, max_length=180)
    slug: str | None = Field(default=None, max_length=96)
    excerpt: str | None = Field(default=None, max_length=300)


class RecipeIngredientInput(_CamelModel):
    label: str = Field(min_length=1, max_length=200)
    quantity_text: str | None = Field(default=None, max_length=80)
    product_id: str | None = Field(default=None, max_length=64)


class RecipeUpdateRequest(_CamelModel):
    title: str | None = Field(default=None, min_length=3, max_length=180)
    slug: str | None = Field(default=None, max_length=96)
    excerpt: str | None = Field(default=None, max_length=300)
    prep_minutes: int | None = Field(default=None, ge=0, le=600)
    cook_minutes: int | None = Field(default=None, ge=0, le=600)
    servings: int | None = Field(default=None, ge=1, le=50)
    hero_media_id: str | None = Field(default=None, max_length=64)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)
    chef_user_id: str | None = Field(default=None, max_length=64)
    dietary_tags: list[str] | None = Field(default=None, max_length=12)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)
    canonical_url: str | None = Field(default=None, max_length=300)
    indexing_policy: str | None = Field(default=None, max_length=16)
    blocks: list[dict[str, Any]] | None = Field(default=None, max_length=40)
    steps: list[str] | None = Field(default=None, max_length=30)
    ingredients: list[RecipeIngredientInput] | None = Field(default=None, max_length=40)

    @field_validator("hero_image_url")
    @classmethod
    def _safe_hero_image_url(cls, value: str | None) -> str | None:
        if value in (None, ""):
            return value
        return _validate_image_url(value)


def _recipe_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "slug": row["slug"],
        "status": row["status"],
        "chefName": row["chef_name"],
        "updatedAt": row["updated_at"],
        "publishedAt": row["published_at"],
        "hasDraftChanges": row["latest_version_number"] != row["published_version_number"],
    }


def _recipe_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "slug": row["slug"],
        "excerpt": row["excerpt"],
        "prepMinutes": row["prep_minutes"],
        "cookMinutes": row["cook_minutes"],
        "servings": row["servings"],
        "dietaryTags": row["dietary_tags"],
        "status": row["status"],
        "chefUserId": row["chef_user_id"],
        "heroImageUrl": row["hero_image_url"],
        "heroImageAlt": row["hero_image_alt"],
        "seoTitle": row["seo_title"],
        "seoDescription": row["seo_description"],
        "seoKeywords": row["seo_keywords"],
        "canonicalUrl": row["canonical_url"],
        "indexingPolicy": row["indexing_policy"],
        "updatedAt": row["updated_at"],
        "blocks": row["blocks"],
        "steps": row["steps"],
        "ingredients": [
            {
                "id": entry["id"],
                "label": entry["label"],
                "quantityText": entry["quantity_text"],
                "productId": entry["product_id"],
                "productSlug": entry["product_slug"],
            }
            for entry in row["ingredients"]
        ],
    }


@router.get("/recipes")
async def list_recipes_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    scope = None if principal.has("recipes.approve") else principal.user_id
    rows = await RecipeRepository(db).list_admin(
        chef_user_id=scope, limit=limit, offset=offset, search=search
    )
    return {"items": [_recipe_summary(row) for row in rows], "limit": limit, "offset": offset}


@router.post("/recipes")
async def create_recipe_endpoint(
    payload: RecipeCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.create"))],
) -> Any:
    return await recipe_service.create_recipe(
        db,
        principal,
        _request_id(request),
        title=payload.title,
        slug=payload.slug,
        excerpt=payload.excerpt,
    )


@router.get("/recipes/{recipe_id}")
async def get_recipe_endpoint(
    recipe_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.view"))],
) -> Any:
    row = await RecipeRepository(db).get_admin_detail(recipe_id)
    if row is None:
        raise NotFoundError("Recipe not found.")
    recipe_service.assert_owns_or_reviews(row, principal)
    return _recipe_detail(row)


@router.patch("/recipes/{recipe_id}")
async def update_recipe_endpoint(
    recipe_id: str,
    payload: RecipeUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.edit"))],
) -> Any:
    fields = payload.model_dump(exclude_unset=True)
    await recipe_service.update_recipe(
        db, principal, _request_id(request), recipe_id, fields=fields
    )
    row = await RecipeRepository(db).get_admin_detail(recipe_id)
    if row is None:
        raise NotFoundError("Recipe not found.")
    return _recipe_detail(row)


@router.post("/recipes/{recipe_id}/submit-for-review")
async def submit_recipe_endpoint(
    recipe_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.edit"))],
) -> Any:
    return await recipe_service.submit_recipe(db, principal, _request_id(request), recipe_id)


@router.post("/recipes/{recipe_id}/approve")
async def approve_recipe_endpoint(
    recipe_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.approve"))],
) -> Any:
    return await recipe_service.approve_recipe(db, principal, _request_id(request), recipe_id)


@router.post("/recipes/{recipe_id}/request-changes")
async def request_recipe_changes_endpoint(
    recipe_id: str,
    payload: ChangesRequestedRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.approve"))],
) -> Any:
    return await recipe_service.request_recipe_changes(
        db, principal, _request_id(request), recipe_id, payload.note
    )


@router.post("/recipes/{recipe_id}/publish")
async def publish_recipe_endpoint(
    recipe_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.publish"))],
) -> Any:
    return await publish_recipe(db, recipe_id, principal, _request_id(request))


@router.post("/recipes/{recipe_id}/unpublish")
async def unpublish_recipe_endpoint(
    recipe_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.publish"))],
) -> Any:
    return await recipe_service.unpublish_recipe(db, principal, _request_id(request), recipe_id)


class RecipeBulkDeleteRequest(_CamelModel):
    recipe_ids: list[str] = Field(min_length=1, max_length=100)


@router.delete("/recipes/{recipe_id}")
async def delete_recipe_endpoint(
    recipe_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.edit"))],
) -> Any:
    return await recipe_service.archive_recipe(db, principal, _request_id(request), recipe_id)


@router.post("/recipes/bulk-delete")
async def bulk_delete_recipes_endpoint(
    payload: RecipeBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("recipes.edit"))],
) -> Any:
    deleted: list[str] = []
    for recipe_id in payload.recipe_ids:
        await recipe_service.archive_recipe(db, principal, _request_id(request), recipe_id)
        deleted.append(recipe_id)
    return {"deletedIds": deleted, "count": len(deleted)}


# ---------------------------------------------------------------------------
# Return requests (RMA) — customers file from the storefront; staff review here
# ---------------------------------------------------------------------------


class ReturnDecisionRequest(_CamelModel):
    decision: str = Field(min_length=1, max_length=20)


class ReturnResolveRequest(_CamelModel):
    resolution_type: str = Field(min_length=1, max_length=20)
    resolution_amount_minor: int | None = Field(default=None, ge=0)
    resolution_notes: str | None = Field(default=None, max_length=1000)


def _return_request_admin_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "orderReference": row["public_reference"],
        "customerName": row["customer_name"],
        "reasonCode": row["reason_code"],
        "status": row["status"],
        "requestedRefundAmountMinor": row["requested_refund_amount_minor"],
        "resolutionType": row["resolution_type"],
        "resolutionAmountMinor": row["resolution_amount_minor"],
        "requestedAt": row["requested_at"],
        "resolvedAt": row["resolved_at"],
    }


@router.get("/returns")
async def list_returns_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("returns.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await ReturnRequestRepository(db).list_admin(
        status=status, limit=limit, offset=offset, search=search, farm_id=principal.farm_id
    )
    return {
        "items": [_return_request_admin_row(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/returns/{return_id}")
async def get_return_endpoint(
    return_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("returns.view"))],
) -> Any:
    row = await ReturnRequestRepository(db).get_admin_detail(return_id, farm_id=principal.farm_id)
    if row is None:
        raise NotFoundError("Return request not found.")
    return {
        "id": row["id"],
        "orderReference": row["public_reference"],
        "orderTotalMinor": row["order_total_minor"],
        "currencyCode": row["currency_code"],
        "customerName": row["customer_name"],
        "productName": row["product_name"],
        "variantName": row["variant_name"],
        "reasonCode": row["reason_code"],
        "description": row["description"],
        "evidenceMediaIds": json.loads(row["evidence_media_ids_json"] or "[]"),
        "status": row["status"],
        "requestedRefundAmountMinor": row["requested_refund_amount_minor"],
        "resolutionType": row["resolution_type"],
        "resolutionAmountMinor": row["resolution_amount_minor"],
        "resolutionNotes": row["resolution_notes"],
        "requestedAt": row["requested_at"],
        "resolvedAt": row["resolved_at"],
    }


@router.post("/returns/{return_id}/decide")
async def decide_return_endpoint(
    return_id: str,
    payload: ReturnDecisionRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("returns.manage"))],
) -> Any:
    return await decide_return_request(
        db, principal, _request_id(request), return_id, decision=payload.decision
    )


@router.post("/returns/{return_id}/resolve")
async def resolve_return_endpoint(
    return_id: str,
    payload: ReturnResolveRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("returns.manage"))],
) -> Any:
    return await resolve_return_request(
        db,
        principal,
        _request_id(request),
        return_id,
        resolution_type=payload.resolution_type,
        resolution_amount_minor=payload.resolution_amount_minor,
        resolution_notes=payload.resolution_notes,
    )


# ---------------------------------------------------------------------------
# Community blog/recipe submissions — customer-submitted, staff-reviewed;
# approval promotes straight into articles/recipes as published (see
# services.submissions for why there is no separate publish step here).
# ---------------------------------------------------------------------------


class SubmissionDecisionRequest(_CamelModel):
    decision: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


def _submission_admin_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "contentType": row["content_type"],
        "status": row["status"],
        "title": row["title"],
        "contactName": row["contact_name"],
        "contactEmail": row["contact_email"],
        "contactPhone": row["contact_phone"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
        "reviewedAt": row["reviewed_at"],
    }


def _submission_admin_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_submission_admin_summary(row),
        "excerpt": row["excerpt"],
        "body": row["body"],
        "prepMinutes": row["prep_minutes"],
        "cookMinutes": row["cook_minutes"],
        "servings": row["servings"],
        "dietaryTags": json.loads(row["dietary_tags_json"]) if row["dietary_tags_json"] else [],
        "ingredients": json.loads(row["ingredients_json"]) if row["ingredients_json"] else [],
        "steps": json.loads(row["steps_json"]) if row["steps_json"] else [],
        "reviewerNotes": row["reviewer_notes"],
        "publishedArticleId": row["published_article_id"],
        "publishedRecipeId": row["published_recipe_id"],
    }


@router.get("/submissions")
async def list_submissions_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("submissions.view"))],
    content_type: Annotated[str | None, Query(max_length=16)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await ContentSubmissionRepository(db).list_admin(
        content_type=content_type, status=status, limit=limit, offset=offset, search=search
    )
    return {
        "items": [_submission_admin_summary(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/submissions/pending-count")
async def submissions_pending_count_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("submissions.view"))],
) -> Any:
    return {"count": await ContentSubmissionRepository(db).count_pending()}


@router.get("/submissions/{submission_id}")
async def get_submission_endpoint(
    submission_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("submissions.view"))],
) -> Any:
    row = await ContentSubmissionRepository(db).get_admin_detail(submission_id)
    if row is None:
        raise NotFoundError("Submission not found.")
    return _submission_admin_detail(row)


@router.post("/submissions/{submission_id}/decide")
async def decide_submission_endpoint(
    submission_id: str,
    payload: SubmissionDecisionRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("submissions.review"))],
) -> Any:
    settings = get_settings()
    result = await submission_service.decide_submission(
        db,
        principal,
        _request_id(request),
        submission_id,
        decision=payload.decision,
        note=payload.note,
    )
    row = await ContentSubmissionRepository(db).get_admin_detail(submission_id)
    if row is not None:
        kind_path = "blog" if row["content_type"] == "article" else "recipes"
        if payload.decision == "approved" and result.get("slug"):
            live_url = f"{settings.public_storefront_url}/{kind_path}/{result['slug']}"
            await enqueue_email(
                db,
                dedupe_key=f"submission:{submission_id}:approved",
                to=row["contact_email"],
                subject=f"Your {'blog post' if row['content_type'] == 'article' else 'recipe'} "
                "is live on True Grit",
                body=f'Hi {row["contact_name"]}, your submission "{row["title"]}" has been '
                f"approved and is now live: {live_url}",
                html_body=render_submission_approved(
                    row["contact_name"], row["content_type"], row["title"], live_url
                ),
                aggregate_type="content_submission",
                aggregate_id=submission_id,
            )
        elif payload.decision == "changes_requested" and payload.note:
            edit_url = f"{settings.public_storefront_url}/account/submissions/{submission_id}/edit"
            await enqueue_email(
                db,
                dedupe_key=f"submission:{submission_id}:changes:{payload.note}",
                to=row["contact_email"],
                subject=f"Changes requested on your "
                f"{'blog post' if row['content_type'] == 'article' else 'recipe'} submission",
                body=f'Hi {row["contact_name"]}, changes were requested on "{row["title"]}": '
                f"{payload.note}\nEdit and resubmit: {edit_url}",
                html_body=render_submission_changes_requested(
                    row["contact_name"], row["content_type"], row["title"], payload.note, edit_url
                ),
                aggregate_type="content_submission",
                aggregate_id=submission_id,
            )
        elif payload.decision == "rejected" and payload.note:
            await enqueue_email(
                db,
                dedupe_key=f"submission:{submission_id}:rejected:{payload.note}",
                to=row["contact_email"],
                subject=f"About your "
                f"{'blog post' if row['content_type'] == 'article' else 'recipe'} submission",
                body=f"Hi {row['contact_name']}, after review we will not be publishing "
                f'"{row["title"]}": {payload.note}',
                html_body=render_submission_rejected(
                    row["contact_name"], row["content_type"], row["title"], payload.note
                ),
                aggregate_type="content_submission",
                aggregate_id=submission_id,
            )
    return result


# ---------------------------------------------------------------------------
# Farm partnership applications — growers apply from the storefront, staff
# triage here. Unlike submissions above, approval records a decision and emails
# the applicant; it does NOT create a `farms` row (see migration 0044).
# ---------------------------------------------------------------------------


class FarmRequestDecisionRequest(_CamelModel):
    decision: str = Field(min_length=1, max_length=20)
    note: str | None = Field(default=None, max_length=2000)


class FarmRequestLinkRequest(_CamelModel):
    farm_id: str = Field(min_length=1, max_length=64)


def _farm_request_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "status": row["status"],
        "farmName": row["farm_name"],
        "region": row["region"],
        "state": row["state"],
        "city": row["city"],
        "contactName": row["contact_name"],
        "contactEmail": row["contact_email"],
        "contactPhone": row["contact_phone"],
        "createdAt": row["created_at"],
        "reviewedAt": row["reviewed_at"],
        "linkedFarmId": row["linked_farm_id"],
    }


def _farm_request_detail(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **_farm_request_summary(row),
        "pincode": row["pincode"],
        "establishedYear": row["established_year"],
        "landAreaAcres": row["land_area_acres"],
        "certification": row["certification"],
        "primaryProduce": row["primary_produce"],
        "farmingPractices": row["farming_practices"],
        "websiteUrl": row["website_url"],
        "message": row["message"],
        "reviewerNotes": row["reviewer_notes"],
        "reviewerName": row["reviewer_name"],
        "submitterName": row["submitter_name"],
        "linkedFarmName": row["linked_farm_name"],
        "updatedAt": row["updated_at"],
    }


def _assert_main_admin(principal: Principal) -> None:
    """Farm-owner sub-admins are scoped to their own farm; deciding who else
    joins the marketplace is not theirs to see. Mirrors the same guard on the
    contact inbox."""
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can review farm applications.")


@router.get("/farm-requests")
async def list_farm_requests_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    _assert_main_admin(principal)
    repository = FarmPartnershipRequestRepository(db)
    rows = await repository.list_admin(status=status, search=search, limit=limit, offset=offset)
    return {
        "items": [_farm_request_summary(row) for row in rows],
        "total": await repository.count(status=status, search=search),
        "limit": limit,
        "offset": offset,
    }


@router.get("/farm-requests/open-count")
async def farm_requests_open_count_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.view"))],
) -> Any:
    _assert_main_admin(principal)
    return {"count": await FarmPartnershipRequestRepository(db).count_open()}


@router.get("/farm-requests/{entry_id}")
async def get_farm_request_endpoint(
    entry_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.view"))],
) -> Any:
    _assert_main_admin(principal)
    row = await FarmPartnershipRequestRepository(db).get(entry_id)
    if row is None:
        raise NotFoundError("Farm application not found.")
    return _farm_request_detail(row)


@router.post("/farm-requests/{entry_id}/decide")
async def decide_farm_request_endpoint(
    entry_id: str,
    payload: FarmRequestDecisionRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.review"))],
) -> Any:
    _assert_main_admin(principal)
    result = await farm_partnership_service.decide_request(
        db,
        principal,
        _request_id(request),
        entry_id,
        decision=payload.decision,
        note=payload.note,
    )

    # Only the two terminal decisions are worth an email. 'under_review' and
    # 'contacted' are internal pipeline states — telling an applicant "someone
    # opened your form" is noise, and telling them "we called you" when the call
    # is the notification is worse.
    recipient = result["contactEmail"]
    if recipient is not None and payload.decision in ("approved", "rejected"):
        note = result["note"] or ""
        if payload.decision == "approved":
            await enqueue_email(
                db,
                dedupe_key=f"farm-application:{entry_id}:approved",
                to=recipient,
                subject="Your farm application has been accepted",
                body=(
                    f"Hi {result['contactName']}, we would like to work with"
                    f" {result['farmName']}. Our sourcing team will be in touch."
                    + (f"\n\n{note}" if note else "")
                ),
                html_body=render_farm_partnership_approved(
                    result["contactName"], result["farmName"], note
                ),
                aggregate_type="farm_partnership_request",
                aggregate_id=entry_id,
            )
        else:
            await enqueue_email(
                db,
                dedupe_key=f"farm-application:{entry_id}:rejected:{note}",
                to=recipient,
                subject="About your farm application",
                body=(
                    f"Hi {result['contactName']}, after reading your application for"
                    f" {result['farmName']} we are not able to take it further right"
                    f" now.\n\n{note}"
                ),
                html_body=render_farm_partnership_rejected(
                    result["contactName"], result["farmName"], note
                ),
                aggregate_type="farm_partnership_request",
                aggregate_id=entry_id,
            )
    return {"id": result["id"], "status": result["status"]}


@router.post("/farm-requests/{entry_id}/link-farm")
async def link_farm_request_endpoint(
    entry_id: str,
    payload: FarmRequestLinkRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.review"))],
) -> Any:
    _assert_main_admin(principal)
    return await farm_partnership_service.attach_farm(
        db, principal, _request_id(request), entry_id, payload.farm_id
    )


@router.delete("/farm-requests/{entry_id}")
async def delete_farm_request_endpoint(
    entry_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("farm_requests.review"))],
) -> Any:
    _assert_main_admin(principal)
    return await farm_partnership_service.delete_request(
        db, principal, _request_id(request), entry_id
    )


# ---------------------------------------------------------------------------
# Reader comments on blog posts and recipes. Policed with `discussions.*`
# rather than a parallel permission — see migration 0043.
# ---------------------------------------------------------------------------


class ContentCommentModerationRequest(_CamelModel):
    action: str = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=500)


@router.get("/content-comments")
async def list_content_comments_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("discussions.view"))],
    content_type: Annotated[str | None, Query(max_length=16)] = None,
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    repository = ContentCommentRepository(db)
    rows = await repository.list_admin(
        content_type=content_type, status=status, search=search, limit=limit, offset=offset
    )
    return {
        "items": [
            {
                "id": row["id"],
                "contentType": row["content_type"],
                "body": row["body"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "moderatedAt": row["moderated_at"],
                "moderationReason": row["moderation_reason"],
                "authorName": row["author_name"],
                "authorEmail": display_contact(row["author_email"], None),
                "parentTitle": row["parent_title"],
                "parentSlug": row["parent_slug"],
            }
            for row in rows
        ],
        "total": await repository.count(content_type=content_type, status=status, search=search),
        "enabled": await content_comment_service.is_enabled(db),
        "limit": limit,
        "offset": offset,
    }


@router.post("/content-comments/{comment_id}/moderate")
async def moderate_content_comment_endpoint(
    comment_id: str,
    payload: ContentCommentModerationRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await content_comment_service.moderate_comment(
        db,
        principal,
        _request_id(request),
        comment_id,
        action=payload.action,
        reason=payload.reason,
    )


@router.delete("/content-comments/{comment_id}")
async def delete_content_comment_endpoint(
    comment_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await content_comment_service.delete_comment(
        db, principal, _request_id(request), comment_id
    )


# ---------------------------------------------------------------------------
# Product reviews and ratings (migration 0005, extended by 0057). Policed with
# its own `reviews.*` pair rather than reusing `discussions.*` -- reviews are
# commerce-adjacent (tied to orders and products), so Order Manager / Product
# Manager territory, not the content-moderation roles.
# ---------------------------------------------------------------------------


class ReviewModerationRequest(_CamelModel):
    action: str = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=500)


class ReviewEditRequest(_CamelModel):
    rating: int | None = Field(default=None, ge=1, le=5)
    title: str | None = Field(default=None, max_length=120)
    body: str | None = Field(default=None, min_length=10, max_length=4000)


def _admin_review_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "rating": row["rating"],
        "title": row["title"],
        "body": row["body"],
        "status": row["status"],
        "authorName": row["author_name"],
        "authorEmail": display_contact(row["author_email"], None),
        "createdAt": row["created_at"],
        "moderatedAt": row["moderated_at"],
        "moderationReason": row["moderation_reason"],
    }


@router.get("/reviews")
async def list_reviews_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("reviews.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    rating: Annotated[int | None, Query(ge=1, le=5)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    repository = ReviewRepository(db)
    rows = await repository.list_admin(
        status=status,
        rating=rating,
        search=search,
        limit=limit,
        offset=offset,
        farm_id=principal.farm_id,
    )
    return {
        "items": [_admin_review_payload(row) for row in rows],
        "total": await repository.count_admin(
            status=status, rating=rating, search=search, farm_id=principal.farm_id
        ),
        "pending": await repository.count_pending(),
        "limit": limit,
        "offset": offset,
    }


@router.patch("/reviews/{review_id}")
async def edit_review_endpoint(
    review_id: str,
    payload: ReviewEditRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("reviews.moderate"))],
) -> Any:
    fields = payload.model_dump(exclude_unset=True)
    return await review_service.edit_review(db, principal, _request_id(request), review_id, fields)


@router.post("/reviews/{review_id}/moderate")
async def moderate_review_endpoint(
    review_id: str,
    payload: ReviewModerationRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("reviews.moderate"))],
) -> Any:
    return await review_service.moderate_review(
        db,
        principal,
        _request_id(request),
        review_id,
        action=payload.action,
        reason=payload.reason,
    )


@router.delete("/reviews/{review_id}")
async def delete_review_endpoint(
    review_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("reviews.moderate"))],
) -> Any:
    return await review_service.delete_review(db, principal, _request_id(request), review_id)


# ---------------------------------------------------------------------------
# Community discussions — moderation. Discussions/comments are created from
# the storefront (api.community); staff here can hide, restore, archive or
# permanently delete any thread or comment, and set the minimum account age
# required to start a new discussion.
# ---------------------------------------------------------------------------


class DiscussionModerationRequest(_CamelModel):
    action: str = Field(min_length=1, max_length=20)
    reason: str | None = Field(default=None, max_length=500)


class CommunitySettingsUpdateRequest(_CamelModel):
    min_account_age_months: int = Field(ge=0, le=120)


class StorefrontSettingsUpdateRequest(_CamelModel):
    """Runtime switches for sign-in methods, taking payments, and the blog banner.

    Every field is optional and only the ones actually sent are written
    (`exclude_unset` in the handler), so a PATCH that flips one switch cannot
    silently overwrite the rest with whatever the client last rendered.
    """

    google_sign_in: bool | None = None
    facebook_sign_in: bool | None = None
    phone_otp_sign_in: bool | None = None
    password_sign_in: bool | None = None
    registration: bool | None = None
    payments: bool | None = None
    promotions: bool | None = None
    recommendations: bool | None = None
    subscriptions: bool | None = None
    diet_cert_filters: bool | None = None
    gift_cards: bool | None = None
    payments_disabled_notice: str | None = Field(default=None, max_length=600)
    blog_banner_image_url: str | None = Field(default=None, max_length=1000)
    blog_banner_image_alt: str | None = Field(default=None, max_length=200)
    farms_banner_image_url: str | None = Field(default=None, max_length=1000)
    farms_banner_image_alt: str | None = Field(default=None, max_length=200)


def _discussion_admin_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "status": row["status"],
        "authorName": row["author_name"],
        "commentCount": row["comment_count"],
        "lastActivityAt": row["last_activity_at"],
        "createdAt": row["created_at"],
    }


@router.get("/discussions")
async def list_discussions_admin_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("discussions.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await DiscussionRepository(db).list_admin(
        status=status, limit=limit, offset=offset, search=search
    )
    return {
        "items": [_discussion_admin_summary(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.get("/discussions/{discussion_id}")
async def get_discussion_admin_endpoint(
    discussion_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("discussions.view"))],
) -> Any:
    repo = DiscussionRepository(db)
    row = await repo.get_admin_detail(discussion_id)
    if row is None:
        raise NotFoundError("Discussion not found.")
    comments = await repo.list_comments_admin(discussion_id)
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "status": row["status"],
        "authorName": row["author_name"],
        "authorEmail": row["author_email"],
        "commentCount": row["comment_count"],
        "lastActivityAt": row["last_activity_at"],
        "createdAt": row["created_at"],
        "moderationReason": row["moderation_reason"],
        "comments": [
            {
                "id": comment["id"],
                "body": comment["body"],
                "status": comment["status"],
                "authorName": comment["author_name"],
                "createdAt": comment["created_at"],
                "moderationReason": comment["moderation_reason"],
            }
            for comment in comments
        ],
    }


@router.post("/discussions/{discussion_id}/moderate")
async def moderate_discussion_endpoint(
    discussion_id: str,
    payload: DiscussionModerationRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await discussion_service.moderate_discussion(
        db,
        principal,
        _request_id(request),
        discussion_id,
        action=payload.action,
        reason=payload.reason,
    )


@router.delete("/discussions/{discussion_id}")
async def delete_discussion_endpoint(
    discussion_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await discussion_service.delete_discussion(
        db, principal, _request_id(request), discussion_id
    )


class DiscussionBulkDeleteRequest(_CamelModel):
    discussion_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/discussions/bulk-delete")
async def bulk_delete_discussions_endpoint(
    payload: DiscussionBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    deleted: list[str] = []
    for discussion_id in payload.discussion_ids:
        await discussion_service.delete_discussion(
            db, principal, _request_id(request), discussion_id
        )
        deleted.append(discussion_id)
    return {"deletedIds": deleted, "count": len(deleted)}


@router.post("/discussions/comments/{comment_id}/moderate")
async def moderate_comment_endpoint(
    comment_id: str,
    payload: DiscussionModerationRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await discussion_service.moderate_comment(
        db,
        principal,
        _request_id(request),
        comment_id,
        action=payload.action,
        reason=payload.reason,
    )


@router.delete("/discussions/comments/{comment_id}")
async def delete_comment_endpoint(
    comment_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("discussions.moderate"))],
) -> Any:
    return await discussion_service.delete_comment(db, principal, _request_id(request), comment_id)


@router.get("/community-settings")
async def get_community_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.community"))],
) -> Any:
    return {"minAccountAgeMonths": await discussion_service.get_min_account_age_months(db)}


@router.patch("/community-settings")
async def update_community_settings_endpoint(
    payload: CommunitySettingsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.community"))],
) -> Any:
    return await discussion_service.set_min_account_age_months(
        db, principal, _request_id(request), payload.min_account_age_months
    )


# ---------------------------------------------------------------------------
# Storefront feature switches — sign-in methods, taking payments, blog banner.
#
# Gated on settings.view/settings.edit, the same pair that guards Site Control:
# these decide whether customers can sign in or spend money, so they belong with
# the owner, not with everyone who can edit a product.
# ---------------------------------------------------------------------------


def _storefront_settings_response(
    stored: Any,
    effective: Any,
) -> dict[str, Any]:
    """Both the switches as set and the state they actually resolve to.

    The console needs both: a checkbox has to show what the operator chose,
    while the warning next to it has to say when that choice is inert because
    the deployment has no Google client id, no SMS key, or no gateway.
    """
    return {
        "settings": stored.to_camel_dict(),
        "effective": {
            "googleSignIn": effective.google_sign_in,
            "facebookSignIn": effective.facebook_sign_in,
            "phoneOtpSignIn": effective.phone_otp_sign_in,
            "passwordSignIn": effective.password_sign_in,
            "registration": effective.registration,
            "payments": effective.payments,
            "promotions": effective.promotions,
            "recommendations": effective.recommendations,
            "subscriptions": effective.subscriptions,
            "dietCertFilters": effective.diet_cert_filters,
            "giftCards": effective.gift_cards,
            "anySignInAvailable": effective.any_sign_in_available,
        },
    }


@router.get("/storefront-settings")
async def get_storefront_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    settings = get_settings()
    stored = await load_storefront_settings(db)
    return _storefront_settings_response(stored, await load_public_settings(db, settings))


@router.patch("/storefront-settings")
async def update_storefront_settings_endpoint(
    payload: StorefrontSettingsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    settings = get_settings()
    stored = await update_storefront_settings(
        db,
        principal,
        _request_id(request),
        updates=payload.model_dump(exclude_unset=True, exclude_none=True),
    )
    return _storefront_settings_response(stored, await load_public_settings(db, settings))


# ---------------------------------------------------------------------------
# Delivery charges. Stored settings (migration-free -- `app_settings` already
# exists), not hardcoded constants, so a seasonal fee change or a raised
# free-delivery bar is an admin edit, not a deploy.
# ---------------------------------------------------------------------------


class DeliverySettingsUpdateRequest(_CamelModel):
    fee_minor: int = Field(ge=0)
    free_threshold_minor: int = Field(ge=0)


@router.get("/delivery-settings")
async def get_delivery_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    settings = await load_delivery_settings(db)
    return {"feeMinor": settings.fee_minor, "freeThresholdMinor": settings.free_threshold_minor}


@router.patch("/delivery-settings")
async def update_delivery_settings_endpoint(
    payload: DeliverySettingsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    settings = await set_delivery_settings(
        db,
        principal,
        _request_id(request),
        fee_minor=payload.fee_minor,
        free_threshold_minor=payload.free_threshold_minor,
    )
    return {"feeMinor": settings.fee_minor, "freeThresholdMinor": settings.free_threshold_minor}


# ---------------------------------------------------------------------------
# Curated list size -- the shared cap for Fresh Favourites, Featured
# Categories (Homepage Settings) and Highlights (Site Control): one setting
# rather than three, since all three are the same shape of feature (pick up
# to N items, in order). Stored, not hardcoded, so raising it past the
# shipped twelve is an admin edit.
# ---------------------------------------------------------------------------


class CuratedSettingsUpdateRequest(_CamelModel):
    max_items: int = Field(ge=1, le=50)


@router.get("/curated-settings")
async def get_curated_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"maxItems": await load_curated_max_items(db)}


@router.patch("/curated-settings")
async def update_curated_settings_endpoint(
    payload: CuratedSettingsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    value = await set_curated_max_items(
        db, principal, _request_id(request), value=payload.max_items
    )
    return {"maxItems": value}


# ---------------------------------------------------------------------------
# Coupons and promotions (migration 0005, extended by 0060). A promotion with
# no coupons is automatic; one or more coupons make it code-gated. The
# sitewide switch lives with the other storefront feature switches above
# (`commerce.promotions.enabled`, in `StorefrontSettingsUpdateRequest`) --
# these routes manage the campaigns and codes themselves.
# ---------------------------------------------------------------------------


class PromotionCreateRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=160)
    headline: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=400)
    status: str = Field(default="draft", max_length=20)
    priority: int = Field(default=0, ge=0, le=1000)
    starts_at: str | None = None
    ends_at: str | None = None
    stacking_policy: str = Field(default="exclusive", max_length=20)
    usage_limit_total: int | None = Field(default=None, ge=1)
    usage_limit_per_customer: int | None = Field(default=None, ge=1)
    min_subtotal_minor: int | None = Field(default=None, ge=0)
    action_type: str = Field(max_length=30)
    value_basis_points: int | None = Field(default=None, ge=0, le=10_000)
    amount_minor: int | None = Field(default=None, ge=0)
    maximum_discount_minor: int | None = Field(default=None, ge=0)


class PromotionUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    headline: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=400)
    status: str | None = Field(default=None, max_length=20)
    priority: int | None = Field(default=None, ge=0, le=1000)
    starts_at: str | None = None
    ends_at: str | None = None
    usage_limit_total: int | None = None
    usage_limit_per_customer: int | None = None


class CouponCreateRequest(_CamelModel):
    code: str = Field(min_length=1, max_length=32)


def _admin_promotion_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "status": row["status"],
        "priority": row["priority"],
        "startsAt": row["starts_at"],
        "endsAt": row["ends_at"],
        "stackingPolicy": row["stacking_policy"],
        "usageLimitTotal": row["usage_limit_total"],
        "usageLimitPerCustomer": row["usage_limit_per_customer"],
        "headline": row["headline"],
        "description": row["description"],
        "couponCount": row["coupon_count"],
        "redemptionCount": row["redemption_count"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


@router.get("/promotions")
async def list_promotions_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("promotions.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    repository = PromotionRepository(db)
    rows = await repository.list_admin(status=status, search=search, limit=limit, offset=offset)
    return {
        "items": [_admin_promotion_payload(row) for row in rows],
        "total": await repository.count_admin(status=status, search=search),
    }


@router.get("/promotions/{promotion_id}")
async def get_promotion_endpoint(
    promotion_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("promotions.view"))],
) -> Any:
    repository = PromotionRepository(db)
    promotion = await repository.get_by_id(promotion_id)
    if promotion is None:
        raise NotFoundError("Promotion not found.")
    rule = await repository.get_rule(promotion_id)
    action = await repository.get_action(promotion_id)
    coupons = await repository.list_coupons(promotion_id)
    payload = _admin_promotion_payload(
        {
            **promotion,
            "coupon_count": len(coupons),
            "redemption_count": sum(coupon["redemption_count"] for coupon in coupons),
        }
    )
    payload["rule"] = (
        {"minSubtotalMinor": json.loads(rule["rule_json"]).get("minSubtotalMinor")}
        if rule is not None
        else None
    )
    payload["action"] = (
        {
            "actionType": action["action_type"],
            "valueBasisPoints": action["value_basis_points"],
            "amountMinor": action["amount_minor"],
            "maximumDiscountMinor": action["maximum_discount_minor"],
        }
        if action is not None
        else None
    )
    payload["coupons"] = [
        {
            "id": coupon["id"],
            "code": coupon["code"],
            "active": bool(coupon["active"]),
            "redemptionCount": coupon["redemption_count"],
            "createdAt": coupon["created_at"],
        }
        for coupon in coupons
    ]
    return payload


@router.post("/promotions")
async def create_promotion_endpoint(
    payload: PromotionCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("promotions.manage"))],
) -> Any:
    return await promotion_service.create_promotion(
        db,
        principal,
        _request_id(request),
        name=payload.name,
        headline=payload.headline,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        stacking_policy=payload.stacking_policy,
        usage_limit_total=payload.usage_limit_total,
        usage_limit_per_customer=payload.usage_limit_per_customer,
        min_subtotal_minor=payload.min_subtotal_minor,
        action_type=payload.action_type,
        value_basis_points=payload.value_basis_points,
        amount_minor=payload.amount_minor,
        maximum_discount_minor=payload.maximum_discount_minor,
    )


@router.patch("/promotions/{promotion_id}")
async def update_promotion_endpoint(
    promotion_id: str,
    payload: PromotionUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("promotions.manage"))],
) -> Any:
    fields = payload.model_dump(exclude_unset=True)
    return await promotion_service.update_promotion(
        db, principal, _request_id(request), promotion_id, fields
    )


@router.delete("/promotions/{promotion_id}")
async def delete_promotion_endpoint(
    promotion_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("promotions.manage"))],
) -> Any:
    return await promotion_service.delete_promotion(
        db, principal, _request_id(request), promotion_id
    )


@router.post("/promotions/{promotion_id}/coupons")
async def create_coupon_endpoint(
    promotion_id: str,
    payload: CouponCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("promotions.manage"))],
) -> Any:
    return await promotion_service.create_coupon(
        db, principal, _request_id(request), promotion_id, code=payload.code
    )


@router.delete("/coupons/{coupon_id}")
async def delete_coupon_endpoint(
    coupon_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("promotions.manage"))],
) -> Any:
    return await promotion_service.delete_coupon(db, principal, _request_id(request), coupon_id)


# ---------------------------------------------------------------------------
# Gift cards (migration 0082): issuable, purchasable stored-value codes
# redeemable at checkout. Balance is derived from gift_card_redemptions, not
# stored -- see services.gift_cards' module docstring.
# ---------------------------------------------------------------------------


class GiftCardIssueRequest(_CamelModel):
    balance_minor: int = Field(ge=0)
    issued_to_email: str | None = Field(default=None, max_length=254)
    note: str | None = Field(default=None, max_length=300)
    expires_at: str | None = Field(default=None, max_length=32)
    code: str | None = Field(default=None, max_length=24)


def _gift_card_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "initialBalanceMinor": row["initial_balance_minor"],
        "balanceMinor": row["balance_minor"],
        "currencyCode": row["currency_code"],
        "status": row["status"],
        "issuedToEmail": row["issued_to_email"],
        "note": row["note"],
        "expiresAt": row["expires_at"],
        "createdAt": row["created_at"],
    }


@router.get("/gift-cards")
async def list_gift_cards_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("gift_cards.view"))],
    search: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    clean_search = f"%{search.strip()}%" if search and search.strip() else None
    where = " WHERE code LIKE ? OR issued_to_email LIKE ?" if clean_search else ""
    params: tuple[Any, ...] = (clean_search, clean_search) if clean_search else ()
    total_row = await db.fetch_one(
        f"SELECT COUNT(*) AS cnt FROM gift_cards{where}", params
    )
    rows = await db.fetch_all(
        f"""
        SELECT gc.*, gc.initial_balance_minor
          - COALESCE((SELECT SUM(amount_minor) FROM gift_card_redemptions
                      WHERE gift_card_id = gc.id), 0) AS balance_minor
        FROM gift_cards gc
        {where}
        ORDER BY gc.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (*params, limit, offset),
    )
    return {
        "items": [_gift_card_row(row) for row in rows],
        "total": int(total_row["cnt"]) if total_row else 0,
        "limit": limit,
        "offset": offset,
    }


@router.get("/gift-cards/{gift_card_id}")
async def get_gift_card_endpoint(
    gift_card_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("gift_cards.view"))],
) -> Any:
    row = await db.fetch_one(
        """
        SELECT gc.*, gc.initial_balance_minor
          - COALESCE((SELECT SUM(amount_minor) FROM gift_card_redemptions
                      WHERE gift_card_id = gc.id), 0) AS balance_minor
        FROM gift_cards gc WHERE gc.id = ?
        """,
        (gift_card_id,),
    )
    if row is None:
        raise NotFoundError("Gift card not found.")
    redemptions = await db.fetch_all(
        """
        SELECT r.id, r.order_id, o.public_reference, r.amount_minor, r.redeemed_at
        FROM gift_card_redemptions r
        JOIN orders o ON o.id = r.order_id
        WHERE r.gift_card_id = ?
        ORDER BY r.redeemed_at DESC
        """,
        (gift_card_id,),
    )
    detail = _gift_card_row(row)
    detail["redemptions"] = [
        {
            "orderId": entry["order_id"],
            "orderReference": entry["public_reference"],
            "amountMinor": entry["amount_minor"],
            "redeemedAt": entry["redeemed_at"],
        }
        for entry in redemptions
    ]
    return detail


@router.post("/gift-cards")
async def issue_gift_card_endpoint(
    payload: GiftCardIssueRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("gift_cards.manage"))],
) -> Any:
    return await gift_card_service.issue_gift_card(
        db,
        principal,
        _request_id(request),
        balance_minor=payload.balance_minor,
        issued_to_email=payload.issued_to_email,
        note=payload.note,
        expires_at=payload.expires_at,
        code=payload.code,
    )


@router.post("/gift-cards/{gift_card_id}/cancel")
async def cancel_gift_card_endpoint(
    gift_card_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("gift_cards.manage"))],
) -> Any:
    await gift_card_service.cancel_gift_card(db, principal, _request_id(request), gift_card_id)
    return {"id": gift_card_id, "status": "cancelled"}


# ---------------------------------------------------------------------------
# Bundles (migration 0062): curated sets of specific variants sold together at
# a flat advertised price. Discount enforcement lives in
# `services.checkout`/`services.bundles`, not here — these routes only manage
# the catalogue definition (which variants, what price).
# ---------------------------------------------------------------------------


class BundleCreateRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=140)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    status: str = Field(default="draft", max_length=20)
    bundle_price_minor: int = Field(ge=0)
    image_url: str | None = Field(default=None, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=200)


class BundleUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=140)
    slug: str | None = Field(default=None, max_length=140)
    description: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=20)
    bundle_price_minor: int | None = Field(default=None, ge=0)
    image_url: str | None = Field(default=None, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=200)


class BundleItemInput(_CamelModel):
    variant_id: str = Field(min_length=1, max_length=64)
    quantity: int = Field(ge=1, le=99)


class BundleItemsReplaceRequest(_CamelModel):
    items: list[BundleItemInput] = Field(min_length=1, max_length=12)


def _admin_bundle_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "description": row["description"],
        "status": row["status"],
        "bundlePriceMinor": row["bundle_price_minor"],
        "imageUrl": row["image_url"],
        "imageAlt": row["image_alt"],
        "itemCount": row.get("item_count", 0),
        "createdAt": row.get("created_at"),
        "updatedAt": row["updated_at"],
    }


def _admin_bundle_item_payload(row: dict[str, Any]) -> dict[str, Any]:
    unit_price = row["unit_price_minor"] or 0
    return {
        "id": row["id"],
        "variantId": row["variant_id"],
        "quantity": row["quantity"],
        "variantName": row["variant_name"],
        "sku": row["sku"],
        "productId": row["product_id"],
        "productName": row["product_name"],
        "productSlug": row["product_slug"],
        "imageUrl": row["image_url"],
        "unitPriceMinor": unit_price,
        "lineTotalMinor": unit_price * row["quantity"],
    }


@router.get("/bundles")
async def list_bundles_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    repository = BundleRepository(db)
    rows = await repository.list_admin(
        status=status, limit=limit, offset=offset, farm_id=principal.farm_id
    )
    return {
        "items": [_admin_bundle_payload(row) for row in rows],
        "total": await repository.count_admin(status=status, farm_id=principal.farm_id),
    }


@router.get("/bundles/{bundle_id}")
async def get_bundle_endpoint(
    bundle_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.view"))],
) -> Any:
    repository = BundleRepository(db)
    bundle = await repository.get_by_id(bundle_id)
    if bundle is None:
        raise NotFoundError("Bundle not found.")
    items = await repository.list_items(bundle_id)
    if principal.farm_id is not None and not any(
        item["product_farm_id"] == principal.farm_id for item in items
    ):
        raise NotFoundError("Bundle not found.")
    payload = _admin_bundle_payload({**bundle, "item_count": len(items)})
    payload["items"] = [_admin_bundle_item_payload(row) for row in items]
    return payload


@router.post("/bundles")
async def create_bundle_endpoint(
    payload: BundleCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.manage"))],
) -> Any:
    return await bundle_service.create_bundle(
        db,
        principal,
        _request_id(request),
        name=payload.name,
        slug=payload.slug,
        description=payload.description,
        status=payload.status,
        bundle_price_minor=payload.bundle_price_minor,
        image_url=payload.image_url,
        image_alt=payload.image_alt,
    )


@router.patch("/bundles/{bundle_id}")
async def update_bundle_endpoint(
    bundle_id: str,
    payload: BundleUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.manage"))],
) -> Any:
    return await bundle_service.update_bundle(
        db,
        principal,
        _request_id(request),
        bundle_id,
        payload.model_dump(exclude_unset=True, by_alias=False),
    )


@router.delete("/bundles/{bundle_id}")
async def delete_bundle_endpoint(
    bundle_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.manage"))],
) -> Any:
    await bundle_service.delete_bundle(db, principal, _request_id(request), bundle_id)
    return {"id": bundle_id, "deleted": True}


@router.put("/bundles/{bundle_id}/items")
async def replace_bundle_items_endpoint(
    bundle_id: str,
    payload: BundleItemsReplaceRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("bundles.manage"))],
) -> Any:
    await bundle_service.replace_bundle_items(
        db,
        principal,
        _request_id(request),
        bundle_id,
        [item.model_dump(by_alias=False) for item in payload.items],
    )
    repository = BundleRepository(db)
    items = await repository.list_items(bundle_id)
    return {"items": [_admin_bundle_item_payload(row) for row in items]}


# ---------------------------------------------------------------------------
# Subscriptions (migration 0064): "Subscribe & Save" recurring COD deliveries.
# Off by default (see the "subscriptions" switch on /storefront-settings) --
# these routes exist for support (view/pause/cancel a customer's subscription)
# and for the renewal job's admin-triggerable twin, not to create
# subscriptions on a customer's behalf: that only ever happens from the
# customer's own product-page action (see api/public.py).
# ---------------------------------------------------------------------------


class SubscriptionDiscountUpdateRequest(_CamelModel):
    percent: int = Field(ge=0, le=SUBSCRIPTION_DISCOUNT_PERCENT_HARD_LIMIT)


@router.get("/subscription-settings")
async def get_subscription_settings_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    return {"discountPercent": await load_subscription_discount_percent(db)}


@router.patch("/subscription-settings")
async def update_subscription_settings_endpoint(
    payload: SubscriptionDiscountUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    value = await set_subscription_discount_percent(
        db, principal, _request_id(request), value=payload.percent
    )
    return {"discountPercent": value}


@router.get("/subscriptions")
async def list_subscriptions_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.view"))],
    status: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    items, total = await subscription_service.list_admin_subscriptions(
        db, limit=limit, offset=offset, status=status, farm_id=principal.farm_id
    )
    return {"items": items, "total": total}


@router.get("/subscriptions/{subscription_id}")
async def get_subscription_admin_endpoint(
    subscription_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.view"))],
) -> Any:
    row = await SubscriptionRepository(db).get_by_id(subscription_id)
    if row is None or (principal.farm_id is not None and row["farm_id"] != principal.farm_id):
        raise NotFoundError("Subscription not found.")
    return subscription_service.serialize_subscription(row)


@router.post("/subscriptions/{subscription_id}/pause")
async def pause_subscription_admin_endpoint(
    subscription_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.manage"))],
) -> Any:
    return await subscription_service.pause_subscription(
        db, principal, _request_id(request), subscription_id
    )


@router.post("/subscriptions/{subscription_id}/resume")
async def resume_subscription_admin_endpoint(
    subscription_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.manage"))],
) -> Any:
    return await subscription_service.resume_subscription(
        db, principal, _request_id(request), subscription_id
    )


@router.post("/subscriptions/{subscription_id}/cancel")
async def cancel_subscription_admin_endpoint(
    subscription_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.manage"))],
) -> Any:
    return await subscription_service.cancel_subscription(
        db, principal, _request_id(request), subscription_id
    )


@router.post("/subscriptions/run-renewals")
async def run_subscription_renewals_endpoint(
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("subscriptions.manage"))],
) -> Any:
    """Runs the identical renewal batch the Worker's `scheduled` cron trigger
    runs (see worker.py) -- a manual lever for verifying the feature works
    before relying on the cron, and a fallback while the Workers Free plan's
    cron reliability is unproven. Safe to click twice: every renewal order is
    idempotency-keyed per subscription per due-date (services/subscriptions.py),
    so a subscription already renewed today is simply not due again.
    """
    return await subscription_service.run_due_renewals(
        db, _request_id(request), triggered_by=principal.user_id
    )


# ---------------------------------------------------------------------------
# Owner reports console — curated, parameterized, read-only queries only
# ---------------------------------------------------------------------------


class ReportRunRequest(_CamelModel):
    filters: dict[str, str] = Field(default_factory=dict)


@router.get("/reports")
async def list_reports_endpoint(
    _principal: Annotated[Principal, Depends(require_permission("reports.query"))],
) -> Any:
    return {"items": list_reports()}


@router.post("/reports/{report_id}/run")
async def run_report_endpoint(
    report_id: str,
    payload: ReportRunRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("reports.query"))],
) -> Any:
    result = await run_report(db, report_id, payload.filters)
    await db.execute(
        "INSERT INTO audit_logs"
        " (id, actor_user_id, action, entity_type, entity_id,"
        "  before_summary_json, after_summary_json, request_id, source, created_at)"
        " VALUES (?, ?, 'report.executed', 'report', ?, NULL, ?, ?, 'admin', ?)",
        (
            new_id("aud"),
            principal.user_id,
            report_id,
            json.dumps({"filters": payload.filters, "rows": len(result["rows"])}),
            _request_id(request),
            utc_now_iso(),
        ),
    )
    return result


# ---------------------------------------------------------------------------
# Analytics (migration 0065): a visual dashboard over a date range -- revenue,
# orders, top products, order-status mix -- computed live, never a stored
# rollup. Distinct from Owner Reports above: that is a data-export tool
# gated to the owner; this is "how is the store doing", visible to Admin and
# Manager too (see the WHY note in the migration).
# ---------------------------------------------------------------------------


@router.get("/analytics/overview")
async def analytics_overview_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("analytics.view"))],
    from_date: Annotated[str | None, Query(alias="from", max_length=10)] = None,
    to_date: Annotated[str | None, Query(alias="to", max_length=10)] = None,
) -> Any:
    return await analytics_service.load_overview(db, from_date=from_date, to_date=to_date)


@router.get("/archive")
async def list_archive_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    if not _can_view_archive(principal):
        raise PermissionDeniedError()

    # Results are unioned across four entity tables, then sorted together, so
    # each per-table fetch must cover the whole page window (offset + limit)
    # rather than just `limit` — otherwise a later page could drop rows that
    # only look "later" because another kind's rows sorted ahead of them.
    fetch_cap = min(offset + limit, 100)
    like = f"%{search}%" if search else None

    items: list[dict[str, Any]] = []
    if principal.has("products.view"):
        product_rows = await db.fetch_all(
            """
            SELECT p.id, p.name, p.slug, p.status, p.archived_at, p.updated_at,
                   u.display_name AS updated_by,
                   COALESCE(f.name, b.name, '') AS detail
            FROM products p
            LEFT JOIN farms f ON f.id = p.farm_id
            LEFT JOIN brands b ON b.id = p.brand_id
            LEFT JOIN users u ON u.id = p.updated_by
            WHERE (p.archived_at IS NOT NULL OR p.status = 'archived')
              AND (? IS NULL OR p.farm_id = ?)
              AND (? IS NULL OR p.name LIKE ? OR p.slug LIKE ?)
            ORDER BY COALESCE(p.archived_at, p.updated_at) DESC, p.name
            LIMIT ?
            """,
            (principal.farm_id, principal.farm_id, like, like, like, fetch_cap),
        )
        items.extend(_archive_row("product", row) for row in product_rows)

    if principal.farm_id is None and principal.has("categories.view"):
        category_rows = await db.fetch_all(
            """
            SELECT c.id, c.name, c.slug, c.status, c.archived_at, c.updated_at,
                   u.display_name AS updated_by,
                   COALESCE(parent.name, '') AS detail
            FROM categories c
            LEFT JOIN categories parent ON parent.id = c.parent_id
            LEFT JOIN users u ON u.id = c.updated_by
            WHERE (c.archived_at IS NOT NULL OR c.status = 'archived')
              AND (? IS NULL OR c.name LIKE ? OR c.slug LIKE ?)
            ORDER BY COALESCE(c.archived_at, c.updated_at) DESC, c.name
            LIMIT ?
            """,
            (like, like, like, fetch_cap),
        )
        items.extend(_archive_row("category", row) for row in category_rows)

    if principal.farm_id is None and principal.has("users.view"):
        farm_rows = await db.fetch_all(
            """
            SELECT f.id, f.name, f.slug, f.status, NULL AS archived_at, f.updated_at,
                   u.display_name AS updated_by,
                   COALESCE(f.region, '') AS detail
            FROM farms f
            LEFT JOIN users u ON u.id = f.updated_by
            WHERE f.status = 'archived'
              AND (? IS NULL OR f.name LIKE ? OR f.slug LIKE ?)
            ORDER BY f.updated_at DESC, f.name
            LIMIT ?
            """,
            (like, like, like, fetch_cap),
        )
        items.extend(_archive_row("farm", row) for row in farm_rows)

    if principal.farm_id is None and principal.has("pages.view"):
        page_rows = await db.fetch_all(
            """
            SELECT p.id, p.title AS name, p.slug, p.status, p.archived_at, p.updated_at,
                   u.display_name AS updated_by,
                   p.page_type AS detail
            FROM pages p
            LEFT JOIN users u ON u.id = p.updated_by
            WHERE (p.archived_at IS NOT NULL OR p.status = 'archived')
              AND (? IS NULL OR p.title LIKE ? OR p.slug LIKE ?)
            ORDER BY COALESCE(p.archived_at, p.updated_at) DESC, p.slug
            LIMIT ?
            """,
            (like, like, like, fetch_cap),
        )
        items.extend(_archive_row("page", row) for row in page_rows)

    if principal.farm_id is None and principal.has("articles.view"):
        article_rows = await db.fetch_all(
            """
            SELECT a.id, a.title AS name, a.slug, a.status, a.archived_at, a.updated_at,
                   u.display_name AS updated_by,
                   COALESCE(author.display_name, '') AS detail
            FROM articles a
            LEFT JOIN users u ON u.id = a.updated_by
            LEFT JOIN users author ON author.id = a.author_user_id
            WHERE (a.archived_at IS NOT NULL OR a.status = 'archived')
              AND (? IS NULL OR a.title LIKE ? OR a.slug LIKE ?)
            ORDER BY COALESCE(a.archived_at, a.updated_at) DESC, a.title
            LIMIT ?
            """,
            (like, like, like, fetch_cap),
        )
        items.extend(_archive_row("article", row) for row in article_rows)

    if principal.farm_id is None and principal.has("recipes.view"):
        recipe_rows = await db.fetch_all(
            """
            SELECT r.id, r.title AS name, r.slug, r.status, r.archived_at, r.updated_at,
                   u.display_name AS updated_by,
                   COALESCE(chef.display_name, '') AS detail
            FROM recipes r
            LEFT JOIN users u ON u.id = r.updated_by
            LEFT JOIN users chef ON chef.id = r.chef_user_id
            WHERE (r.archived_at IS NOT NULL OR r.status = 'archived')
              AND (? IS NULL OR r.title LIKE ? OR r.slug LIKE ?)
            ORDER BY COALESCE(r.archived_at, r.updated_at) DESC, r.title
            LIMIT ?
            """,
            (like, like, like, fetch_cap),
        )
        items.extend(_archive_row("recipe", row) for row in recipe_rows)

    items.sort(key=lambda item: item["archivedAt"], reverse=True)
    page = items[offset : offset + limit]
    return {"items": page, "limit": limit, "offset": offset}


@router.post("/archive/{kind}/{item_id}/restore")
async def restore_archive_item_endpoint(
    kind: str,
    item_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    permissions = {
        "product": "products.edit",
        "category": "categories.edit",
        "farm": "users.invite",
        "page": "pages.edit",
        "article": "articles.edit",
        "recipe": "recipes.edit",
    }
    permission = permissions.get(kind)
    if permission is None:
        raise NotFoundError("Archived item not found.")
    if not principal.has(permission):
        raise PermissionDeniedError()
    if kind != "product" and principal.farm_id is not None:
        raise PermissionDeniedError()

    now = utc_now_iso()
    request_id = _request_id(request)

    if kind == "product":
        await _assert_product_scope(db, item_id, principal)
        current = await db.fetch_one(
            "SELECT id, status, farm_id FROM products WHERE id = ?"
            " AND (archived_at IS NOT NULL OR status = 'archived')",
            (item_id,),
        )
        if current is None:
            raise NotFoundError("Archived product not found.")
        await db.batch(
            [
                (
                    "UPDATE products SET status = 'draft', archived_at = NULL,"
                    " updated_at = ?, updated_by = ? WHERE id = ?",
                    (now, principal.user_id, item_id),
                ),
                audit_statement(
                    action="product.restored",
                    entity_type="product",
                    entity_id=item_id,
                    actor_id=principal.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "draft"},
                ),
            ]
        )
        return {"id": item_id, "kind": kind, "status": "draft"}

    if kind == "category":
        current = await db.fetch_one(
            "SELECT id, status FROM categories WHERE id = ?"
            " AND (archived_at IS NOT NULL OR status = 'archived')",
            (item_id,),
        )
        if current is None:
            raise NotFoundError("Archived category not found.")
        await db.batch(
            [
                (
                    "UPDATE categories SET status = 'draft', archived_at = NULL,"
                    " updated_at = ?, updated_by = ? WHERE id = ?",
                    (now, principal.user_id, item_id),
                ),
                audit_statement(
                    action="category.restored",
                    entity_type="category",
                    entity_id=item_id,
                    actor_id=principal.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "draft"},
                ),
            ]
        )
        return {"id": item_id, "kind": kind, "status": "draft"}

    if kind == "farm":
        current = await db.fetch_one(
            "SELECT id, status FROM farms WHERE id = ? AND status = 'archived'",
            (item_id,),
        )
        if current is None:
            raise NotFoundError("Archived farm not found.")
        await db.batch(
            [
                (
                    "UPDATE farms SET status = 'draft', updated_at = ?, updated_by = ?"
                    " WHERE id = ?",
                    (now, principal.user_id, item_id),
                ),
                audit_statement(
                    action="farm.restored",
                    entity_type="farm",
                    entity_id=item_id,
                    actor_id=principal.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "draft"},
                ),
            ]
        )
        return {"id": item_id, "kind": kind, "status": "draft"}

    if kind == "article":
        current = await db.fetch_one(
            "SELECT id, status FROM articles WHERE id = ?"
            " AND (archived_at IS NOT NULL OR status = 'archived')",
            (item_id,),
        )
        if current is None:
            raise NotFoundError("Archived article not found.")
        await db.batch(
            [
                (
                    "UPDATE articles SET status = 'draft', archived_at = NULL,"
                    " updated_at = ?, updated_by = ? WHERE id = ?",
                    (now, principal.user_id, item_id),
                ),
                audit_statement(
                    action="article.restored",
                    entity_type="article",
                    entity_id=item_id,
                    actor_id=principal.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "draft"},
                ),
            ]
        )
        return {"id": item_id, "kind": kind, "status": "draft"}

    if kind == "recipe":
        current = await db.fetch_one(
            "SELECT id, status FROM recipes WHERE id = ?"
            " AND (archived_at IS NOT NULL OR status = 'archived')",
            (item_id,),
        )
        if current is None:
            raise NotFoundError("Archived recipe not found.")
        await db.batch(
            [
                (
                    "UPDATE recipes SET status = 'draft', archived_at = NULL,"
                    " updated_at = ?, updated_by = ? WHERE id = ?",
                    (now, principal.user_id, item_id),
                ),
                audit_statement(
                    action="recipe.restored",
                    entity_type="recipe",
                    entity_id=item_id,
                    actor_id=principal.user_id,
                    request_id=request_id,
                    created_at=now,
                    before={"status": current["status"]},
                    after={"status": "draft"},
                ),
            ]
        )
        return {"id": item_id, "kind": kind, "status": "draft"}

    current = await db.fetch_one(
        "SELECT id, status FROM pages WHERE id = ?"
        " AND (archived_at IS NOT NULL OR status = 'archived')",
        (item_id,),
    )
    if current is None:
        raise NotFoundError("Archived page not found.")
    await db.batch(
        [
            (
                "UPDATE pages SET status = 'draft', archived_at = NULL,"
                " updated_at = ?, updated_by = ? WHERE id = ?",
                (now, principal.user_id, item_id),
            ),
            audit_statement(
                action="page.restored",
                entity_type="page",
                entity_id=item_id,
                actor_id=principal.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={"status": "draft"},
            ),
        ]
    )
    return {"id": item_id, "kind": kind, "status": "draft"}


_ARCHIVE_PURGE_PERMISSIONS = {
    "product": "products.edit",
    "category": "categories.edit",
    "farm": "users.invite",
    "page": "pages.edit",
    "article": "articles.edit",
    "recipe": "recipes.edit",
}

_ARCHIVE_PURGE_TABLES = {
    "product": "products",
    "category": "categories",
    "farm": "farms",
    "page": "pages",
    "article": "articles",
    "recipe": "recipes",
}


async def _purge_archive_item(
    db: Database, actor: Principal, request_id: str, kind: str, item_id: str
) -> None:
    """Permanently removes an already-archived row. Unlike restore/archive,
    this is a real SQL DELETE with no way back — only reachable for rows the
    per-kind query above already confirmed are archived. Foreign-key
    RESTRICT constraints (e.g. a product whose variants still have order or
    inventory history) surface as a clear ConflictError instead of a raw
    database error, since D1 and the local SQLite adapter both raise on the
    same "FOREIGN KEY constraint failed" wording."""
    table = _ARCHIVE_PURGE_TABLES[kind]
    archived_clause = (
        "status = 'archived'"
        if kind == "farm"
        else "(archived_at IS NOT NULL OR status = 'archived')"
    )
    current = await db.fetch_one(
        f"SELECT id FROM {table} WHERE id = ? AND {archived_clause}", (item_id,)
    )
    if current is None:
        raise NotFoundError("Archived item not found.")
    now = utc_now_iso()
    try:
        await db.batch(
            [
                (f"DELETE FROM {table} WHERE id = ?", (item_id,)),
                audit_statement(
                    action=f"{kind}.purged",
                    entity_type=kind,
                    entity_id=item_id,
                    actor_id=actor.user_id,
                    request_id=request_id,
                    created_at=now,
                ),
            ]
        )
    except Exception as exc:
        if "foreign key constraint" in str(exc).lower():
            raise ConflictError(
                "Can't permanently delete this item — other records (such as orders or "
                "inventory history) still depend on it."
            ) from exc
        raise


class ArchivePurgeItem(_CamelModel):
    kind: str = Field(max_length=20)
    id: str = Field(max_length=64)


class ArchiveBulkDeleteRequest(_CamelModel):
    items: list[ArchivePurgeItem] = Field(min_length=1, max_length=100)


@router.post("/archive/bulk-delete")
async def bulk_delete_archive_endpoint(
    payload: ArchiveBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    request_id = _request_id(request)
    deleted: list[dict[str, str]] = []
    for item in payload.items:
        permission = _ARCHIVE_PURGE_PERMISSIONS.get(item.kind)
        if permission is None:
            raise NotFoundError("Archived item not found.")
        if not principal.has(permission):
            raise PermissionDeniedError()
        if item.kind != "product" and principal.farm_id is not None:
            raise PermissionDeniedError()
        if item.kind == "product":
            await _assert_product_scope(db, item.id, principal)
        await _purge_archive_item(db, principal, request_id, item.kind, item.id)
        deleted.append({"kind": item.kind, "id": item.id})
    return {"deleted": deleted, "count": len(deleted)}


# ---------------------------------------------------------------------------
# Global search
# ---------------------------------------------------------------------------

SEARCH_MIN_QUERY_LENGTH = 2
SEARCH_RESULT_LIMIT = 5


@router.get("/search")
async def global_search_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
    q: Annotated[str, Query(max_length=120)] = "",
) -> Any:
    """Cross-entity "jump to" search for the admin dashboard. Any authenticated
    staff member may call this endpoint, but each entity group is only
    populated if the principal actually holds that entity's `.view`
    permission — a user without `orders.view` gets an empty `orders` list,
    never a 403 for the whole request, so one search box works for everyone."""
    term = q.strip()
    empty: dict[str, list[dict[str, Any]]] = {
        "products": [],
        "orders": [],
        "users": [],
        "categories": [],
    }
    if len(term) < SEARCH_MIN_QUERY_LENGTH:
        return empty

    repo = AdminRepository(db)

    if principal.has("products.view"):
        rows = await repo.search_products(
            term, limit=SEARCH_RESULT_LIMIT, farm_id=principal.farm_id
        )
        empty["products"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "sku": row["sku"] or "—",
            }
            for row in rows
        ]

    if principal.has("orders.view"):
        rows = await repo.search_orders(term, limit=SEARCH_RESULT_LIMIT, farm_id=principal.farm_id)
        empty["orders"] = [
            {
                "id": row["id"],
                "publicReference": row["public_reference"],
                "customerEmail": contactable_email(row["customer_email"]),
                "orderStatus": row["order_status"],
                "totalMinor": row["total_minor"],
                "currencyCode": row["currency_code"],
            }
            for row in rows
        ]

    if principal.has("users.view"):
        rows = await repo.search_users(term, limit=SEARCH_RESULT_LIMIT)
        empty["users"] = [
            {
                "id": row["id"],
                "displayName": row["display_name"],
                "email": row["email"],
                "status": row["status"],
            }
            for row in rows
        ]

    if principal.has("categories.view"):
        rows = await repo.search_categories(term, limit=SEARCH_RESULT_LIMIT)
        empty["categories"] = [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "status": row["status"],
            }
            for row in rows
        ]

    return empty


class HighlightsUpdateRequest(_CamelModel):
    product_ids: list[str] = Field(max_length=12)


@router.get("/highlights")
async def get_highlights(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("settings.view"))],
) -> Any:
    """The curated highlight slots (search page box), in curated order."""
    rows = await db.fetch_all(
        """
        SELECT p.id, p.name, p.slug, p.status
        FROM highlighted_products hp
        JOIN products p ON p.id = hp.product_id
        WHERE p.archived_at IS NULL
        ORDER BY hp.sort_order
        """
    )
    return {
        "items": [
            {"id": row["id"], "name": row["name"], "slug": row["slug"], "status": row["status"]}
            for row in rows
        ]
    }


@router.put("/highlights")
async def update_highlights(
    payload: HighlightsUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("settings.edit"))],
) -> Any:
    await set_highlighted_products(
        db, principal, _request_id(request), product_ids=payload.product_ids
    )
    return await get_highlights(db, principal)


@router.post("/media/images")
async def upload_image_endpoint(
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("media.upload"))],
    filename: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
) -> Any:
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    if content_type == "application/json":
        payload = ImageUploadRequest.model_validate(await request.json())
        saved = await save_image_upload(
            request.app.state.media,
            db,
            principal,
            content_type=payload.content_type,
            data_base64=payload.data_base64,
            original_filename=filename,
        )
    else:
        # Browser uploads use the raw File body. Avoid base64 JSON here: in
        # Python Workers that path burns enough CPU for real photos to be
        # terminated before CORS headers are written.
        saved = await save_image_bytes(
            request.app.state.media,
            db,
            principal,
            content_type=content_type,
            data=await request.body(),
            original_filename=filename,
        )
    base_url = str(request.base_url).rstrip("/")
    return {"id": saved["id"], "url": f"{base_url}{saved['path']}"}


class MediaUpdateRequest(_CamelModel):
    alt_text: str | None = Field(default=None, max_length=300)
    caption: str | None = Field(default=None, max_length=500)


def _media_row(row: dict[str, Any], base_url: str) -> dict[str, Any]:
    return {
        "id": row["id"],
        "url": f"/media/{row['object_key']}",
        "originalFilename": row["original_filename"],
        "mimeType": row["mime_type"],
        "sizeBytes": row["size_bytes"],
        "widthPx": row["width_px"],
        "heightPx": row["height_px"],
        "altText": row["alt_text"] or "",
        "caption": row["caption"] or "",
        "createdAt": row["created_at"],
    }


@router.get("/media")
async def list_media_endpoint(
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("media.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 60,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await list_media(db, limit=limit, offset=offset, search=search)
    base_url = str(request.base_url).rstrip("/")
    return {
        "items": [_media_row(row, base_url) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.patch("/media/{media_id}")
async def update_media_endpoint(
    media_id: str,
    payload: MediaUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("media.edit"))],
) -> Any:
    row = await update_media(
        db,
        principal,
        _request_id(request),
        media_id,
        alt_text=payload.alt_text,
        caption=payload.caption,
    )
    base_url = str(request.base_url).rstrip("/")
    return _media_row(row, base_url)


@router.delete("/media/{media_id}")
async def delete_media_endpoint(
    media_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("media.delete"))],
) -> Any:
    await delete_media(request.app.state.media, db, principal, _request_id(request), media_id)
    return {"id": media_id, "deleted": True}


@router.get("/products")
async def list_products(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    rows = await AdminRepository(db).list_products(
        limit=limit, offset=offset, farm_id=principal.farm_id, search=search
    )
    items = []
    for row in rows:
        min_price = row["min_price_minor"]
        max_price = row["max_price_minor"]
        if min_price is None:
            price_range = "—"
        elif min_price == max_price:
            price_range = f"{min_price / 100:.0f}"
        else:
            price_range = f"{min_price / 100:.0f}-{max_price / 100:.0f}"
        items.append(
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "imageUrl": row["image_url"] or "",
                "imageAlt": row["image_alt"] or row["name"],
                "sku": row["sku"] or "—",
                "status": row["status"],
                "categories": (row["categories"] or "").split(", ") if row["categories"] else [],
                "farmName": row["farm_name"],
                "priceRange": price_range,
                "availableStock": row["available_stock"],
                "updatedAt": row["updated_at"],
                "updatedBy": row["updated_by"] or "—",
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


@router.get("/categories")
async def list_categories(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("categories.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: Annotated[str | None, Query(max_length=200)] = None,
) -> Any:
    rows = await AdminRepository(db).list_categories(limit=limit, offset=offset, search=search)
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "imageUrl": row["hero_image_url"] or "",
                "imageAlt": row["hero_image_alt"] or row["name"],
                "slug": row["slug"],
                "parentName": row["parent_name"],
                "productCount": row["product_count"],
                "visibility": row["visibility"],
                "status": row["status"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/diet-tags")
async def list_diet_tags(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("products.view"))],
) -> Any:
    """Full 'diet' tag_group vocabulary for the product editor's checkbox
    list -- small and fixed (a handful of rows), so unlike /categories this
    is neither paginated nor searchable."""
    rows = await db.fetch_all(
        "SELECT id, label FROM tags WHERE tag_group = 'diet' ORDER BY label"
    )
    return {"items": [{"id": row["id"], "label": row["label"]} for row in rows]}


@router.get("/certifications")
async def list_certifications(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("products.view"))],
) -> Any:
    """Full certification master list for the product editor's checkbox
    list -- same small/fixed shape as /diet-tags."""
    rows = await db.fetch_all("SELECT id, name FROM certifications ORDER BY name")
    return {"items": [{"id": row["id"], "name": row["name"]} for row in rows]}


@router.post("/categories/{category_id}/publish")
async def publish_category_endpoint(
    category_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.publish"))],
) -> Any:
    return await publish_category(
        db,
        CategoryRepository(db),
        category_id,
        principal,
        request_id=getattr(request.state, "request_id", "unknown"),
    )


@router.get("/inventory")
async def list_inventory(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    groups = await AdminRepository(db).list_inventory(
        limit=limit, offset=offset, farm_id=principal.farm_id, search=search
    )
    return {
        "items": [
            {
                "productId": group["product_id"],
                "productName": group["product_name"],
                "productStatus": group["product_status"],
                "variants": [
                    {
                        "variantId": variant["variant_id"],
                        "productId": group["product_id"],
                        "productStatus": group["product_status"],
                        "productName": group["product_name"],
                        "variantName": variant["variant_name"],
                        "sku": variant["sku"],
                        "locationName": variant["location_name"],
                        "onHand": variant["on_hand"],
                        "reserved": variant["reserved"],
                        "reorderThreshold": variant["reorder_threshold"],
                        "updatedAt": variant["updated_at"],
                    }
                    for variant in group["variants"]
                ],
            }
            for group in groups
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit")
async def audit_log(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AuditRepository(db).recent(limit=limit, offset=offset)
    return {
        "items": [
            {
                "id": row["id"],
                "actorName": row["actor_name"],
                "action": row["action"],
                "entityType": row["entity_type"],
                "entityId": row["entity_id"],
                "requestId": row["request_id"],
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Owner-only: server logs and read-only DB browser.
#
# Both are hard-gated to the super_admin role via `_require_owner`, on top of
# the `audit.view` permission dependency — a farm-owner sub-admin granted
# `audit.view` through Scope Management must still be rejected. See
# `_require_owner` above for why the permission check alone is not enough.
# ---------------------------------------------------------------------------


@router.get("/server-logs")
async def list_server_logs(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    await _require_owner(db, principal)
    rows = await db.fetch_all(
        """
        SELECT id, level, event, fields_json, created_at
        FROM application_logs
        ORDER BY created_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "level": row["level"],
                "event": row["event"],
                "fields": json.loads(row["fields_json"]),
                "createdAt": row["created_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


# Tables holding password hashes or session/rate-limit secrets. Excluded from
# both the table list and direct row access below — defense-in-depth only,
# since the owner already has unrestricted DB access via the Cloudflare
# dashboard regardless of what this read-only browser exposes.
_DB_BROWSER_BLOCKED_TABLES = frozenset({"user_credentials", "sessions", "auth_rate_limits"})


async def _db_browser_allowed_tables(db: Database) -> list[str]:
    """The allowlist of real, browsable table names, straight from sqlite_master
    minus the sensitive-table blocklist. This is the single source of truth
    both endpoints below validate `table_name` against before it is ever
    interpolated into a query string."""
    rows = await db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type='table'"
        " AND name NOT LIKE 'sqlite_%' ORDER BY name"
    )
    return [row["name"] for row in rows if row["name"] not in _DB_BROWSER_BLOCKED_TABLES]


@router.get("/db-browser/tables")
async def list_db_browser_tables(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("audit.view"))],
) -> Any:
    await _require_owner(db, principal)
    return {"items": await _db_browser_allowed_tables(db)}


@router.get("/db-browser/tables/{table_name}")
async def get_db_browser_table(
    table_name: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    await _require_owner(db, principal)
    if table_name not in await _db_browser_allowed_tables(db):
        raise NotFoundError("Table not found.")
    # Safe to interpolate only because table_name was just checked for an
    # exact match against sqlite_master above — `?` binds values, not
    # identifiers, so this is the one place a table name may be spliced in.
    columns = [row["name"] for row in await db.fetch_all(f"PRAGMA table_info({table_name})")]
    rows = await db.fetch_all(
        f"SELECT * FROM {table_name} LIMIT ? OFFSET ?",
        (limit, offset),
    )
    return {
        "columns": columns,
        "rows": [[row.get(column) for column in columns] for row in rows],
        "limit": limit,
        "offset": offset,
    }


# ---------------------------------------------------------------------------
# Product mutations
# ---------------------------------------------------------------------------


class ProductCreateRequest(_CamelModel):
    name: str = Field(min_length=3, max_length=140)
    product_type: str = Field(default="general", max_length=60)
    slug: str | None = Field(default=None, max_length=96)
    short_description: str | None = Field(default=None, max_length=300)


class ProductUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, max_length=140)
    slug: str | None = Field(default=None, max_length=96)
    short_description: str | None = Field(default=None, max_length=300)
    # Traceability copy (migration 0080), shown on the public product page
    # when set -- free text, not a structured date, so "harvested the week
    # of 3 March" is expressible alongside a plain date.
    harvest_note: str | None = Field(default=None, max_length=300)
    growing_method: str | None = Field(default=None, max_length=300)
    storage_guidance: str | None = Field(default=None, max_length=300)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    image_url: str | None = Field(default=None, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=200)
    release_scope: str | None = Field(default=None, max_length=16)
    release_countries: list[str] | None = Field(default=None, max_length=100)
    linked_product_ids: list[str] | None = Field(default=None, max_length=12)
    return_eligible: bool | None = Field(default=None)
    # Per-product order/payment switch (migration 0048), independent of the
    # site-wide one on Site Control. False keeps the product page live and
    # browsable while pulling only "Add to basket" -- see the migration.
    accepts_orders: bool | None = Field(default=None)
    # Overrides the site-wide payments switch in either direction (migration
    # 0069) -- "inherit" | "force_enabled" | "force_disabled", validated
    # against `services.catalogue._PAYMENTS_OVERRIDE_VALUES`.
    payments_override: str | None = Field(default=None, max_length=20)
    farm_id: str | None = Field(default=None)
    category_ids: list[str] | None = Field(default=None)
    # Dietary tags (tag_group = 'diet') and certifications the admin has
    # verified for this product -- see services.catalogue.update_product's
    # diet_tag_ids/certification_ids handling.
    diet_tag_ids: list[str] | None = Field(default=None)
    certification_ids: list[str] | None = Field(default=None)


class ProductBulkDeleteRequest(_CamelModel):
    product_ids: list[str] = Field(min_length=1, max_length=100)


class PublishRequest(_CamelModel):
    change_summary: str | None = Field(default=None, max_length=300)


@router.post("/products")
async def create_product_endpoint(
    payload: ProductCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.create"))],
) -> Any:
    return await create_product(
        db,
        principal,
        _request_id(request),
        name=payload.name,
        product_type=payload.product_type,
        slug=payload.slug,
        short_description=payload.short_description,
        farm_id=principal.farm_id,
    )


@router.get("/products/{product_id}")
async def get_product_endpoint(
    product_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.view"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    detail = await AdminRepository(db).get_product_detail(product_id)
    if detail is None:
        raise NotFoundError("Product not found.")
    images = await CatalogueRepository(db).list_images(product_id)
    return {
        "id": detail["id"],
        "name": detail["name"],
        "slug": detail["slug"],
        "shortDescription": detail["short_description"] or "",
        "harvestNote": detail["harvest_note"] or "",
        "growingMethod": detail["growing_method"] or "",
        "storageGuidance": detail["storage_guidance"] or "",
        "productType": detail["product_type"],
        "status": detail["status"],
        "farmName": detail["farm_name"],
        "farmId": detail.get("farm_id"),
        "categoryIds": detail.get("category_ids", []),
        "dietTagIds": detail.get("diet_tag_ids", []),
        "certificationIds": detail.get("certification_ids", []),
        "seoTitle": detail["seo_title"] or "",
        "seoDescription": detail["seo_description"] or "",
        "imageUrl": detail["image_url"] or "",
        "imageAlt": detail["image_alt"] or detail["name"],
        "images": [
            {"id": image["id"], "imageUrl": image["image_url"], "imageAlt": image["image_alt"]}
            for image in images
        ],
        "updatedAt": detail["updated_at"],
        "releaseScope": detail["release_scope"],
        "releaseCountries": detail["release_countries"],
        "returnEligible": bool(detail["return_eligible"]),
        "acceptsOrders": bool(detail["accepts_orders"]),
        "paymentsOverride": detail["payments_override"],
        "linkedProducts": [
            {
                "id": linked["id"],
                "name": linked["name"],
                "slug": linked["slug"],
                "status": linked["status"],
            }
            for linked in detail["linked_products"]
        ],
        "variants": [
            {
                "id": v["id"],
                "name": v["name"],
                "sku": v["sku"],
                "status": v["status"],
                "listMinor": v["list_minor"],
                "saleMinor": v["sale_minor"],
                "available": v["available"],
            }
            for v in detail["variants"]
        ],
    }


@router.patch("/products/{product_id}")
async def update_product_endpoint(
    product_id: str,
    payload: ProductUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    fields = payload.model_dump(exclude_unset=True)

    # Geo release and curated links are relational, not simple columns — they
    # are applied through their own audited services, then any remaining plain
    # fields go through the standard update path.
    changed = False
    release_scope = fields.pop("release_scope", None)
    release_countries = fields.pop("release_countries", None)
    if release_scope is None and release_countries is not None:
        # Countries sent alone keep the product's current scope.
        row = await db.fetch_one("SELECT release_scope FROM products WHERE id = ?", (product_id,))
        release_scope = row["release_scope"] if row else "global"
    if release_scope is not None:
        await set_product_release(
            db,
            principal,
            _request_id(request),
            product_id,
            scope=release_scope,
            countries=release_countries or [],
        )
        changed = True
    linked_product_ids = fields.pop("linked_product_ids", None)
    if linked_product_ids is not None:
        await set_product_links(
            db,
            principal,
            _request_id(request),
            product_id,
            linked_product_ids=linked_product_ids,
        )
        changed = True

    if fields:
        result = await update_product(
            db, principal, _request_id(request), product_id, fields=fields
        )
        result["changed"] = result.get("changed", False) or changed
        return result
    row = await db.fetch_one("SELECT status FROM products WHERE id = ?", (product_id,))
    return {"id": product_id, "status": row["status"] if row else "draft", "changed": changed}


class ProductImageInput(_CamelModel):
    image_url: str = Field(min_length=1, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=200)


class ProductImagesReplaceRequest(_CamelModel):
    images: list[ProductImageInput] = Field(default_factory=list, max_length=8)


@router.put("/products/{product_id}/images")
async def replace_product_images_endpoint(
    product_id: str,
    payload: ProductImagesReplaceRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    await replace_product_images(
        db,
        principal,
        _request_id(request),
        product_id,
        [image.model_dump(by_alias=False) for image in payload.images],
    )
    images = await CatalogueRepository(db).list_images(product_id)
    return {
        "images": [
            {"id": image["id"], "imageUrl": image["image_url"], "imageAlt": image["image_alt"]}
            for image in images
        ]
    }


class VariantCreateRequest(_CamelModel):
    name: str = Field(min_length=1, max_length=140)
    sku: str = Field(min_length=1, max_length=64)
    list_minor: int = Field(ge=0)
    sale_minor: int | None = Field(default=None)


class VariantUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, max_length=140)
    sku: str | None = Field(default=None, max_length=64)
    list_minor: int | None = Field(default=None, ge=0)
    sale_minor: int | None = Field(default=None)


class ProductStatusRequest(_CamelModel):
    status: str = Field(pattern="^(published|unpublished)$")


@router.post("/products/{product_id}/variants")
async def create_variant_endpoint(
    product_id: str,
    payload: VariantCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    from ..services.catalogue import create_variant

    await _assert_product_scope(db, product_id, principal)
    variant_id = await create_variant(
        db,
        principal,
        _request_id(request),
        product_id,
        name=payload.name,
        sku=payload.sku,
        list_minor=payload.list_minor,
        sale_minor=payload.sale_minor,
    )
    return {"id": variant_id}


@router.patch("/products/{product_id}/variants/{variant_id}")
async def update_variant_endpoint(
    product_id: str,
    variant_id: str,
    payload: VariantUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    from ..services.catalogue import update_variant

    await _assert_product_scope(db, product_id, principal)
    return await update_variant(
        db,
        principal,
        _request_id(request),
        product_id,
        variant_id,
        name=payload.name,
        sku=payload.sku,
        list_minor=payload.list_minor,
        sale_minor=payload.sale_minor,
    )


@router.patch("/products/{product_id}/status")
async def set_product_status_endpoint(
    product_id: str,
    payload: ProductStatusRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.publish"))],
) -> Any:
    from ..services.catalogue import set_product_status

    await _assert_product_scope(db, product_id, principal)
    return await set_product_status(
        db,
        principal,
        _request_id(request),
        product_id,
        payload.status,
    )


@router.post("/products/{product_id}/publish")
async def publish_product_endpoint(
    product_id: str,
    payload: PublishRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.publish"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    return await publish_product(
        db, product_id, principal, _request_id(request), payload.change_summary
    )


@router.post("/products/{product_id}/archive")
async def archive_product_endpoint(
    product_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    return await archive_product(db, principal, _request_id(request), product_id)


@router.delete("/products/{product_id}")
async def delete_product_endpoint(
    product_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    await _assert_product_scope(db, product_id, principal)
    return await archive_product(db, principal, _request_id(request), product_id)


@router.post("/products/bulk-delete")
async def bulk_delete_products_endpoint(
    payload: ProductBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.edit"))],
) -> Any:
    deleted: list[str] = []
    for product_id in payload.product_ids:
        await _assert_product_scope(db, product_id, principal)
        await archive_product(db, principal, _request_id(request), product_id)
        deleted.append(product_id)
    return {"deletedIds": deleted, "count": len(deleted)}


# ---------------------------------------------------------------------------
# Category mutations
# ---------------------------------------------------------------------------


class CategoryCreateRequest(_CamelModel):
    name: str = Field(min_length=3, max_length=140)
    slug: str | None = Field(default=None, max_length=96)
    short_description: str | None = Field(default=None, max_length=300)
    hero_title: str | None = Field(default=None, max_length=160)
    hero_description: str | None = Field(default=None, max_length=500)


class CategoryUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, max_length=140)
    slug: str | None = Field(default=None, max_length=96)
    short_description: str | None = Field(default=None, max_length=300)
    hero_eyebrow: str | None = Field(default=None, max_length=120)
    hero_title: str | None = Field(default=None, max_length=160)
    hero_description: str | None = Field(default=None, max_length=500)
    season_label: str | None = Field(default=None, max_length=80)
    theme_key: str | None = Field(default=None, max_length=40)
    visibility: str | None = Field(default=None, max_length=16)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)
    release_scope: str | None = Field(default=None, max_length=16)
    release_countries: list[str] | None = Field(default=None, max_length=100)


class CategoryBulkDeleteRequest(_CamelModel):
    category_ids: list[str] = Field(min_length=1, max_length=100)


@router.post("/categories")
async def create_category_endpoint(
    payload: CategoryCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.create"))],
) -> Any:
    return await create_category(
        db,
        principal,
        _request_id(request),
        name=payload.name,
        slug=payload.slug,
        short_description=payload.short_description,
        hero_title=payload.hero_title,
        hero_description=payload.hero_description,
    )


@router.get("/categories/{category_id}")
async def get_category_endpoint(
    category_id: str,
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("categories.view"))],
) -> Any:
    detail = await AdminRepository(db).get_category_detail(category_id)
    if detail is None:
        raise NotFoundError("Category not found.")
    return {
        "id": detail["id"],
        "name": detail["name"],
        "slug": detail["slug"],
        "shortDescription": detail["short_description"] or "",
        "heroEyebrow": detail["hero_eyebrow"] or "",
        "heroTitle": detail["hero_title"] or "",
        "heroDescription": detail["hero_description"] or "",
        "seasonLabel": detail["season_label"] or "",
        "themeKey": detail["theme_key"] or "",
        "visibility": detail["visibility"],
        "status": detail["status"],
        "seoTitle": detail["seo_title"] or "",
        "seoDescription": detail["seo_description"] or "",
        "heroImageUrl": detail["hero_image_url"] or "",
        "heroImageAlt": detail["hero_image_alt"] or detail["name"],
        "productAssignmentMode": detail["product_assignment_mode"],
        "releaseScope": detail["release_scope"],
        "releaseCountries": detail["release_countries"],
        "updatedAt": detail["updated_at"],
    }


@router.patch("/categories/{category_id}")
async def update_category_endpoint(
    category_id: str,
    payload: CategoryUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.edit"))],
) -> Any:
    fields = payload.model_dump(exclude_unset=True)

    # Geo release is relational, not a simple column — applied through its own
    # audited service, mirroring update_product_endpoint exactly.
    changed = False
    release_scope = fields.pop("release_scope", None)
    release_countries = fields.pop("release_countries", None)
    if release_scope is None and release_countries is not None:
        row = await db.fetch_one(
            "SELECT release_scope FROM categories WHERE id = ?", (category_id,)
        )
        release_scope = row["release_scope"] if row else "global"
    if release_scope is not None:
        await set_category_release(
            db,
            principal,
            _request_id(request),
            category_id,
            scope=release_scope,
            countries=release_countries or [],
        )
        changed = True

    if fields:
        result = await update_category(
            db, principal, _request_id(request), category_id, fields=fields
        )
        result["changed"] = result.get("changed", False) or changed
        return result
    row = await db.fetch_one("SELECT status FROM categories WHERE id = ?", (category_id,))
    return {"id": category_id, "status": row["status"] if row else "draft", "changed": changed}


class CategoryStatusRequest(_CamelModel):
    status: str = Field(pattern="^(published|unpublished)$")


@router.patch("/categories/{category_id}/status")
async def set_category_status_endpoint(
    category_id: str,
    payload: CategoryStatusRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.publish"))],
) -> Any:
    from ..services.catalogue import set_category_status

    return await set_category_status(
        db,
        principal,
        _request_id(request),
        category_id,
        payload.status,
    )


@router.delete("/categories/{category_id}")
async def delete_category_endpoint(
    category_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.edit"))],
) -> Any:
    return await archive_category(db, principal, _request_id(request), category_id)


@router.post("/categories/bulk-delete")
async def bulk_delete_categories_endpoint(
    payload: CategoryBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("categories.edit"))],
) -> Any:
    deleted: list[str] = []
    for category_id in payload.category_ids:
        await archive_category(db, principal, _request_id(request), category_id)
        deleted.append(category_id)
    return {"deletedIds": deleted, "count": len(deleted)}


# ---------------------------------------------------------------------------
# Inventory adjustment
# ---------------------------------------------------------------------------


class InventoryAdjustRequest(_CamelModel):
    variant_id: str | None = Field(default=None, max_length=64)
    sku: str | None = Field(default=None, max_length=64)
    quantity_delta: int
    reason_code: str = Field(max_length=32)
    note: str = Field(min_length=1, max_length=300)


class InventoryBulkClearRequest(_CamelModel):
    variant_ids: list[str] = Field(min_length=1, max_length=100)
    note: str = Field(min_length=5, max_length=300)


@router.post("/inventory/adjustments")
async def adjust_inventory_endpoint(
    payload: InventoryAdjustRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.adjust"))],
) -> Any:
    variant_id = payload.variant_id
    if variant_id is None and payload.sku:
        row = await db.fetch_one(
            "SELECT id FROM product_variants WHERE sku = ?", (payload.sku.strip(),)
        )
        if row is None:
            raise NotFoundError("No variant with that SKU.")
        variant_id = row["id"]
    if not variant_id:
        raise NotFoundError("A variant id or SKU is required.")
    await _assert_variant_scope(db, variant_id, principal)
    return await adjust_inventory(
        db,
        principal,
        _request_id(request),
        variant_id=variant_id,
        quantity_delta=payload.quantity_delta,
        reason_code=payload.reason_code,
        note=payload.note,
    )


@router.post("/inventory/bulk-clear")
async def bulk_clear_inventory_endpoint(
    payload: InventoryBulkClearRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("inventory.adjust"))],
) -> Any:
    for variant_id in payload.variant_ids:
        await _assert_variant_scope(db, variant_id, principal)
    return await clear_inventory_levels(
        db,
        principal,
        _request_id(request),
        variant_ids=payload.variant_ids,
        note=payload.note,
    )


# ---------------------------------------------------------------------------
# Users & roles
# ---------------------------------------------------------------------------


class UserInviteRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    role_ids: list[str] = Field(default_factory=list)


class UserCreateRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    role_ids: list[str] = Field(default_factory=list)
    password: str = Field(min_length=1, max_length=256)


class UserStatusRequest(_CamelModel):
    status: str = Field(max_length=16)


class UserRolesRequest(_CamelModel):
    role_ids: list[str] = Field(default_factory=list)


class RolePermissionsRequest(_CamelModel):
    permission_ids: list[str] = Field(default_factory=list)


class RoleCreateRequest(_CamelModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=300)
    permission_ids: list[str] = Field(default_factory=list)


class RoleUpdateRequest(_CamelModel):
    name: str = Field(min_length=3, max_length=80)
    description: str = Field(default="", max_length=300)


class UserBulkDeleteRequest(_CamelModel):
    user_ids: list[str] = Field(min_length=1, max_length=100)


async def _assert_scope_owner(db: Database, principal: Principal) -> None:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only the owner can manage role scopes.")
    owner_role = await db.fetch_one(
        """
        SELECT 1
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = ? AND r.key = 'super_admin'
        LIMIT 1
        """,
        (principal.user_id,),
    )
    if owner_role is None:
        raise PermissionDeniedError("Only the owner can manage role scopes.")


@router.get("/users")
async def list_users_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("users.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await AdminRepository(db).list_users(limit=limit, offset=offset, search=search)
    return {
        "items": [
            {
                "id": row["id"],
                "displayName": row["display_name"],
                "email": row["email"],
                "status": row["status"],
                "roles": row["role_names"].split(", ") if row["role_names"] else [],
                "roleIds": row["role_ids"].split(",") if row["role_ids"] else [],
                "lastSignInAt": row["last_sign_in_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/roles")
async def list_roles_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("users.view"))],
) -> Any:
    rows = await AdminRepository(db).list_roles()
    return {
        "items": [
            {
                "id": row["id"],
                "key": row["key"],
                "name": row["name"],
                "description": row["description"] or "",
                "isSystem": bool(row["is_system"]),
                "locked": row["key"] == "super_admin",
                "permissionIds": row["permission_ids"].split(",") if row["permission_ids"] else [],
                "permissionKeys": row["permission_keys"].split(",")
                if row["permission_keys"]
                else [],
            }
            for row in rows
        ]
    }


@router.get("/permissions")
async def list_permissions_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    await _assert_scope_owner(db, principal)
    rows = await AdminRepository(db).list_permissions()
    return {
        "items": [
            {"id": row["id"], "key": row["key"], "description": row["description"]} for row in rows
        ]
    }


@router.patch("/roles/{role_id}/permissions")
async def set_role_permissions_endpoint(
    role_id: str,
    payload: RolePermissionsRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    await _assert_scope_owner(db, principal)
    return await set_role_permissions(
        db,
        principal,
        _request_id(request),
        role_id,
        permission_ids=payload.permission_ids,
    )


@router.post("/roles")
async def create_role_endpoint(
    payload: RoleCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    await _assert_scope_owner(db, principal)
    return await create_role(
        db,
        principal,
        _request_id(request),
        name=payload.name,
        description=payload.description,
        permission_ids=payload.permission_ids,
    )


@router.patch("/roles/{role_id}")
async def update_role_endpoint(
    role_id: str,
    payload: RoleUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    await _assert_scope_owner(db, principal)
    return await update_role(
        db,
        principal,
        _request_id(request),
        role_id,
        name=payload.name,
        description=payload.description,
    )


@router.delete("/roles/{role_id}")
async def delete_role_endpoint(
    role_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    await _assert_scope_owner(db, principal)
    await delete_role(db, principal, _request_id(request), role_id)
    return {"id": role_id, "deleted": True}


@router.get("/contact-messages")
async def list_contact_messages_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can view contact attempts.")
    where_clause = ""
    params: list[Any] = []
    if search:
        # Phone included: "someone rang about this last week" is the lookup
        # staff actually run, and it is the one field they are certain of.
        where_clause = "WHERE name LIKE ? OR email LIKE ? OR subject LIKE ? OR phone_e164 LIKE ?"
        params.extend([f"%{search}%", f"%{search}%", f"%{search}%", f"%{search}%"])
    params.extend([limit, max(offset, 0)])
    rows = await db.fetch_all(
        f"""
        SELECT id, name, email, phone_e164, subject, message, status, created_at, handled_at
        FROM contact_messages
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
        """,
        tuple(params),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                # NULL for anything sent before migration 0045 added the
                # column. The console renders that as "not given" rather than
                # an empty cell that reads as a bug.
                "phone": row["phone_e164"],
                "subject": row["subject"],
                "message": row["message"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "handledAt": row["handled_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.post("/users/invite")
async def invite_user_endpoint(
    payload: UserInviteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    result = await invite_user(
        db,
        principal,
        _request_id(request),
        email=payload.email,
        display_name=payload.display_name,
        role_ids=payload.role_ids,
    )
    settings = get_settings()
    email = await request_staff_invitation_email(
        db,
        user_id=result["id"],
        reset_base_url=f"{settings.public_admin_url}/reset-password",
        settings=settings,
    )
    email_sent = (
        send_email(email.to, email.subject, email.body, settings, email.html_body)
        if email is not None
        else False
    )
    # The console sender "succeeds" without delivering anything, so a bare
    # emailSent=true would tell the operator an invitation arrived when no mail
    # transport is configured at all. Report which transport handled it.
    return {**result, "emailSent": email_sent, "emailTransport": email_transport_name(settings)}


@router.post("/users")
async def create_user_endpoint(
    payload: UserCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can add users.")
    return await create_user(
        db,
        principal,
        _request_id(request),
        email=payload.email,
        display_name=payload.display_name,
        role_ids=payload.role_ids,
        password=payload.password,
    )


@router.patch("/users/{user_id}/status")
async def set_user_status_endpoint(
    user_id: str,
    payload: UserStatusRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    return await set_user_status(
        db, principal, _request_id(request), user_id, status=payload.status
    )


@router.patch("/users/{user_id}/roles")
async def set_user_roles_endpoint(
    user_id: str,
    payload: UserRolesRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    return await set_user_roles(
        db, principal, _request_id(request), user_id, role_ids=payload.role_ids
    )


@router.delete("/users/{user_id}")
async def delete_user_endpoint(
    user_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    return await delete_users(db, principal, _request_id(request), [user_id])


@router.post("/users/bulk-delete")
async def bulk_delete_users_endpoint(
    payload: UserBulkDeleteRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    return await delete_users(db, principal, _request_id(request), payload.user_ids)


@router.post("/users/{user_id}/temporary-password")
async def reset_farm_owner_password_endpoint(
    user_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can reset farm owner passwords.")
    return await reset_farm_owner_password(db, principal, _request_id(request), user_id)


@router.post("/users/{user_id}/password-reset-email")
async def email_user_password_reset_endpoint(
    user_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.manage_roles"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can reset user passwords.")
    user = await db.fetch_one(
        """
        SELECT u.id, u.email, u.status
        FROM users u
        WHERE u.id = ? AND u.user_type = 'staff' AND u.deleted_at IS NULL
        """,
        (user_id,),
    )
    if user is None:
        raise NotFoundError("User not found.")

    settings = get_settings()
    email = await request_staff_password_reset_for_user(
        db,
        user_id=user_id,
        reset_base_url=f"{settings.public_admin_url}/reset-password",
        settings=settings,
    )
    if email is None:
        raise ValidationAppError("This user cannot receive a reset email.")
    email_sent = send_email(email.to, email.subject, email.body, settings, email.html_body)
    await db.batch(
        [
            audit_statement(
                action="user.password_reset_email",
                entity_type="user",
                entity_id=user_id,
                actor_id=principal.user_id,
                request_id=_request_id(request),
                created_at=utc_now_iso(),
                after={
                    "email": user["email"],
                    "status": user["status"],
                    "resetEmailSent": email_sent,
                    "passwordStored": False,
                },
            )
        ]
    )
    return {
        "id": user_id,
        "email": user["email"],
        "emailSent": email_sent,
        "emailTransport": email_transport_name(settings),
    }


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class OrderStatusRequest(_CamelModel):
    status: str = Field(max_length=32)


class OrderRefundRequest(_CamelModel):
    amount_minor: int | None = Field(default=None, ge=1)
    reason: str = Field(min_length=3, max_length=300)


@router.get("/orders")
async def list_orders_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("orders.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    rows = await AdminRepository(db).list_orders(
        limit=limit, offset=offset, search=search, farm_id=principal.farm_id
    )
    return {
        "items": [
            {
                "id": row["id"],
                "publicReference": row["public_reference"],
                # Null, not the `@phone.invalid` placeholder: staff looking at a
                # phone-only customer's order should see no email, not a fake one
                # they might try to write to.
                "customerEmail": contactable_email(row["customer_email"]),
                "totalMinor": row["total_minor"],
                "currencyCode": row["currency_code"],
                "orderStatus": row["order_status"],
                "paymentStatus": row["payment_status"],
                "fulfilmentStatus": row["fulfilment_status"],
                "placedAt": row["placed_at"] or row["created_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/orders/{order_id}")
async def get_order_endpoint(
    order_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("orders.view"))],
) -> Any:
    order = await AdminRepository(db).get_order_detail(order_id, farm_id=principal.farm_id)
    if order is None:
        raise NotFoundError("Order not found.")
    return {
        "id": order["id"],
        "publicReference": order["public_reference"],
        "customerEmail": contactable_email(order["customer_email"]),
        "customerPhone": order["customer_phone_e164"],
        "currencyCode": order["currency_code"],
        "subtotalMinor": order["subtotal_minor"],
        "discountMinor": order["discount_minor"],
        "deliveryMinor": order["delivery_minor"],
        "taxMinor": order["tax_minor"],
        "totalMinor": order["total_minor"],
        "giftCardAppliedMinor": order["gift_card_applied_minor"],
        "giftCardCode": order["gift_card_code"],
        "orderStatus": order["order_status"],
        "paymentStatus": order["payment_status"],
        "fulfilmentStatus": order["fulfilment_status"],
        "deliveryStatus": order["delivery_status"],
        "placedAt": order["placed_at"] or order["created_at"],
        "items": [
            {
                "id": item["id"],
                "productName": item["product_name"],
                "variantName": item["variant_name"],
                "sku": item["sku"],
                "quantity": item["quantity"],
                "unitMinor": item["unit_effective_amount_minor"],
                "lineTotalMinor": item["line_total_minor"],
            }
            for item in order["items"]
        ],
        "payment": (
            {
                "provider": order["payment"]["provider"],
                "status": order["payment"]["status"],
                "amountMinor": order["payment"]["amount_minor"],
                "currencyCode": order["payment"]["currency_code"],
                "refundedMinor": order["payment"]["refunded_minor"],
            }
            if order["payment"] is not None
            else None
        ),
    }


@router.patch("/orders/{order_id}/status")
async def update_order_status_endpoint(
    order_id: str,
    payload: OrderStatusRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("orders.view"))],
) -> Any:
    return await update_order_status(
        db, principal, _request_id(request), order_id, target_status=payload.status
    )


@router.post("/orders/{order_id}/refund")
async def refund_order_endpoint(
    order_id: str,
    payload: OrderRefundRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("orders.view"))],
) -> Any:
    return await issue_refund(
        db,
        principal,
        _request_id(request),
        order_id,
        amount_minor=payload.amount_minor,
        reason=payload.reason,
    )


@router.get("/refunds")
async def list_refunds_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """Owner-only oversight of every refund issued, regardless of who issued it
    -- read from the audit trail rather than payment_events so actor and
    reason (never stored on payment_events itself) come along for free."""
    await _require_owner(db, principal)
    rows = await db.fetch_all(
        """
        SELECT al.id, al.entity_id AS order_id, al.actor_user_id,
               u.display_name AS actor_name, al.after_summary_json, al.created_at,
               o.public_reference, o.currency_code
        FROM audit_logs al
        JOIN orders o ON o.id = al.entity_id
        LEFT JOIN users u ON u.id = al.actor_user_id
        WHERE al.action = 'order.refunded'
        ORDER BY al.created_at DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    )
    items = []
    for row in rows:
        after = json.loads(row["after_summary_json"] or "{}")
        items.append(
            {
                "id": row["id"],
                "orderId": row["order_id"],
                "orderReference": row["public_reference"],
                "currencyCode": row["currency_code"],
                "actorName": row["actor_name"] or "Unknown",
                "paymentStatus": after.get("paymentStatus"),
                "refundedMinor": after.get("refundedNow"),
                "reason": after.get("reason"),
                "providerRefundId": after.get("providerRefundId"),
                "createdAt": row["created_at"],
            }
        )
    return {"items": items, "limit": limit, "offset": offset}


# ---------------------------------------------------------------------------
# Farm owners (created only from the main admin panel) & staff password reset
# ---------------------------------------------------------------------------


class FarmOwnerCreateRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    farm_id: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class FarmCreateRequest(_CamelModel):
    name: str = Field(min_length=3, max_length=140)
    slug: str | None = Field(default=None, max_length=140)
    farmer_name: str = Field(default="", max_length=140)
    region: str = Field(default="", max_length=180)
    country_code: str = Field(default="IN", min_length=2, max_length=2)
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    summary: str = Field(default="", max_length=500)
    status: str = Field(default="published", max_length=24)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)


class FarmUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=3, max_length=140)
    slug: str | None = Field(default=None, max_length=140)
    farmer_name: str | None = Field(default=None, max_length=140)
    region: str | None = Field(default=None, max_length=180)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    summary: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=24)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)


class StaffResetRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)


class StaffResetConfirm(_CamelModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


def _farm_response(row: Any) -> dict[str, Any]:
    story = json.loads(row["story_json"] or "{}")
    summary = story.get("summary", "") if isinstance(story, dict) else ""
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "farmerName": row["farmer_name"] or "",
        "region": row["region"] or "",
        "countryCode": row["country_code"],
        "establishedYear": row["established_year"],
        "summary": summary,
        "status": row["status"],
        "productCount": row["product_count"],
        "updatedAt": row["updated_at"],
        "heroImageUrl": row["hero_image_url"] or None,
        "heroImageAlt": row["hero_image_alt"] or None,
    }


@router.get("/farms")
async def list_farms_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("users.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
    search: str | None = None,
) -> Any:
    where_clause = "WHERE f.status != 'archived'"
    params: list[Any] = []
    if search:
        where_clause += " AND (f.name LIKE ? OR f.farmer_name LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])
    params.extend([limit, max(offset, 0)])
    rows = await db.fetch_all(
        f"""
        SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.country_code,
               f.story_json, f.established_year, f.status, f.updated_at,
               f.hero_image_url, f.hero_image_alt,
               (SELECT COUNT(*) FROM products p
                 WHERE p.farm_id = f.id AND p.archived_at IS NULL) AS product_count
        FROM farms f
        {where_clause}
        ORDER BY f.name
        LIMIT ? OFFSET ?
        """,
        tuple(params),
    )
    return {
        "items": [_farm_response(row) for row in rows],
        "limit": limit,
        "offset": offset,
    }


@router.post("/farms")
async def create_farm_endpoint(
    payload: FarmCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can create farms.")
    name = payload.name.strip()
    slug = validate_slug(payload.slug.strip()) if payload.slug else slugify(name)
    existing = await db.fetch_one("SELECT id FROM farms WHERE slug = ?", (slug,))
    if existing is not None:
        raise ValidationAppError("A farm with that slug already exists.")
    status = payload.status if payload.status in {"draft", "published", "unpublished"} else "draft"
    now = utc_now_iso()
    farm_id = new_id("farm")
    summary = payload.summary.strip()
    story_json = json.dumps({"summary": summary}) if summary else None
    await db.batch(
        [
            (
                """
                INSERT INTO farms (
                  id, name, slug, farmer_name, region, country_code, established_year,
                  story_json, status, seo_title, seo_description,
                  hero_image_url, hero_image_alt,
                  created_at, created_by, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    farm_id,
                    name,
                    slug,
                    payload.farmer_name.strip() or None,
                    payload.region.strip() or None,
                    payload.country_code.upper(),
                    payload.established_year,
                    story_json,
                    status,
                    f"{name} - True Grit partner farm",
                    summary,
                    (payload.hero_image_url or "").strip() or None,
                    (payload.hero_image_alt or "").strip() or None,
                    now,
                    principal.user_id,
                    now,
                    principal.user_id,
                ),
            ),
            audit_statement(
                action="farm.created",
                entity_type="farm",
                entity_id=farm_id,
                actor_id=principal.user_id,
                request_id=_request_id(request),
                created_at=now,
                after={"name": name, "slug": slug, "status": status},
            ),
        ]
    )
    return {
        "id": farm_id,
        "name": name,
        "slug": slug,
        "farmerName": payload.farmer_name.strip(),
        "region": payload.region.strip(),
        "countryCode": payload.country_code.upper(),
        "establishedYear": payload.established_year,
        "summary": summary,
        "status": status,
        "productCount": 0,
        "updatedAt": now,
        "heroImageUrl": (payload.hero_image_url or "").strip() or None,
        "heroImageAlt": (payload.hero_image_alt or "").strip() or None,
    }


@router.patch("/farms/{farm_id}")
async def update_farm_endpoint(
    farm_id: str,
    payload: FarmUpdateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can edit farms.")
    current = await db.fetch_one(
        """
        SELECT f.*,
               (SELECT COUNT(*) FROM products p
                 WHERE p.farm_id = f.id AND p.archived_at IS NULL) AS product_count
        FROM farms f
        WHERE f.id = ? AND f.status != 'archived'
        """,
        (farm_id,),
    )
    if current is None:
        raise NotFoundError("Farm not found.")

    fields = payload.model_dump(exclude_unset=True)
    updates: dict[str, Any] = {}
    if "name" in fields and payload.name is not None:
        name = payload.name.strip()
        updates["name"] = name
        updates["seo_title"] = f"{name} - True Grit partner farm"
    if "slug" in fields and payload.slug:
        slug = validate_slug(payload.slug.strip())
        existing = await db.fetch_one(
            "SELECT id FROM farms WHERE slug = ? AND id != ?",
            (slug, farm_id),
        )
        if existing is not None:
            raise ValidationAppError("A farm with that slug already exists.")
        updates["slug"] = slug
    if "farmer_name" in fields:
        updates["farmer_name"] = payload.farmer_name.strip() if payload.farmer_name else None
    if "region" in fields:
        updates["region"] = payload.region.strip() if payload.region else None
    if "country_code" in fields and payload.country_code:
        updates["country_code"] = payload.country_code.upper()
    if "established_year" in fields:
        updates["established_year"] = payload.established_year
    if "summary" in fields:
        summary = payload.summary.strip() if payload.summary else ""
        updates["story_json"] = json.dumps({"summary": summary}) if summary else None
        updates["seo_description"] = summary
    if "status" in fields and payload.status:
        updates["status"] = (
            payload.status if payload.status in {"draft", "published", "unpublished"} else "draft"
        )
    if "hero_image_url" in fields:
        updates["hero_image_url"] = (
            payload.hero_image_url.strip() if payload.hero_image_url else None
        )
    if "hero_image_alt" in fields:
        updates["hero_image_alt"] = (
            payload.hero_image_alt.strip() if payload.hero_image_alt else None
        )

    changed = {key: value for key, value in updates.items() if value != current[key]}
    if changed:
        now = utc_now_iso()
        assignments = ", ".join(f"{key} = ?" for key in changed)
        await db.batch(
            [
                (
                    f"UPDATE farms SET {assignments}, updated_at = ?, updated_by = ? WHERE id = ?",
                    (*changed.values(), now, principal.user_id, farm_id),
                ),
                audit_statement(
                    action="farm.updated",
                    entity_type="farm",
                    entity_id=farm_id,
                    actor_id=principal.user_id,
                    request_id=_request_id(request),
                    created_at=now,
                    before={key: current[key] for key in changed},
                    after=changed,
                ),
            ]
        )

    refreshed = await db.fetch_one(
        """
        SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.country_code,
               f.story_json, f.established_year, f.status, f.updated_at,
               f.hero_image_url, f.hero_image_alt,
               (SELECT COUNT(*) FROM products p
                 WHERE p.farm_id = f.id AND p.archived_at IS NULL) AS product_count
        FROM farms f
        WHERE f.id = ?
        """,
        (farm_id,),
    )
    return _farm_response(refreshed)


@router.delete("/farms/{farm_id}")
async def delete_farm_endpoint(
    farm_id: str,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can delete farms.")
    current = await db.fetch_one(
        "SELECT id, name, status FROM farms WHERE id = ? AND status != 'archived'",
        (farm_id,),
    )
    if current is None:
        raise NotFoundError("Farm not found.")
    product_rows = await db.fetch_all(
        "SELECT id FROM products WHERE farm_id = ? AND archived_at IS NULL",
        (farm_id,),
    )
    request_id = _request_id(request)
    for product in product_rows:
        await archive_product(db, principal, request_id, product["id"])
    now = utc_now_iso()
    await db.batch(
        [
            (
                "UPDATE farms SET status = 'archived', updated_at = ?, updated_by = ? WHERE id = ?",
                (now, principal.user_id, farm_id),
            ),
            audit_statement(
                action="farm.archived",
                entity_type="farm",
                entity_id=farm_id,
                actor_id=principal.user_id,
                request_id=request_id,
                created_at=now,
                before={"status": current["status"]},
                after={
                    "status": "archived",
                    "archivedProductCount": len(product_rows),
                },
            ),
        ]
    )
    return {"id": farm_id, "status": "archived", "archivedProductCount": len(product_rows)}


@router.post("/farm-owners")
async def create_farm_owner_endpoint(
    payload: FarmOwnerCreateRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.invite"))],
) -> Any:
    # Farm owners are provisioned only from the main admin panel — a farm-scoped
    # sub-admin (who has no users.invite anyway) can never create another.
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can create farm owners.")
    return await create_farm_owner(
        db,
        principal,
        _request_id(request),
        email=payload.email,
        display_name=payload.display_name,
        farm_id=payload.farm_id,
        password=payload.password,
    )


@router.post("/auth/password-reset")
async def staff_password_reset_request(
    payload: StaffResetRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    settings = get_settings()
    if settings.rate_limit_enabled:
        await enforce_rate_limit(
            db,
            key=f"admin-reset:ip:{hash_identifier(client_ip(request))}",
            rule=RateLimitRule(
                settings.rate_limit_login_per_ip, settings.rate_limit_window_seconds
            ),
        )
    email = await request_password_reset(
        db,
        email=payload.email,
        user_type="staff",
        reset_base_url=f"{settings.public_admin_url}/reset-password",
        settings=settings,
    )
    if email is not None:
        send_email(email.to, email.subject, email.body, settings, email.html_body)
    return {"ok": True}


@router.post("/auth/password-reset/confirm")
async def staff_password_reset_confirm(
    payload: StaffResetConfirm,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    return await confirm_password_reset(
        db,
        token=payload.token,
        new_password=payload.new_password,
        settings=get_settings(),
        request_id=_request_id(request),
        source="admin",
    )


# ---------------------------------------------------------------------------
# Farm revenue & payouts
#
# Two permissions, because reading what a farm earned and moving money to it
# are different jobs: `revenue.view` for the console, `revenue.manage` for the
# commission rate and the payout button.
# ---------------------------------------------------------------------------


class DefaultCommissionRequest(_CamelModel):
    percent: float = Field(ge=0, le=100)


class FarmCommissionRequest(_CamelModel):
    # `None` clears the override and returns the farm to the house default,
    # which is deliberately distinct from 0 ("this farm is charged nothing").
    percent: float | None = Field(default=None, ge=0, le=100)


class FarmPayoutRequest(_CamelModel):
    reference: str = Field(default="", max_length=120)
    note: str = Field(default="", max_length=500)
    # The amount the operator saw on screen. A mismatch means the balance moved
    # under them, and the payout is refused rather than silently paying a
    # different number than the one approved.
    expected_payout_minor: int | None = Field(default=None, ge=0)


@router.get("/revenue")
async def farm_revenue_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.view"))],
) -> Any:
    return await farm_revenue_summary(db, actor=principal)


@router.get("/revenue/payouts")
async def farm_payouts_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> Any:
    return await list_payouts(db, limit=limit, actor=principal)


@router.get("/revenue/farms/{farm_id}")
async def farm_revenue_detail_endpoint(
    farm_id: str,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.view"))],
) -> Any:
    return await farm_revenue_detail(db, farm_id, actor=principal)


@router.patch("/revenue/commission")
async def set_default_commission_endpoint(
    payload: DefaultCommissionRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.manage"))],
) -> Any:
    return await set_default_commission(
        db, principal, _request_id(request), percent=payload.percent
    )


@router.patch("/revenue/farms/{farm_id}/commission")
async def set_farm_commission_endpoint(
    farm_id: str,
    payload: FarmCommissionRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.manage"))],
) -> Any:
    return await set_farm_commission(
        db, principal, _request_id(request), farm_id=farm_id, percent=payload.percent
    )


@router.post("/revenue/farms/{farm_id}/payouts")
async def issue_farm_payout_endpoint(
    farm_id: str,
    payload: FarmPayoutRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("revenue.manage"))],
) -> Any:
    """Record a payout settling every outstanding line for this farm.

    This writes the ledger entry and marks the lines paid; it does not move
    money — no disbursement rail is configured (see `services/revenue.py`).
    The operator transfers out of band and files the reference.
    """
    return await issue_farm_payout(
        db,
        principal,
        _request_id(request),
        farm_id=farm_id,
        reference=payload.reference,
        note=payload.note,
        expected_payout_minor=payload.expected_payout_minor,
    )

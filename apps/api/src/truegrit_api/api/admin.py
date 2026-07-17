"""Admin endpoints. Every route enforces a permission — UI hiding is not authorization."""

from __future__ import annotations

import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_staff, get_database, require_permission
from truegrit_api.auth.passwords import password_hash_iterations, verify_password
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.auth.sessions import end_session, hash_token, start_session
from truegrit_api.config import Settings, get_settings
from truegrit_api.domain.blocks import validate_href
from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import (
    AuthenticationError,
    NotFoundError,
    PermissionDeniedError,
    ValidationAppError,
)
from truegrit_api.platform.database import Database
from truegrit_api.repositories.admin import AdminRepository
from truegrit_api.repositories.content import (
    AuditRepository,
    CategoryRepository,
    SiteDocumentRepository,
)
from truegrit_api.services.access import (
    adopt_bootstrap_owner,
    change_own_password,
    create_farm_owner,
    create_user,
    delete_users,
    invite_user,
    reset_farm_owner_password,
    set_role_permissions,
    set_user_roles,
    set_user_status,
)
from truegrit_api.services.audit import audit_statement
from truegrit_api.services.catalogue import (
    archive_category,
    archive_product,
    create_category,
    create_product,
    set_highlighted_products,
    set_product_links,
    set_product_release,
    update_category,
    update_product,
)
from truegrit_api.services.contact import contactable_email
from truegrit_api.services.email import send_email
from truegrit_api.services.inventory import adjust_inventory, clear_inventory_levels
from truegrit_api.services.media import save_image_bytes, save_image_upload
from truegrit_api.services.orders import update_order_status
from truegrit_api.services.password_reset import (
    confirm_password_reset,
    request_password_reset,
    request_staff_invitation_email,
    request_staff_password_reset_for_user,
)
from truegrit_api.services.publishing import publish_category, publish_product
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
    stored_hash = await _stored_password_hash(db, user["id"]) if user is not None else None
    credential_ok = stored_hash is not None and verify_password(
        payload.password, stored_hash, max_iterations=settings.pbkdf2_verify_max_iterations
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
    return {
        "id": principal.user_id,
        "displayName": principal.display_name,
        "email": principal.email,
        "permissions": sorted(principal.permissions),
        "farmId": principal.farm_id,
        "farmName": farm_name,
    }


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
    announcement_active: bool | None = None
    announcement_message: str | None = Field(default=None, max_length=220)
    announcement_path: str | None = Field(default=None, max_length=200)
    hero_eyebrow: str | None = Field(default=None, max_length=120)
    hero_heading: str | None = Field(default=None, max_length=160)
    hero_text: str | None = Field(default=None, max_length=500)
    hero_image_url: str | None = Field(default=None, max_length=1000)
    hero_image_alt: str | None = Field(default=None, max_length=200)
    hero_slides: list[SiteControlHeroSlide] | None = Field(default=None, max_length=8)
    primary_action_label: str | None = Field(default=None, max_length=80)
    primary_action_href: str | None = Field(default=None, max_length=200)
    secondary_action_label: str | None = Field(default=None, max_length=80)
    secondary_action_href: str | None = Field(default=None, max_length=200)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)

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


async def _require_owner(db: Database, principal: Principal) -> None:
    row = await db.fetch_one(
        """
        SELECT 1 AS ok
        FROM user_roles ur
        JOIN roles r ON r.id = ur.role_id
        WHERE ur.user_id = ? AND r.key = 'super_admin'
        LIMIT 1
        """,
        (principal.user_id,),
    )
    if row is None:
        raise PermissionDeniedError("Only the owner can manage global site documents.")


def _normalize_hero_slides(slides: Any) -> list[dict[str, Any]]:
    if not isinstance(slides, list):
        return []
    normalized = []
    for slide in slides[:8]:
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
    announcement = await db.fetch_one(
        "SELECT message, destination_path, active FROM announcements"
        " ORDER BY active DESC, updated_at DESC LIMIT 1"
    )
    hero = _home_hero(page)["props"]
    slides = _normalize_hero_slides(hero.get("slides"))
    primary_slide = slides[0] if slides else {}
    primary = hero.get("primaryAction") or {}
    secondary = hero.get("secondaryAction") or {}
    return {
        "announcementActive": bool(announcement["active"]) if announcement else False,
        "announcementMessage": announcement["message"] if announcement else "",
        "announcementPath": announcement["destination_path"] if announcement else "",
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
    }


@router.patch("/site-control")
async def update_site_control(
    payload: SiteControlUpdate,
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
    content = json.loads(page["content_json"])
    blocks = content.setdefault("blocks", [])
    hero = next((block for block in blocks if block.get("type") == "hero"), None)
    if hero is None:
        hero = {"id": "blk_hero", "type": "hero", "version": 1, "enabled": True, "props": {}}
        blocks.insert(0, hero)
    props = hero.setdefault("props", {})

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
    if {
        "announcement_active",
        "announcement_message",
        "announcement_path",
    } & set(fields):
        existing = await db.fetch_one(
            "SELECT id FROM announcements ORDER BY updated_at DESC LIMIT 1"
        )
        if existing:
            await db.execute(
                """
                UPDATE announcements
                SET active = COALESCE(?, active),
                    message = COALESCE(?, message),
                    destination_path = COALESCE(?, destination_path),
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    int(fields["announcement_active"]) if "announcement_active" in fields else None,
                    fields.get("announcement_message"),
                    fields.get("announcement_path"),
                    now,
                    existing["id"],
                ),
            )
    return await get_site_control(db, principal)


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
                    json.dumps({"blocks": payload.blocks}, separators=(",", ":")),
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


@router.get("/archive")
async def list_archive_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(get_current_staff)],
) -> Any:
    if not _can_view_archive(principal):
        raise PermissionDeniedError()

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
            ORDER BY COALESCE(p.archived_at, p.updated_at) DESC, p.name
            LIMIT 100
            """,
            (principal.farm_id, principal.farm_id),
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
            WHERE c.archived_at IS NOT NULL OR c.status = 'archived'
            ORDER BY COALESCE(c.archived_at, c.updated_at) DESC, c.name
            LIMIT 100
            """
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
            ORDER BY f.updated_at DESC, f.name
            LIMIT 100
            """
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
            WHERE p.archived_at IS NOT NULL OR p.status = 'archived'
            ORDER BY COALESCE(p.archived_at, p.updated_at) DESC, p.slug
            LIMIT 100
            """
        )
        items.extend(_archive_row("page", row) for row in page_rows)

    items.sort(key=lambda item: item["archivedAt"], reverse=True)
    return {"items": items}


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
    _principal: Annotated[Principal, Depends(require_permission("media.upload"))],
    filename: Annotated[str | None, Query(min_length=1, max_length=180)] = None,
) -> Any:
    content_type = (request.headers.get("content-type") or "").split(";", 1)[0].lower()
    if content_type == "application/json":
        payload = ImageUploadRequest.model_validate(await request.json())
        saved = await save_image_upload(
            request.app.state.media,
            content_type=payload.content_type,
            data_base64=payload.data_base64,
        )
    else:
        # Browser uploads use the raw File body. Avoid base64 JSON here: in
        # Python Workers that path burns enough CPU for real photos to be
        # terminated before CORS headers are written.
        _ = filename
        saved = await save_image_bytes(
            request.app.state.media,
            content_type=content_type,
            data=await request.body(),
        )
    base_url = str(request.base_url).rstrip("/")
    return {"id": saved["id"], "url": f"{base_url}{saved['path']}"}


@router.get("/products")
async def list_products(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("products.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AdminRepository(db).list_products(
        limit=limit, offset=offset, farm_id=principal.farm_id
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
) -> Any:
    rows = await AdminRepository(db).list_categories(limit=limit, offset=offset)
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
) -> Any:
    rows = await AdminRepository(db).list_inventory(
        limit=limit, offset=offset, farm_id=principal.farm_id
    )
    return {
        "items": [
            {
                "variantId": row["variant_id"],
                "productName": row["product_name"],
                "variantName": row["variant_name"],
                "sku": row["sku"],
                "locationName": row["location_name"],
                "onHand": row["on_hand"],
                "reserved": row["reserved"],
                "reorderThreshold": row["reorder_threshold"],
                "updatedAt": row["updated_at"],
            }
            for row in rows
        ],
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit")
async def audit_log(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("audit.view"))],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> Any:
    rows = await AuditRepository(db).recent(limit=limit)
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
        ]
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
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    image_url: str | None = Field(default=None, max_length=1000)
    image_alt: str | None = Field(default=None, max_length=200)
    release_scope: str | None = Field(default=None, max_length=16)
    release_countries: list[str] | None = Field(default=None, max_length=100)
    linked_product_ids: list[str] | None = Field(default=None, max_length=12)


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
    return {
        "id": detail["id"],
        "name": detail["name"],
        "slug": detail["slug"],
        "shortDescription": detail["short_description"] or "",
        "productType": detail["product_type"],
        "status": detail["status"],
        "farmName": detail["farm_name"],
        "seoTitle": detail["seo_title"] or "",
        "seoDescription": detail["seo_description"] or "",
        "imageUrl": detail["image_url"] or "",
        "imageAlt": detail["image_alt"] or detail["name"],
        "updatedAt": detail["updated_at"],
        "releaseScope": detail["release_scope"],
        "releaseCountries": detail["release_countries"],
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
    return await update_category(db, principal, _request_id(request), category_id, fields=fields)


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
) -> Any:
    rows = await AdminRepository(db).list_users()
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
        ]
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
                "permissionKeys": row["permission_keys"].split(",") if row["permission_keys"] else [],
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
            {"id": row["id"], "key": row["key"], "description": row["description"]}
            for row in rows
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


@router.get("/contact-messages")
async def list_contact_messages_endpoint(
    db: Annotated[Database, Depends(get_database)],
    principal: Annotated[Principal, Depends(require_permission("users.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Any:
    if principal.farm_id is not None:
        raise PermissionDeniedError("Only main admins can view contact attempts.")
    rows = await db.fetch_all(
        """
        SELECT id, name, email, subject, message, status, created_at, handled_at
        FROM contact_messages
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "email": row["email"],
                "subject": row["subject"],
                "message": row["message"],
                "status": row["status"],
                "createdAt": row["created_at"],
                "handledAt": row["handled_at"],
            }
            for row in rows
        ]
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
    if email is not None:
        send_email(email.to, email.subject, email.body, settings, email.html_body)
    return {**result, "emailSent": email is not None}


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
    send_email(email.to, email.subject, email.body, settings, email.html_body)
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
                    "resetEmailSent": True,
                    "passwordStored": False,
                },
            )
        ]
    )
    return {"id": user_id, "email": user["email"], "emailSent": True}


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------


class OrderStatusRequest(_CamelModel):
    status: str = Field(max_length=32)


@router.get("/orders")
async def list_orders_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("orders.view"))],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    rows = await AdminRepository(db).list_orders(limit=limit, offset=offset)
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
    _principal: Annotated[Principal, Depends(require_permission("orders.view"))],
) -> Any:
    order = await AdminRepository(db).get_order_detail(order_id)
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


class FarmUpdateRequest(_CamelModel):
    name: str | None = Field(default=None, min_length=3, max_length=140)
    slug: str | None = Field(default=None, max_length=140)
    farmer_name: str | None = Field(default=None, max_length=140)
    region: str | None = Field(default=None, max_length=180)
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    established_year: int | None = Field(default=None, ge=1800, le=2100)
    summary: str | None = Field(default=None, max_length=500)
    status: str | None = Field(default=None, max_length=24)


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
    }


@router.get("/farms")
async def list_farms_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("users.view"))],
) -> Any:
    rows = await db.fetch_all(
        """
        SELECT f.id, f.name, f.slug, f.farmer_name, f.region, f.country_code,
               f.story_json, f.established_year, f.status, f.updated_at,
               (SELECT COUNT(*) FROM products p
                 WHERE p.farm_id = f.id AND p.archived_at IS NULL) AS product_count
        FROM farms f
        WHERE f.status != 'archived'
        ORDER BY f.name
        """
    )
    return {"items": [_farm_response(row) for row in rows]}


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
                  created_at, created_by, updated_at, updated_by
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

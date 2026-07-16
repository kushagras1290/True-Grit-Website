"""Admin endpoints. Every route enforces a permission — UI hiding is not authorization."""

from __future__ import annotations

import hmac
import json
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_staff, get_database, require_permission
from truegrit_api.auth.passwords import verify_password
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import (
    RateLimitRule,
    client_ip,
    enforce_rate_limit,
    hash_identifier,
)
from truegrit_api.auth.sessions import end_session, hash_token, start_session
from truegrit_api.config import Settings, get_settings
from truegrit_api.errors import AuthenticationError, NotFoundError, PermissionDeniedError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.admin import AdminRepository
from truegrit_api.repositories.content import AuditRepository, CategoryRepository
from truegrit_api.services.access import (
    adopt_bootstrap_owner,
    change_own_password,
    create_farm_owner,
    delete_users,
    invite_user,
    reset_farm_owner_password,
    set_user_roles,
    set_user_status,
)
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
from truegrit_api.services.inventory import adjust_inventory
from truegrit_api.services.media import save_image_upload
from truegrit_api.services.orders import update_order_status
from truegrit_api.services.password_reset import confirm_password_reset, request_password_reset
from truegrit_api.services.publishing import publish_category, publish_product
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
    credential_ok = stored_hash is not None and verify_password(payload.password, stored_hash)

    # The `.env` credential is a bootstrap, not a permanent key: it opens the
    # owner account only while that account has no password of its own. The first
    # sign-in adopts it — ADMIN_LOGIN_EMAIL becomes the account's address and
    # ADMIN_LOGIN_PASSWORD becomes its stored hash — and from then on editing
    # `.env` changes nothing, because a password the console can rotate has to be
    # the only one that works. To hand the account back to `.env`, delete its row
    # from user_credentials.
    if not credential_ok and _env_credential_matches(settings, email, payload.password):
        owner = user if user is not None else await db.fetch_one(_FIRST_SUPER_ADMIN_SQL)
        if owner is not None and await _stored_password_hash(db, owner["id"]) is None:
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


class SiteControlUpdate(_CamelModel):
    announcement_active: bool | None = None
    announcement_message: str | None = Field(default=None, max_length=220)
    announcement_path: str | None = Field(default=None, max_length=200)
    hero_eyebrow: str | None = Field(default=None, max_length=120)
    hero_heading: str | None = Field(default=None, max_length=160)
    hero_text: str | None = Field(default=None, max_length=500)
    primary_action_label: str | None = Field(default=None, max_length=80)
    primary_action_href: str | None = Field(default=None, max_length=200)
    secondary_action_label: str | None = Field(default=None, max_length=80)
    secondary_action_href: str | None = Field(default=None, max_length=200)
    seo_title: str | None = Field(default=None, max_length=160)
    seo_description: str | None = Field(default=None, max_length=320)
    seo_keywords: str | None = Field(default=None, max_length=500)


class ImageUploadRequest(_CamelModel):
    filename: str = Field(min_length=1, max_length=180)
    content_type: str = Field(min_length=1, max_length=80)
    data_base64: str = Field(min_length=1)


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
    primary = hero.get("primaryAction") or {}
    secondary = hero.get("secondaryAction") or {}
    return {
        "announcementActive": bool(announcement["active"]) if announcement else False,
        "announcementMessage": announcement["message"] if announcement else "",
        "announcementPath": announcement["destination_path"] if announcement else "",
        "heroEyebrow": hero.get("eyebrow") or "",
        "heroHeading": hero.get("heading") or page["title"],
        "heroText": hero.get("text") or "",
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
    ):
        if source in fields:
            props[target] = fields[source] or ""
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
                    int(fields["announcement_active"])
                    if "announcement_active" in fields
                    else None,
                    fields.get("announcement_message"),
                    fields.get("announcement_path"),
                    now,
                    existing["id"],
                ),
            )
    return await get_site_control(db, principal)


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
    payload: ImageUploadRequest,
    request: Request,
    _principal: Annotated[Principal, Depends(require_permission("media.upload"))],
) -> Any:
    saved = await save_image_upload(
        request.app.state.media,
        content_type=payload.content_type,
        data_base64=payload.data_base64,
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
        row = await db.fetch_one(
            "SELECT release_scope FROM products WHERE id = ?", (product_id,)
        )
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


# ---------------------------------------------------------------------------
# Users & roles
# ---------------------------------------------------------------------------


class UserInviteRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    role_ids: list[str] = Field(default_factory=list)


class UserStatusRequest(_CamelModel):
    status: str = Field(max_length=16)


class UserRolesRequest(_CamelModel):
    role_ids: list[str] = Field(default_factory=list)


class UserBulkDeleteRequest(_CamelModel):
    user_ids: list[str] = Field(min_length=1, max_length=100)


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
    return await invite_user(
        db,
        principal,
        _request_id(request),
        email=payload.email,
        display_name=payload.display_name,
        role_ids=payload.role_ids,
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


class StaffResetRequest(_CamelModel):
    email: str = Field(min_length=3, max_length=254)


class StaffResetConfirm(_CamelModel):
    token: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


@router.get("/farms")
async def list_farms_endpoint(
    db: Annotated[Database, Depends(get_database)],
    _principal: Annotated[Principal, Depends(require_permission("users.view"))],
) -> Any:
    rows = await db.fetch_all("SELECT id, name FROM farms WHERE status != 'archived' ORDER BY name")
    return {"items": [{"id": row["id"], "name": row["name"]} for row in rows]}


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
    background: BackgroundTasks,
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
        background.add_task(
            send_email,
            email.to,
            email.subject,
            email.body,
            settings,
            email.html_body,
        )
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

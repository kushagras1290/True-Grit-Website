"""Public catalogue and content endpoints. Published data only — never drafts."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database
from truegrit_api.config import get_settings
from truegrit_api.domain.phone import MAX_PHONE_INPUT_LENGTH, normalize_phone
from truegrit_api.domain.slugs import MAX_SLUG_LENGTH, validate_slug
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    ArticleRepository,
    CategoryRepository,
    FarmRepository,
    NavigationRepository,
    PageRepository,
    RecipeRepository,
    RouteSeoRepository,
    SearchRepository,
    SiteDocumentRepository,
)
from truegrit_api.schemas.public import (
    ArticleDetail,
    ArticleListResponse,
    FarmDetail,
    FarmListResponse,
    ProductDetail,
    ProductListResponse,
    PublicBootstrap,
    PublicCategoryPage,
    PublicPage,
    RecipeDetail,
    RecipeListResponse,
    SearchResponse,
)
from truegrit_api.services.announcements import resolve_announcement
from truegrit_api.services.appearance import load_public_appearance
from truegrit_api.services.email import send_email
from truegrit_api.services.feature_settings import load_public_settings
from truegrit_api.services.homepage_geo import resolve_public_home
from truegrit_api.services.site_documents import (
    SITE_DOCUMENT_TYPES,
    SITEMAP_GENERATORS,
    default_site_documents,
)
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["public"])

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_COUNTRY_PATTERN = re.compile(r"^[A-Za-z]{2}$")

# Storefront grid pagination. 24 divides evenly into the grid's 2/3/4-column
# breakpoints (12/8/6 full rows); the cap keeps a single request bounded.
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 48


def _normalize_country(country: str | None) -> str | None:
    """Uppercase a two-letter ISO country code; anything else is rejected.
    Absent means \"unknown\" and no geo filtering is applied."""
    if not country:
        return None
    if not _COUNTRY_PATTERN.match(country):
        raise ValidationAppError("Country must be a two-letter ISO code.")
    return country.upper()


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ContactRequest(_CamelModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
    # Required: most of what arrives here is answered in one call and ten
    # emails, and a phone-only account (0016) has no address we could reply to
    # at all. Normalised to E.164 by the route, so it is comparable with
    # `users.phone_e164`. Rows predating migration 0045 keep NULL.
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)
    subject: str = Field(min_length=3, max_length=160)
    message: str = Field(min_length=10, max_length=2000)


_STANDARDS_FAQ = [
    {
        "question": "How do you verify these farms?",
        "answer": (
            "Every partner farm holds a current NPOP or PGS-India certificate that we verify"
            " at onboarding and re-check annually."
        ),
    },
    {
        "question": "When is my order harvested?",
        "answer": (
            "Fresh produce is harvested against confirmed orders, never stockpiled. Pantry"
            " goods show their milling or pressing date."
        ),
    },
]


@router.get("/bootstrap", response_model=PublicBootstrap)
async def bootstrap(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    navigation = NavigationRepository(db)
    # `country` (the same signal `resolveCountry()` resolves for currency,
    # catalogue release, and the appearance overrides) picks up any
    # country-specific announcement an owner has saved, falling back to the
    # site-wide one -- see `resolve_announcement`.
    return {
        "navigation": await navigation.menu("header"),
        "footer_navigation": await navigation.menu("footer"),
        "announcement": await resolve_announcement(db, country),
    }


@router.get("/settings")
async def storefront_settings(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    """Which sign-in methods and commerce features the storefront should offer.

    The owner's switches (`app_settings`, migration 0040) ANDed with what this
    deployment is actually configured for — so a `true` here always means the
    feature will work, never just that someone ticked a box. Public and
    unauthenticated: it carries no secrets, only what the account menu and
    checkout need in order to render the truth on first paint.

    The owner's colours and ambient effects ride along on the same response
    rather than a second request: the storefront needs them before the first
    byte of HTML, and a separate fetch would repaint the page in front of the
    visitor on every load. `country` (the same signal `resolveCountry()`
    already resolves for currency and catalogue release) picks up any
    per-country override an owner has saved — a Diwali palette for visitors in
    India, snow only where it snows — and folds it into `theme.global` and
    `effects` before either ever reaches the browser, so the storefront itself
    stays completely unaware that "global" was resolved per visitor.
    """
    settings, appearance = await asyncio.gather(
        load_public_settings(db, get_settings()),
        load_public_appearance(db, country),
    )
    return {**settings.to_camel_dict(), **appearance}


@router.get("/payment-methods")
async def payment_methods(db: Annotated[Database, Depends(get_database)]) -> Any:
    """Which checkout methods the storefront should offer, plus the public
    Razorpay key its widget needs. No secrets are exposed.

    With payments switched off in the admin console this reports no methods at
    all, matching what `/v1/public/checkout` will now refuse to accept — the
    storefront must never render a gateway the API would reject."""
    settings = get_settings()
    public = await load_public_settings(db, settings)
    if not public.payments:
        return {
            "methods": [],
            "currency": settings.payment_currency,
            "codMaxMinor": settings.payment_cod_max_minor,
            "razorpayKeyId": "",
            "paypalClientId": "",
            "paypalCurrency": "",
        }
    return {
        "methods": settings.enabled_payment_methods,
        "currency": settings.payment_currency,
        "codMaxMinor": settings.payment_cod_max_minor,
        "razorpayKeyId": settings.razorpay_key_id if settings.razorpay_enabled else "",
        # Public client id only — the secret never leaves the API. PayPal is the
        # international lane, so the storefront also needs the currency an
        # overseas buyer will actually be charged in (never INR).
        "paypalClientId": settings.paypal_client_id if settings.paypal_enabled else "",
        "paypalCurrency": settings.paypal_currency.upper() if settings.paypal_enabled else "",
    }


@router.get("/home")
async def home(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    page = await resolve_public_home(db, country)
    if page is None:
        raise NotFoundError("Homepage is not published.")
    return page


@router.get("/pages/{slug}", response_model=PublicPage)
async def public_page(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    page = await PageRepository(db).get_published_by_slug(slug)
    if page is None:
        raise NotFoundError("Page is not published.")
    return page


@router.get("/site-documents/{key}")
async def site_document(key: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    if key not in {"robots_txt", "sitemap_xml", "llms_txt"}:
        raise NotFoundError("Site document not found.")
    document = await SiteDocumentRepository(db).get(key)
    if document is None:
        document = (await default_site_documents(db, get_settings()))[key]
    return {
        "key": document["key"],
        "content": document["content"],
        "contentType": document["content_type"],
        "updatedAt": document["updated_at"],
    }


@router.get("/route-seo")
async def route_seo(
    db: Annotated[Database, Depends(get_database)],
    path: Annotated[str, Query(min_length=1, max_length=200)],
) -> Any:
    """SEO override for a storefront route that isn't backed by a CMS page
    (e.g. `/blog/submit`) — see `RouteSeoRepository`. A missing row means the
    caller should fall back to its own hardcoded metadata."""
    override = await RouteSeoRepository(db).get(path)
    if override is None:
        raise NotFoundError("No SEO override for this route.")
    return {
        "path": override["path"],
        "seoTitle": override["seo_title"],
        "seoDescription": override["seo_description"],
        "seoKeywords": override["seo_keywords"],
        "indexingPolicy": override["indexing_policy"],
        "updatedAt": override["updated_at"],
    }


@router.get("/sitemaps/{kind}")
async def sitemap_kind(kind: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    """Per-type sitemap files linked from the sitemap index. Always
    mechanically generated from live D1 content — unlike `sitemap_xml` above,
    there is no owner-override path here, so these can never go stale behind
    a forgotten manual edit."""
    generator = SITEMAP_GENERATORS.get(kind)
    if generator is None:
        raise NotFoundError("Sitemap not found.")
    xml = await generator(db, get_settings())
    return Response(content=xml, media_type=SITE_DOCUMENT_TYPES["sitemap_xml"])


@router.post("/contact")
async def contact(
    payload: ContactRequest,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    email = payload.email.strip().lower()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationAppError("Enter a valid email address.")
    # Raises ValidationAppError with a message naming the expected format, so a
    # mistyped number is corrected rather than silently stored unringable.
    phone = normalize_phone(payload.phone)

    now = utc_now_iso()
    message_id = new_id("msg")
    await db.execute(
        """
        INSERT INTO contact_messages
          (id, name, email, phone_e164, subject, message, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'new', ?)
        """,
        (
            message_id,
            payload.name.strip(),
            email,
            phone,
            payload.subject.strip(),
            payload.message.strip(),
            now,
        ),
    )
    settings = get_settings()
    to = settings.contact_recipient_email or settings.admin_login_email
    background.add_task(
        send_email,
        to,
        f"Contact form: {payload.subject.strip()}",
        (
            f"Name: {payload.name.strip()}\nEmail: {email}\nPhone: {phone}\n\n"
            f"{payload.message.strip()}"
        ),
        settings,
    )
    return {"ok": True, "id": message_id}


@router.get("/categories/{slug}", response_model=PublicCategoryPage)
async def category_page(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    validate_slug(slug)
    visitor_country = _normalize_country(country)
    category = await CategoryRepository(db).get_published_by_slug(slug, country=visitor_country)
    if category is None:
        raise NotFoundError("Category not found.")

    catalogue = CatalogueRepository(db)
    rule_json = category["product_rule_json"]
    if category["product_assignment_mode"] in {"dynamic", "hybrid"} and rule_json:
        products, products_total = await catalogue.list_published_by_rule(
            json.loads(rule_json), country=visitor_country, limit=limit, offset=offset
        )
    else:
        products, products_total = await catalogue.list_published_by_category(
            category["id"], country=visitor_country, limit=limit, offset=offset
        )
    subcategories = await CategoryRepository(db).list_published_children(
        category["id"], country=visitor_country
    )

    return {
        "id": category["id"],
        "name": category["name"],
        "slug": category["slug"],
        # A subcategory sits under its department, so the trail names it. The
        # department link filters the shop grid rather than pointing at the
        # department page, matching where the visitor came from.
        "breadcrumbs": [
            {"label": "Home", "path": "/"},
            {"label": "Shop", "path": "/shop"},
            *(
                [
                    {
                        "label": category["parent_name"],
                        "path": f"/shop?category={category['parent_slug']}",
                    }
                ]
                if category["parent_name"]
                else []
            ),
            {"label": category["name"], "path": f"/category/{category['slug']}"},
        ],
        "theme_key": category["theme_key"] or "forest",
        "hero": {
            "eyebrow": category["hero_eyebrow"] or "",
            "title": category["hero_title"] or category["name"],
            "description": category["hero_description"] or category["short_description"] or "",
            "season_label": category["season_label"],
            "image_url": category["hero_image_url"],
            "image_alt": category["hero_image_alt"] or category["name"],
        },
        "subcategories": [_category_summary(row) for row in subcategories],
        "products": products,
        "products_total": products_total,
        "faq": _STANDARDS_FAQ,
        "seo": {
            "title": category["seo_title"] or f"{category['name']} — True Grit",
            "description": category["seo_description"] or category["short_description"] or "",
            "canonical_path": f"/category/{category['slug']}",
            "indexing": "index",
        },
        "updated_at": category["updated_at"],
    }


def _category_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Row -> `CategorySummary`. `parentId` and `level` let the storefront group
    the flat list into departments and subcategories in one request."""
    return {
        "id": row["id"],
        "name": row["name"],
        "slug": row["slug"],
        "shortDescription": row["short_description"] or "",
        "themeKey": row["theme_key"] or "forest",
        "seasonLabel": row["season_label"],
        "imageUrl": row["hero_image_url"],
        "productCount": row["product_count"],
        "parentId": row["parent_id"],
        "level": row["level"] or 0,
    }


@router.get("/categories")
async def categories(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    """Every published category in tree order — departments each followed by
    their own subcategories. Returned flat rather than nested so a single
    response serves both the shop sidebar and the department rail."""
    rows = await CategoryRepository(db).list_published(country=_normalize_country(country))
    return {"items": [_category_summary(row) for row in rows]}


@router.get("/farms", response_model=FarmListResponse)
async def farms_list(db: Annotated[Database, Depends(get_database)]) -> Any:
    return {"items": await FarmRepository(db).list_published()}


@router.get("/farms/{slug}", response_model=FarmDetail)
async def farm_detail(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    farm = await FarmRepository(db).get_published_by_slug(slug)
    if farm is None:
        raise NotFoundError("Farm not found.")
    return farm


@router.get("/recipes", response_model=RecipeListResponse)
async def recipes_list(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    repository = RecipeRepository(db)
    return {
        "items": await repository.list_published(limit=limit, offset=offset),
        "total": await repository.count_published(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/recipes/{slug}", response_model=RecipeDetail)
async def recipe_detail(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    recipe = await RecipeRepository(db).get_published_by_slug(slug)
    if recipe is None:
        raise NotFoundError("Recipe not found.")
    return recipe


@router.get("/articles", response_model=ArticleListResponse)
async def articles_list(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    repository = ArticleRepository(db)
    return {
        "items": await repository.list_published(limit=limit, offset=offset),
        "total": await repository.count_published(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/articles/{slug}", response_model=ArticleDetail)
async def article_detail(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    article = await ArticleRepository(db).get_published_by_slug(slug)
    if article is None:
        raise NotFoundError("Article not found.")
    return article


@router.get("/products", response_model=ProductListResponse)
async def products_list(
    db: Annotated[Database, Depends(get_database)],
    slugs: Annotated[str | None, Query(max_length=4000)] = None,
    category: Annotated[str | None, Query(max_length=MAX_SLUG_LENGTH)] = None,
    country: Annotated[str | None, Query(max_length=2)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """Published products for storefront grids.

    With `?slugs=a,b,c` returns exactly those, in the given order (home-page
    product collections) — `limit`/`offset` do not apply, since that request
    is already a bounded, exact set. Without it, a page of published products,
    newest first (the shop grid), windowed by `limit`/`offset`; `total` is the
    full published count so the caller can compute page numbers.

    `?category=<slug>` narrows the grid to one department or subcategory, for
    the shop page's in-place sidebar filter. An unknown, unpublished or
    geo-excluded slug yields an empty page rather than the unfiltered
    catalogue, so a filter can never silently widen what is visible. `slugs`
    takes precedence — it is already an exact set.

    `?country=XX` hides products not released in that country. Declared before
    `/products/{slug}` so the literal path wins.
    """
    visitor_country = _normalize_country(country)
    catalogue = CatalogueRepository(db)
    if slugs is not None:
        wanted = [slug.strip() for slug in slugs.split(",") if slug.strip()][:200]
        items = (
            await catalogue.list_published_by_slugs(wanted, country=visitor_country)
            if wanted
            else []
        )
        total = len(items)
    elif category is not None:
        validate_slug(category)
        category_id = await CategoryRepository(db).get_published_id_by_slug(
            category, country=visitor_country
        )
        if category_id is None:
            return {"items": [], "total": 0}
        items, total = await catalogue.list_published_by_category(
            category_id, country=visitor_country, limit=limit, offset=offset
        )
    else:
        items, total = await catalogue.list_all_published(
            limit=limit, offset=offset, country=visitor_country
        )
    return {"items": items, "total": total}


@router.get("/highlights", response_model=ProductListResponse)
async def highlighted_products(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    """The owner-curated highlight slots (search page box), curated order."""
    items = await CatalogueRepository(db).list_highlighted(country=_normalize_country(country))
    return {"items": items, "total": len(items)}


@router.get("/products/{slug}", response_model=ProductDetail)
async def product_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    validate_slug(slug)
    detail = await CatalogueRepository(db).get_published_detail(
        slug, country=_normalize_country(country)
    )
    if detail is None:
        raise NotFoundError("Product not found.")
    return detail


@router.get("/search", response_model=SearchResponse)
async def search(
    db: Annotated[Database, Depends(get_database)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
    country: Annotated[str | None, Query(max_length=2)] = None,
) -> Any:
    return await SearchRepository(db).search(q, country=_normalize_country(country))

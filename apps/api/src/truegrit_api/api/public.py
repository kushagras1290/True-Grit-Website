"""Public catalogue and content endpoints. Published data only — never drafts."""

from __future__ import annotations

import asyncio
import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database
from truegrit_api.config import get_settings
from truegrit_api.domain.phone import MAX_PHONE_INPUT_LENGTH, normalize_phone
from truegrit_api.domain.slugs import MAX_SLUG_LENGTH, validate_slug
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.bundles import BundleRepository
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    ArticleRepository,
    CategoryRepository,
    FarmRepository,
    NavigationRepository,
    PageRepository,
    RecipeRepository,
    ReviewRepository,
    RouteSeoRepository,
    SearchRepository,
    SiteDocumentRepository,
)
from truegrit_api.repositories.entity_translations import EntityTranslationRepository
from truegrit_api.repositories.promotions import PromotionRepository
from truegrit_api.schemas.public import (
    ArticleDetail,
    ArticleListResponse,
    FarmDetail,
    FarmListResponse,
    GiftCardBalanceResponse,
    ProductDetail,
    ProductFiltersResponse,
    ProductListResponse,
    PublicBootstrap,
    PublicCategoryPage,
    PublicPage,
    RecipeDetail,
    RecipeListResponse,
    SearchResponse,
)
from truegrit_api.services import support_bot_settings
from truegrit_api.services.announcements import resolve_announcement
from truegrit_api.services.appearance import load_public_appearance
from truegrit_api.services.feature_settings import (
    gift_cards_enabled,
    load_curated_max_items,
    load_delivery_settings,
    load_public_settings,
    load_subscription_discount_percent,
    promotions_enabled,
    recommendations_enabled,
)
from truegrit_api.services.gift_cards import get_balance_by_code
from truegrit_api.services.homepage_geo import resolve_public_home
from truegrit_api.services.jobs import enqueue_email
from truegrit_api.services.site_documents import (
    SITE_DOCUMENT_TYPES,
    SITEMAP_GENERATORS,
    default_site_document,
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
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    navigation = NavigationRepository(db)
    # `country` (the same signal `resolveCountry()` resolves for currency,
    # catalogue release, and the appearance overrides) picks up any
    # country-specific announcement an owner has saved, falling back to the
    # site-wide one -- see `resolve_announcement`.
    return {
        "navigation": await navigation.menu("header", locale=locale),
        "footer_navigation": await navigation.menu("footer", locale=locale),
        "announcement": await resolve_announcement(db, country, locale=locale),
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
    (
        settings,
        appearance,
        support_bot_color,
        support_bot_storefront_enabled,
        support_bot_admin_enabled,
    ) = await asyncio.gather(
        load_public_settings(db, get_settings()),
        load_public_appearance(db, country),
        # Rides along for the same reason the colours above do: the chat
        # widget renders on first paint, and a second request would repaint it
        # in front of the visitor. Also the only source the admin panel's own
        # widget can read -- /v1/admin/support-bot/settings is
        # `support_bot.manage`-gated, and the widget is shown to every staff
        # member. A colour carries nothing sensitive.
        support_bot_settings.get_widget_color(db),
        # Enabled state rides along too, for the same reason: without it,
        # both widgets rendered their floating launcher unconditionally and
        # only found out the bot was off when a message actually failed to
        # send, instead of the button never appearing at all.
        support_bot_settings.is_enabled(db, "storefront"),
        support_bot_settings.is_enabled(db, "admin"),
    )
    return {
        **settings.to_camel_dict(),
        **appearance,
        "supportBotColor": support_bot_color,
        "supportBotStorefrontEnabled": support_bot_storefront_enabled,
        "supportBotAdminEnabled": support_bot_admin_enabled,
    }


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


@router.get("/delivery-settings")
async def delivery_settings(db: Annotated[Database, Depends(get_database)]) -> Any:
    """The delivery fee and free-delivery subtotal threshold checkout will
    charge against. Admin-editable (`load_delivery_settings`), so the
    storefront's order summary reads it here rather than hardcoding a figure
    that would silently drift from what checkout actually applies."""
    settings = await load_delivery_settings(db)
    return {"feeMinor": settings.fee_minor, "freeThresholdMinor": settings.free_threshold_minor}


@router.get("/subscription-settings")
async def subscription_settings(db: Annotated[Database, Depends(get_database)]) -> Any:
    """The percent-off Subscribe & Save advertises on a product page. Read
    regardless of whether the feature is currently switched on -- gating that
    is `storefrontSettings.subscriptions` (site-settings), read once at the
    root loader; this only ever answers "how much", never "whether"."""
    return {"discountPercent": await load_subscription_discount_percent(db)}


@router.get("/home")
async def home(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    page = await resolve_public_home(db, country, locale)
    if page is None:
        raise NotFoundError("Homepage is not published.")
    return page


@router.get("/pages/{slug}", response_model=PublicPage)
async def public_page(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    page = await PageRepository(db).get_published_by_slug(slug, locale=locale)
    if page is None:
        raise NotFoundError("Page is not published.")
    return page


@router.get("/site-documents/{key}")
async def site_document(key: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    if key not in {"robots_txt", "sitemap_xml", "llms_txt"}:
        raise NotFoundError("Site document not found.")
    document = await SiteDocumentRepository(db).get(key)
    if document is None:
        document = await default_site_document(db, get_settings(), key)
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
    await enqueue_email(
        db,
        dedupe_key=f"contact:{message_id}:staff",
        to=to,
        subject=f"Contact form: {payload.subject.strip()}",
        body=(
            f"Name: {payload.name.strip()}\nEmail: {email}\nPhone: {phone}\n\n"
            f"{payload.message.strip()}"
        ),
        aggregate_type="contact_message",
        aggregate_id=message_id,
        category="contact_form",
    )
    return {"ok": True, "id": message_id}


@router.get("/categories/{slug}", response_model=PublicCategoryPage)
async def category_page(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    validate_slug(slug)
    visitor_country = _normalize_country(country)
    category = await CategoryRepository(db).get_published_by_slug(
        slug, country=visitor_country, locale=locale
    )
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
        category["id"], country=visitor_country, locale=locale
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
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    """Every published category in tree order — departments each followed by
    their own subcategories. Returned flat rather than nested so a single
    response serves both the shop sidebar and the department rail."""
    rows = await CategoryRepository(db).list_published(
        country=_normalize_country(country), locale=locale
    )
    return {"items": [_category_summary(row) for row in rows]}


@router.get("/farms", response_model=FarmListResponse)
async def farms_list(
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    return {"items": await FarmRepository(db).list_published(locale=locale)}


@router.get("/farms/{slug}", response_model=FarmDetail)
async def farm_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    farm = await FarmRepository(db).get_published_by_slug(slug, locale=locale)
    if farm is None:
        raise NotFoundError("Farm not found.")
    return farm


@router.get("/recipes", response_model=RecipeListResponse)
async def recipes_list(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 12,
    offset: Annotated[int, Query(ge=0)] = 0,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    repository = RecipeRepository(db)
    return {
        "items": await repository.list_published(limit=limit, offset=offset, locale=locale),
        "total": await repository.count_published(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/recipes/{slug}", response_model=RecipeDetail)
async def recipe_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    recipe = await RecipeRepository(db).get_published_by_slug(slug, locale=locale)
    if recipe is None:
        raise NotFoundError("Recipe not found.")
    return recipe


@router.get("/articles", response_model=ArticleListResponse)
async def articles_list(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
    offset: Annotated[int, Query(ge=0)] = 0,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    repository = ArticleRepository(db)
    return {
        "items": await repository.list_published(limit=limit, offset=offset, locale=locale),
        "total": await repository.count_published(),
        "limit": limit,
        "offset": offset,
    }


@router.get("/articles/{slug}", response_model=ArticleDetail)
async def article_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    article = await ArticleRepository(db).get_published_by_slug(slug, locale=locale)
    if article is None:
        raise NotFoundError("Article not found.")
    return article


@router.get("/filters", response_model=ProductFiltersResponse)
async def product_filters(db: Annotated[Database, Depends(get_database)]) -> Any:
    """The full dietary-tag and certification vocabulary for the shop grid's
    filter checkboxes -- see `?diet=`/`?certification=` on `/products`."""
    return await CatalogueRepository(db).list_filter_facets()


@router.get("/gift-cards/{code}", response_model=GiftCardBalanceResponse)
async def gift_card_balance(code: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    """Balance lookup for a code a customer already holds -- no sign-in
    required, since a gift card can be issued to someone with no account yet.
    Returns balanceMinor: 0 for a cancelled/expired card rather than the
    stale value it had while active, so a spent-out or dead card never
    displays money that is not actually redeemable."""
    if not await gift_cards_enabled(db):
        raise ValidationAppError("Gift cards are not available right now.")
    return await get_balance_by_code(db, code)


@router.get("/products", response_model=ProductListResponse)
async def products_list(
    db: Annotated[Database, Depends(get_database)],
    slugs: Annotated[str | None, Query(max_length=4000)] = None,
    category: Annotated[str | None, Query(max_length=MAX_SLUG_LENGTH)] = None,
    diet: Annotated[str | None, Query(max_length=500)] = None,
    certification: Annotated[str | None, Query(max_length=500)] = None,
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
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

    `?diet=vegan,gluten-free` and `?certification=india-organic,pgs-india`
    each narrow further, OR-within-facet (either tag/cert matches) and
    AND-across-facets (combined with `category` and with each other) —
    ignored entirely when `slugs` is set, same as `category`.

    `?country=XX` hides products not released in that country. Declared before
    `/products/{slug}` so the literal path wins.
    """
    visitor_country = _normalize_country(country)
    catalogue = CatalogueRepository(db)
    diet_keys = [key.strip() for key in (diet or "").split(",") if key.strip()][:50]
    cert_slugs = [slug.strip() for slug in (certification or "").split(",") if slug.strip()][:50]
    if slugs is not None:
        wanted = [slug.strip() for slug in slugs.split(",") if slug.strip()][:200]
        items = (
            await catalogue.list_published_by_slugs(wanted, country=visitor_country, locale=locale)
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
            category_id,
            country=visitor_country,
            limit=limit,
            offset=offset,
            locale=locale,
            diet_keys=diet_keys,
            certification_slugs=cert_slugs,
        )
    else:
        items, total = await catalogue.list_all_published(
            limit=limit,
            offset=offset,
            country=visitor_country,
            locale=locale,
            diet_keys=diet_keys,
            certification_slugs=cert_slugs,
        )
    return {"items": items, "total": total}


@router.get("/highlights", response_model=ProductListResponse)
async def highlighted_products(
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    """The owner-curated highlight slots (search page box), curated order."""
    limit = await load_curated_max_items(db)
    items = await CatalogueRepository(db).list_highlighted(
        country=_normalize_country(country), limit=limit, locale=locale
    )
    return {"items": items, "total": len(items)}


@router.get("/recommendations/bestsellers", response_model=ProductListResponse)
async def bestsellers(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
    exclude: Annotated[str | None, Query(max_length=2000)] = None,
    category: Annotated[str | None, Query(max_length=140)] = None,
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    """Real sellers, ranked by quantity actually sold on non-cancelled
    orders -- not a curated list, so there is nothing here for an editor to
    keep stocked. Backs the homepage `recommendations` block and, with
    `exclude` (a comma-separated slug list), the basket page's "you might
    also like" row -- dropping whatever is already in the basket. Empty while
    the sitewide switch is off."""
    if not await recommendations_enabled(db):
        return {"items": [], "total": 0}
    exclude_slugs = (
        [entry.strip() for entry in exclude.split(",") if entry.strip()] if exclude else None
    )
    items = await CatalogueRepository(db).list_bestsellers(
        limit=limit,
        exclude_slugs=exclude_slugs,
        category_slug=category,
        country=_normalize_country(country),
        locale=locale,
    )
    return {"items": items, "total": len(items)}


@router.get("/products/{slug}/also-bought", response_model=ProductListResponse)
async def also_bought(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=24)] = 6,
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    """Products that show up in the same orders as this one, most frequent
    first -- real co-purchase counts, not a curated "goes well with" list
    (that is `product.relatedSlugs`, a separate signal). Empty for a product
    with no order history yet, or while the sitewide switch is off."""
    if not await recommendations_enabled(db):
        return {"items": [], "total": 0}
    validate_slug(slug)
    visitor_country = _normalize_country(country)
    repository = CatalogueRepository(db)
    product = await repository.get_published_detail(slug, country=visitor_country)
    if product is None:
        raise NotFoundError("Product not found.")
    items = await repository.list_also_bought(
        product["id"], limit=limit, country=visitor_country, locale=locale
    )
    return {"items": items, "total": len(items)}


@router.get("/products/{slug}", response_model=ProductDetail)
async def product_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    detail = await CatalogueRepository(db).get_published_detail(
        slug, country=_normalize_country(country), locale=locale
    )
    if detail is None:
        raise NotFoundError("Product not found.")
    return detail


def _public_review_payload(row: dict[str, Any]) -> dict[str, Any]:
    payload = {
        "id": row["id"],
        "rating": row["rating"],
        "title": row["title"],
        "body": row["body"],
        "authorName": row["author_name"],
        "verifiedPurchase": bool(row["verified_purchase"]),
        "createdAt": row["created_at"],
    }
    # Only present on the sitewide featured-reviews feed, not the per-product
    # list -- a product's own review list already has the product for context.
    if "product_name" in row:
        payload["productName"] = row["product_name"]
        payload["productSlug"] = row["product_slug"]
    return payload


@router.get("/products/{slug}/reviews")
async def product_reviews(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """Approved reviews for one published product."""
    validate_slug(slug)
    product = await db.fetch_one(
        "SELECT id FROM products WHERE slug = ? AND status = 'published'", (slug,)
    )
    if product is None:
        raise NotFoundError("Product not found.")
    repository = ReviewRepository(db)
    rows = await repository.list_public_for_product(product["id"], limit=limit, offset=offset)
    return {
        "items": [_public_review_payload(row) for row in rows],
        "total": await repository.count_public_for_product(product["id"]),
    }


@router.get("/reviews")
async def all_reviews(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Any:
    """Every approved review sitewide, newest first -- backs the storefront's
    dedicated `/reviews` page. `GET /products/{slug}/reviews` is the
    per-product equivalent; `GET /reviews/featured` is the curated homepage
    feed."""
    repository = ReviewRepository(db)
    rows = await repository.list_public_all(limit=limit, offset=offset)
    return {
        "items": [_public_review_payload(row) for row in rows],
        "total": await repository.count_public_all(),
    }


@router.get("/reviews/featured")
async def featured_reviews(
    db: Annotated[Database, Depends(get_database)],
    ids: Annotated[str | None, Query(max_length=2000)] = None,
    min_rating: Annotated[int, Query(ge=1, le=5, alias="minRating")] = 4,
    limit: Annotated[int, Query(ge=1, le=24)] = 8,
) -> Any:
    """Backs the homepage `reviews_showcase` block. `ids` (manual mode) is a
    comma-separated review id list, in display order; omitted (rule mode)
    returns the current top-rated approved reviews sitewide."""
    review_ids = [entry.strip() for entry in ids.split(",") if entry.strip()][:24] if ids else None
    rows = await ReviewRepository(db).list_featured(
        review_ids=review_ids, min_rating=min_rating, limit=limit
    )
    return {"items": [_public_review_payload(row) for row in rows]}


@router.get("/promotions/featured")
async def featured_promotion(
    db: Annotated[Database, Depends(get_database)],
    promotion_id: Annotated[str | None, Query(max_length=64, alias="promotionId")] = None,
) -> Any:
    """The one promotion to advertise right now. The homepage banner and the
    checkout box both call this, so they always show the same copy -- never
    two hand-maintained versions of it. `promotionId` (manual mode) pins one
    specific promotion, still re-checked for active/in-window on every call;
    omitted (rule mode) resolves the current highest-priority automatic
    promotion. Returns `{"promotion": null}` when the sitewide switch is off
    or nothing currently qualifies -- never an error, since "nothing to
    advertise" is an ordinary state, not a failure.
    """
    if not await promotions_enabled(db):
        return {"promotion": None}
    repository = PromotionRepository(db)
    now = utc_now_iso()
    if promotion_id:
        row = await repository.get_by_id(promotion_id)
        if (
            row is None
            or row["status"] != "active"
            or (row["starts_at"] and row["starts_at"] > now)
            or (row["ends_at"] and row["ends_at"] <= now)
        ):
            return {"promotion": None}
    else:
        automatic = await repository.list_active_automatic(now)
        if not automatic:
            return {"promotion": None}
        row = automatic[0]
    coupons = await repository.list_coupons(row["id"])
    active_code = next((coupon["code"] for coupon in coupons if coupon["active"]), None)
    return {
        "promotion": {
            "id": row["id"],
            "name": row["name"],
            "headline": row["headline"] or row["name"],
            "description": row["description"],
            "code": active_code,
        }
    }


def _public_bundle_item_payload(row: dict[str, Any]) -> dict[str, Any]:
    unit_price = row["unit_price_minor"] or 0
    return {
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


def _public_bundle_payload(
    row: dict[str, Any],
    items: list[dict[str, Any]],
    fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    item_payloads = [_public_bundle_item_payload(item) for item in items]
    component_sum_minor = sum(item["lineTotalMinor"] for item in item_payloads)

    def translated(field: str, fallback: Any) -> Any:
        if not fields:
            return fallback
        value = fields.get(field)
        return value if isinstance(value, str) and value.strip() else fallback

    return {
        "id": row["id"],
        "name": translated("name", row["name"]),
        "slug": row["slug"],
        "description": translated("description", row["description"]),
        "bundlePriceMinor": row["bundle_price_minor"],
        "componentSumMinor": component_sum_minor,
        "savingsMinor": max(component_sum_minor - row["bundle_price_minor"], 0),
        "imageUrl": row["image_url"],
        "imageAlt": row["image_alt"],
        "items": item_payloads,
    }


@router.get("/bundles")
async def list_bundles(
    db: Annotated[Database, Depends(get_database)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    """Active, purchasable bundles for the shop -- each carries its own item
    list and the savings the checkout discount will actually apply, computed
    against current variant prices, so the shop card never advertises a
    number `resolve_bundle_discount` would not also grant."""
    repository = BundleRepository(db)
    rows = await repository.list_active(limit=limit, offset=offset)
    fields_by_id: dict[str, dict[str, Any]] = {}
    if locale and locale != "en" and rows:
        fields_by_id = await EntityTranslationRepository(db).get_fields_map(
            "bundle", [row["id"] for row in rows], locale
        )
    payloads = []
    for row in rows:
        items = await repository.list_items(row["id"])
        payloads.append(_public_bundle_payload(row, items, fields_by_id.get(row["id"])))
    return {"items": payloads}


@router.get("/bundles/{slug}")
async def bundle_detail(
    slug: str,
    db: Annotated[Database, Depends(get_database)],
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    validate_slug(slug)
    repository = BundleRepository(db)
    row = await repository.get_by_slug(slug)
    if row is None or row["status"] != "active":
        raise NotFoundError("Bundle not found.")
    items = await repository.list_items(row["id"])
    translation = None
    if locale and locale != "en":
        translation = await EntityTranslationRepository(db).get("bundle", row["id"], locale)
    return _public_bundle_payload(row, items, translation["fields"] if translation else None)


@router.get("/search", response_model=SearchResponse)
async def search(
    db: Annotated[Database, Depends(get_database)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
    country: Annotated[str | None, Query(max_length=2)] = None,
    locale: Annotated[str | None, Query(max_length=10)] = None,
) -> Any:
    return await SearchRepository(db).search(q, country=_normalize_country(country), locale=locale)

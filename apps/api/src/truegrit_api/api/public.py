"""Public catalogue and content endpoints. Published data only — never drafts."""

from __future__ import annotations

import json
import re
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_database
from truegrit_api.config import get_settings
from truegrit_api.domain.slugs import validate_slug
from truegrit_api.errors import NotFoundError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.repositories.catalogue import CatalogueRepository
from truegrit_api.repositories.content import (
    CategoryRepository,
    NavigationRepository,
    PageRepository,
    SearchRepository,
)
from truegrit_api.schemas.public import (
    ProductDetail,
    ProductListResponse,
    PublicBootstrap,
    PublicCategoryPage,
    SearchResponse,
)
from truegrit_api.services.email import send_email
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

router = APIRouter(tags=["public"])

_EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ContactRequest(_CamelModel):
    name: str = Field(min_length=2, max_length=120)
    email: str = Field(min_length=3, max_length=254)
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
async def bootstrap(db: Annotated[Database, Depends(get_database)]) -> Any:
    navigation = NavigationRepository(db)
    return {
        "navigation": await navigation.menu("header"),
        "footer_navigation": await navigation.menu("footer"),
        "announcement": await navigation.active_announcement(),
    }


@router.get("/payment-methods")
async def payment_methods() -> Any:
    """Which checkout methods the storefront should offer, plus the public
    Razorpay key its widget needs. No secrets are exposed."""
    settings = get_settings()
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
async def home(db: Annotated[Database, Depends(get_database)]) -> Any:
    page = await PageRepository(db).get_published_by_slug("home")
    if page is None:
        raise NotFoundError("Homepage is not published.")
    return page


@router.post("/contact")
async def contact(
    payload: ContactRequest,
    background: BackgroundTasks,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    email = payload.email.strip().lower()
    if not _EMAIL_PATTERN.match(email):
        raise ValidationAppError("Enter a valid email address.")

    now = utc_now_iso()
    message_id = new_id("msg")
    await db.execute(
        """
        INSERT INTO contact_messages (id, name, email, subject, message, status, created_at)
        VALUES (?, ?, ?, ?, ?, 'new', ?)
        """,
        (
            message_id,
            payload.name.strip(),
            email,
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
            f"Name: {payload.name.strip()}\n"
            f"Email: {email}\n\n"
            f"{payload.message.strip()}"
        ),
        settings,
    )
    return {"ok": True, "id": message_id}


@router.get("/categories/{slug}", response_model=PublicCategoryPage)
async def category_page(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    category = await CategoryRepository(db).get_published_by_slug(slug)
    if category is None:
        raise NotFoundError("Category not found.")

    catalogue = CatalogueRepository(db)
    rule_json = category["product_rule_json"]
    if category["product_assignment_mode"] in {"dynamic", "hybrid"} and rule_json:
        products = await catalogue.list_published_by_rule(json.loads(rule_json))
    else:
        products = await catalogue.list_published_by_category(category["id"])

    return {
        "id": category["id"],
        "name": category["name"],
        "slug": category["slug"],
        "breadcrumbs": [
            {"label": "Home", "path": "/"},
            {"label": "Shop", "path": "/shop"},
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
        "subcategories": [],
        "products": products,
        "faq": _STANDARDS_FAQ,
        "seo": {
            "title": category["seo_title"] or f"{category['name']} — True Grit",
            "description": category["seo_description"] or category["short_description"] or "",
            "canonical_path": f"/category/{category['slug']}",
            "indexing": "index",
        },
        "updated_at": category["updated_at"],
    }


@router.get("/categories")
async def categories(db: Annotated[Database, Depends(get_database)]) -> Any:
    rows = await CategoryRepository(db).list_published()
    return {
        "items": [
            {
                "id": row["id"],
                "name": row["name"],
                "slug": row["slug"],
                "shortDescription": row["short_description"] or "",
                "themeKey": row["theme_key"] or "forest",
                "seasonLabel": row["season_label"],
                "imageUrl": row["hero_image_url"],
                "productCount": row["product_count"],
            }
            for row in rows
        ]
    }


@router.get("/products", response_model=ProductListResponse)
async def products_list(
    db: Annotated[Database, Depends(get_database)],
    slugs: Annotated[str | None, Query(max_length=4000)] = None,
) -> Any:
    """Published products for storefront grids.

    With `?slugs=a,b,c` returns exactly those, in the given order (home-page
    product collections). Without it, every published product, newest first (the
    shop grid). Declared before `/products/{slug}` so the literal path wins.
    """
    catalogue = CatalogueRepository(db)
    if slugs is not None:
        wanted = [slug.strip() for slug in slugs.split(",") if slug.strip()][:200]
        items = await catalogue.list_published_by_slugs(wanted) if wanted else []
    else:
        items = await catalogue.list_all_published()
    return {"items": items}


@router.get("/products/{slug}", response_model=ProductDetail)
async def product_detail(slug: str, db: Annotated[Database, Depends(get_database)]) -> Any:
    validate_slug(slug)
    detail = await CatalogueRepository(db).get_published_detail(slug)
    if detail is None:
        raise NotFoundError("Product not found.")
    return detail


@router.get("/search", response_model=SearchResponse)
async def search(
    db: Annotated[Database, Depends(get_database)],
    q: Annotated[str, Query(min_length=1, max_length=120)],
) -> Any:
    return await SearchRepository(db).search(q)

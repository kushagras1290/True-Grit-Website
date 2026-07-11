"""Public catalogue and content endpoints. Published data only — never drafts."""

from __future__ import annotations

import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from truegrit_api.auth.dependencies import get_database
from truegrit_api.domain.slugs import validate_slug
from truegrit_api.errors import NotFoundError
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
    PublicBootstrap,
    PublicCategoryPage,
    SearchResponse,
)

router = APIRouter(tags=["public"])

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


@router.get("/home")
async def home(db: Annotated[Database, Depends(get_database)]) -> Any:
    page = await PageRepository(db).get_published_by_slug("home")
    if page is None:
        raise NotFoundError("Homepage is not published.")
    return page


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
                "productCount": row["product_count"],
            }
            for row in rows
        ]
    }


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

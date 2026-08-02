"""Public response DTOs — camelCase at the boundary, snake_case internally.

These mirror `@truegrit/contracts` exactly; the OpenAPI document generated from
this app is the source for frontend type generation.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class PublicModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class SeoDocument(PublicModel):
    title: str
    description: str
    canonical_path: str
    indexing: str = "index"
    keywords: str | None = None


class BreadcrumbItem(PublicModel):
    label: str
    path: str


class NavigationItem(PublicModel):
    label: str
    path: str


class Announcement(PublicModel):
    message: str
    path: str | None = None


class PublicBootstrap(PublicModel):
    navigation: list[NavigationItem]
    footer_navigation: list[NavigationItem]
    announcement: Announcement | None = None


class ProductSummary(PublicModel):
    id: str
    name: str
    slug: str
    farm_name: str
    region: str
    certification: str
    price_minor: int
    sale_minor: int | None = None
    # Set only when an active price-adjustment rule (`services.price_adjustments`)
    # changes what this visitor pays for this product; absent, not zero, so the
    # storefront can tell "no adjustment" apart from "adjusted to no change".
    # Positive-adjustment (markup) and negative-adjustment (genuine discount)
    # render differently -- see the field's use in `packages/contracts`.
    adjusted_minor: int | None = None
    currency_code: str
    unit_label: str
    availability: str
    tags: list[str]
    image_url: str | None = None
    image_alt: str
    # Per-product order/payment switch (migration 0048), independent of the
    # site-wide one on Site Control. False means the product is still shown
    # and browsable -- just not currently orderable.
    accepts_orders: bool = True


class ProductListResponse(PublicModel):
    items: list[ProductSummary]
    total: int


class VariantSummary(PublicModel):
    id: str
    name: str
    sku: str
    list_minor: int
    sale_minor: int | None = None
    adjusted_minor: int | None = None
    availability: str


class TraceabilityStep(PublicModel):
    label: str
    detail: str


class ProductDetail(ProductSummary):
    short_description: str
    overview: str
    farm_slug: str
    storage_guidance: str
    harvest_note: str
    growing_method: str
    variants: list[VariantSummary]
    traceability: list[TraceabilityStep]
    related_slugs: list[str]
    return_eligible: bool
    seo: SeoDocument


class CategorySummary(PublicModel):
    id: str
    name: str
    slug: str
    short_description: str
    theme_key: str
    season_label: str | None = None
    image_url: str | None = None
    product_count: int
    # Tree position: `parent_id` is None for a department, set for a
    # subcategory; `level` is 0 for departments and 1 for subcategories.
    parent_id: str | None = None
    level: int = 0


class FaqItem(PublicModel):
    question: str
    answer: str


class CategoryHero(PublicModel):
    eyebrow: str
    title: str
    description: str
    season_label: str | None = None
    image_url: str | None = None
    image_alt: str | None = None


class PublicCategoryPage(PublicModel):
    id: str
    name: str
    slug: str
    breadcrumbs: list[BreadcrumbItem]
    theme_key: str
    hero: CategoryHero
    subcategories: list[CategorySummary]
    products: list[ProductSummary]
    products_total: int
    faq: list[FaqItem]
    seo: SeoDocument
    updated_at: str


class PublicPage(PublicModel):
    id: str
    slug: str
    title: str
    blocks: list[dict[str, Any]]
    seo: SeoDocument


class FarmDetail(PublicModel):
    id: str
    name: str
    slug: str
    farmer_name: str
    region: str
    summary: str
    certification: str
    established_year: int
    story: str
    methods: list[str]
    product_slugs: list[str]
    seo: SeoDocument


class FarmListResponse(PublicModel):
    items: list[FarmDetail]


class RecipeIngredient(PublicModel):
    label: str
    quantity_text: str
    product_slug: str | None = None


class RecipeDetail(PublicModel):
    id: str
    title: str
    slug: str
    excerpt: str
    prep_minutes: int
    cook_minutes: int
    servings: int
    dietary_tags: list[str]
    hero_image_url: str | None = None
    hero_image_alt: str | None = None
    ingredients: list[RecipeIngredient]
    blocks: list[dict[str, Any]]
    steps: list[str]
    seo: SeoDocument


class RecipeListResponse(PublicModel):
    items: list[RecipeDetail]
    total: int
    limit: int
    offset: int


class ArticleDetail(PublicModel):
    id: str
    title: str
    slug: str
    excerpt: str
    author_name: str
    published_at: str
    reading_minutes: int
    hero_image_url: str | None = None
    hero_image_alt: str | None = None
    blocks: list[dict[str, Any]]
    pull_quote: str | None = None
    seo: SeoDocument


class ArticleListResponse(PublicModel):
    items: list[ArticleDetail]
    total: int
    limit: int
    offset: int


class SearchResultGroup(PublicModel):
    group: str
    items: list[dict[str, str]]


class SearchResponse(PublicModel):
    query: str
    total: int
    groups: list[SearchResultGroup]

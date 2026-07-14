"""Public response DTOs — camelCase at the boundary, snake_case internally.

These mirror `@truegrit/contracts` exactly; the OpenAPI document generated from
this app is the source for frontend type generation.
"""

from __future__ import annotations

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
    currency_code: str
    unit_label: str
    availability: str
    tags: list[str]
    image_url: str | None = None
    image_alt: str


class VariantSummary(PublicModel):
    id: str
    name: str
    sku: str
    list_minor: int
    sale_minor: int | None = None
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
    faq: list[FaqItem]
    seo: SeoDocument
    updated_at: str


class SearchResultGroup(PublicModel):
    group: str
    items: list[dict[str, str]]


class SearchResponse(PublicModel):
    query: str
    total: int
    groups: list[SearchResultGroup]

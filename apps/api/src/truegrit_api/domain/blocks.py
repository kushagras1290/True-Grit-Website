"""CMS block registry (ADR-005).

Pages store validated, versioned structured blocks — never arbitrary HTML or JS.
The union here mirrors `@truegrit/contracts` exactly. Unknown block types are
rejected on save; the storefront independently fails safely on render.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

from truegrit_api.errors import ValidationAppError

_SAFE_HREF_PREFIXES = ("/", "https://", "http://", "mailto:")
MAX_BLOCKS = 40


def validate_href(href: str) -> str:
    if not href.startswith(_SAFE_HREF_PREFIXES) or href.startswith("//"):
        raise ValueError(f"Unsafe link destination: {href!r}")
    return href


class BlockAction(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    href: str = Field(min_length=1, max_length=512)

    @field_validator("href")
    @classmethod
    def _safe_href(cls, value: str) -> str:
        return validate_href(value)


class _BlockBase(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    version: int = Field(ge=1, le=10)
    enabled: bool = True


class HeroProps(BaseModel):
    layout: Literal["editorial-split", "full-bleed"]
    eyebrow: str = Field(max_length=120)
    heading: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=600)
    primary_action: BlockAction = Field(alias="primaryAction")
    secondary_action: BlockAction | None = Field(default=None, alias="secondaryAction")

    model_config = {"populate_by_name": True}


class HeroBlock(_BlockBase):
    type: Literal["hero"]
    props: HeroProps


class CategoryCollectionProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    category_slugs: list[str] = Field(alias="categorySlugs", min_length=1, max_length=12)

    model_config = {"populate_by_name": True}


class CategoryCollectionBlock(_BlockBase):
    type: Literal["category_collection"]
    props: CategoryCollectionProps


class ProductCollectionProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    source: Literal["manual", "rule"]
    product_slugs: list[str] = Field(alias="productSlugs", default_factory=list, max_length=24)
    limit: int = Field(ge=1, le=24)

    model_config = {"populate_by_name": True}


class ProductCollectionBlock(_BlockBase):
    type: Literal["product_collection"]
    props: ProductCollectionProps


class FarmerStoryProps(BaseModel):
    farm_slug: str = Field(alias="farmSlug", min_length=1, max_length=96)
    quote: str = Field(min_length=1, max_length=400)
    attribution: str = Field(min_length=1, max_length=160)

    model_config = {"populate_by_name": True}


class FarmerStoryBlock(_BlockBase):
    type: Literal["farmer_story"]
    props: FarmerStoryProps


class FaqItem(BaseModel):
    question: str = Field(min_length=1, max_length=240)
    answer: str = Field(min_length=1, max_length=1200)


class FaqProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    items: list[FaqItem] = Field(min_length=1, max_length=20)


class FaqBlock(_BlockBase):
    type: Literal["faq"]
    props: FaqProps


class RichTextProps(BaseModel):
    # Restricted rich text: plain paragraphs only in Release 1. No raw HTML ever.
    paragraphs: list[str] = Field(min_length=1, max_length=60)

    @field_validator("paragraphs")
    @classmethod
    def _no_markup(cls, value: list[str]) -> list[str]:
        for paragraph in value:
            if "<" in paragraph or ">" in paragraph:
                raise ValueError("Rich text paragraphs cannot contain markup.")
        return value


class RichTextBlock(_BlockBase):
    type: Literal["rich_text"]
    props: RichTextProps


class NewsletterProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    consent_text: str = Field(alias="consentText", min_length=1, max_length=300)

    model_config = {"populate_by_name": True}


class NewsletterBlock(_BlockBase):
    type: Literal["newsletter"]
    props: NewsletterProps


PageBlock = Annotated[
    HeroBlock
    | CategoryCollectionBlock
    | ProductCollectionBlock
    | FarmerStoryBlock
    | FaqBlock
    | RichTextBlock
    | NewsletterBlock,
    Field(discriminator="type"),
]

_blocks_adapter: TypeAdapter[list[PageBlock]] = TypeAdapter(list[PageBlock])


def validate_blocks(raw_blocks: Any) -> list[PageBlock]:
    """Validate a block list from untrusted input; raise a structured 422 on failure."""
    if not isinstance(raw_blocks, list):
        raise ValidationAppError("Page content must be a list of blocks.")
    if len(raw_blocks) > MAX_BLOCKS:
        raise ValidationAppError(f"A page supports at most {MAX_BLOCKS} blocks.")
    ids = [block.get("id") for block in raw_blocks if isinstance(block, dict)]
    if len(ids) != len(set(ids)):
        raise ValidationAppError("Block ids must be unique within a page.")
    try:
        return _blocks_adapter.validate_python(raw_blocks)
    except ValidationError as exc:
        raise ValidationAppError(
            "Page content failed validation.",
            details={"issues": exc.errors(include_url=False, include_input=False)[:10]},
        ) from exc

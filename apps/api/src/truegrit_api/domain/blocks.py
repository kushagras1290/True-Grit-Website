"""CMS block registry (ADR-005).

Pages store validated, versioned structured blocks — never arbitrary HTML or JS.
The union here mirrors `@truegrit/contracts` exactly. Unknown block types are
rejected on save; the storefront independently fails safely on render.
"""

from __future__ import annotations

import re
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, field_validator

from truegrit_api.errors import ValidationAppError

_SAFE_HREF_PREFIXES = ("/", "https://", "http://", "mailto:")
MAX_BLOCKS = 40

# Structural ceiling on the banner carousel, enforced by the block model itself.
#
# This is *not* the number an operator works to -- that one is
# `homepage.hero.max_slides` in `app_settings`, editable from Homepage Settings
# so raising the carousel from twelve to fifteen needs no deploy. This constant
# only stops a request pasting hundreds of slides into one block and blowing up
# every homepage render, so it deliberately sits well above any sensible
# configured value and should effectively never be the limit that bites.
#
# Migration 0047 ships twelve branded banners, which is why the shipped
# configured default is twelve: a cap below what the product actually seeds
# would make the homepage unsaveable -- the console loads the block, sends it
# back untouched, and gets a 422 for content it never edited.
HERO_SLIDES_HARD_LIMIT = 40
DEFAULT_MAX_HERO_SLIDES = 12

# Inline link syntax allowed inside rich-text paragraphs: `[label](href)`.
# This is the only way a link can appear in body copy — raw `<a>`/HTML is
# still rejected outright (ADR-005). The storefront renderer parses the same
# pattern to build real anchor elements; it never uses dangerouslySetInnerHTML.
_INLINE_LINK_PATTERN = re.compile(r"\[(?P<label>[^\[\]\n]{1,120})\]\((?P<href>[^\s()]{1,512})\)")
MAX_LINKS_PER_PARAGRAPH = 5
MAX_PARAGRAPH_LENGTH = 4000


def validate_href(href: str) -> str:
    if not href.startswith(_SAFE_HREF_PREFIXES) or href.startswith("//"):
        raise ValueError(f"Unsafe link destination: {href!r}")
    return href


def validate_inline_links(paragraph: str) -> None:
    """Validate every `[label](href)` span in a rich-text paragraph.

    Raises ValueError on an unsafe href or too many links in one paragraph.
    Text outside the pattern (including stray literal brackets) is untouched —
    it renders as plain text, so it carries no injection risk.
    """
    matches = _INLINE_LINK_PATTERN.findall(paragraph)
    if len(matches) > MAX_LINKS_PER_PARAGRAPH:
        raise ValueError(f"A paragraph cannot contain more than {MAX_LINKS_PER_PARAGRAPH} links.")
    for _label, href in matches:
        validate_href(href)


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


class HeroSlide(BaseModel):
    image_url: str = Field(alias="imageUrl", min_length=1, max_length=1000)
    image_alt: str = Field(alias="imageAlt", max_length=200)
    href: str = Field(min_length=1, max_length=512)
    label: str = Field(min_length=1, max_length=80)
    enabled: bool = True

    @field_validator("href")
    @classmethod
    def _safe_href(cls, value: str) -> str:
        return validate_href(value)

    model_config = {"populate_by_name": True}


class HeroProps(BaseModel):
    layout: Literal["editorial-split", "full-bleed"]
    eyebrow: str = Field(max_length=120)
    heading: str = Field(min_length=1, max_length=200)
    text: str = Field(max_length=600)
    image_url: str | None = Field(default=None, alias="imageUrl", max_length=1000)
    image_alt: str | None = Field(default=None, alias="imageAlt", max_length=200)
    slides: list[HeroSlide] = Field(default_factory=list, max_length=HERO_SLIDES_HARD_LIMIT)
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


def _safe_prose_list(value: list[str]) -> list[str]:
    for entry in value:
        if "<" in entry or ">" in entry:
            raise ValueError("Text cannot contain markup.")
        if len(entry) > MAX_PARAGRAPH_LENGTH:
            raise ValueError(f"Text cannot exceed {MAX_PARAGRAPH_LENGTH} characters.")
        validate_inline_links(entry)
    return value


class RichTextProps(BaseModel):
    # Restricted rich text: plain paragraphs with an optional safe inline link
    # syntax `[label](href)`. No raw HTML ever.
    heading: str | None = Field(default=None, max_length=120)
    paragraphs: list[str] = Field(min_length=1, max_length=60)

    @field_validator("paragraphs")
    @classmethod
    def _safe_paragraphs(cls, value: list[str]) -> list[str]:
        return _safe_prose_list(value)


class RichTextBlock(_BlockBase):
    type: Literal["rich_text"]
    props: RichTextProps


class BulletListProps(BaseModel):
    # Same restricted-text rules as rich_text, applied per list item rather
    # than per paragraph.
    heading: str | None = Field(default=None, max_length=120)
    items: list[str] = Field(min_length=1, max_length=30)

    @field_validator("items")
    @classmethod
    def _safe_items(cls, value: list[str]) -> list[str]:
        return _safe_prose_list(value)


class BulletListBlock(_BlockBase):
    type: Literal["bullet_list"]
    props: BulletListProps


class NewsletterProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    consent_text: str = Field(alias="consentText", min_length=1, max_length=300)

    model_config = {"populate_by_name": True}


class NewsletterBlock(_BlockBase):
    type: Literal["newsletter"]
    props: NewsletterProps


class PageLinkItem(BaseModel):
    """One snippet card pointing at another page.

    `href` goes through the same allow-list as every other block link, so a
    snippet cannot become a `javascript:` payload however it was authored.
    """

    label: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=240)
    href: str = Field(min_length=1, max_length=512)
    enabled: bool = True

    @field_validator("href")
    @classmethod
    def _safe_href(cls, value: str) -> str:
        return validate_href(value)


class PageLinksProps(BaseModel):
    heading: str = Field(min_length=1, max_length=120)
    intro: str = Field(default="", max_length=400)
    # 24 is roughly twice the storefront's public route count -- room for a
    # campaign page or two without turning the homepage into a sitemap.
    items: list[PageLinkItem] = Field(min_length=1, max_length=24)


class PageLinksBlock(_BlockBase):
    type: Literal["page_links"]
    props: PageLinksProps


class ReviewsShowcaseProps(BaseModel):
    """Either a hand-picked set of testimonials (`manual`, via `reviewIds`) or
    the current top-rated approved reviews sitewide (`rule`). `rule` resolves
    live on every render -- like `product_collection`'s own rule mode -- so it
    never goes stale and degrades to nothing rendered when no review yet meets
    `minRating`, rather than needing an editor to notice and disable it."""

    heading: str = Field(min_length=1, max_length=120)
    subheading: str = Field(default="", max_length=240)
    source: Literal["manual", "rule"]
    review_ids: list[str] = Field(alias="reviewIds", default_factory=list, max_length=24)
    limit: int = Field(ge=1, le=24, default=8)
    min_rating: int = Field(alias="minRating", ge=1, le=5, default=4)

    model_config = {"populate_by_name": True}


class ReviewsShowcaseBlock(_BlockBase):
    type: Literal["reviews_showcase"]
    props: ReviewsShowcaseProps


class PromotionBannerProps(BaseModel):
    """`manual` pins one specific promotion by id; `rule` resolves the
    current highest-priority active promotion live on every render, the same
    two-mode split as `reviews_showcase`. There is no heading/subheading
    override here -- unlike reviews, a promotion already carries its own
    `headline`/`description` (migration 0060), which is also what the
    checkout-page callout reads, so the homepage and checkout always show the
    same copy rather than two hand-maintained versions of it."""

    source: Literal["manual", "rule"]
    promotion_id: str | None = Field(alias="promotionId", default=None, max_length=64)

    model_config = {"populate_by_name": True}


class PromotionBannerBlock(_BlockBase):
    type: Literal["promotion_banner"]
    props: PromotionBannerProps


class RecommendationsProps(BaseModel):
    """Best-sellers, computed live from real `order_items` -- not a curated
    list, so there is nothing for an editor to keep stocked or let go stale.
    Reads as ordinary merchandising copy (heading/subheading), not a labelled
    "recommendations" widget."""

    heading: str = Field(min_length=1, max_length=120)
    subheading: str = Field(default="", max_length=240)
    limit: int = Field(ge=1, le=24, default=8)


class RecommendationsBlock(_BlockBase):
    type: Literal["recommendations"]
    props: RecommendationsProps


class ImageBannerProps(BaseModel):
    """A single full-width graphic -- a brand statement or campaign lockup
    that is itself the content, as opposed to `hero`'s rotating carousel or
    `rich_text`'s prose. Optionally links somewhere; renders as a plain image
    when it does not."""

    image_url: str = Field(alias="imageUrl", min_length=1, max_length=1000)
    image_alt: str = Field(alias="imageAlt", min_length=1, max_length=200)
    href: str | None = Field(default=None, max_length=512)

    @field_validator("href")
    @classmethod
    def _safe_href(cls, value: str | None) -> str | None:
        return validate_href(value) if value else value

    model_config = {"populate_by_name": True}


class ImageBannerBlock(_BlockBase):
    type: Literal["image_banner"]
    props: ImageBannerProps


PageBlock = Annotated[
    HeroBlock
    | CategoryCollectionBlock
    | ProductCollectionBlock
    | FarmerStoryBlock
    | FaqBlock
    | RichTextBlock
    | BulletListBlock
    | NewsletterBlock
    | PageLinksBlock
    | ReviewsShowcaseBlock
    | PromotionBannerBlock
    | RecommendationsBlock
    | ImageBannerBlock,
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
            # `include_context=False` matters: for a failure raised by one of the
            # custom field validators above, Pydantic puts the live ValueError
            # object in `ctx`, which the JSON error renderer cannot serialise --
            # so a perfectly ordinary "unsafe href" 422 came back as a 500. The
            # human-readable reason is already in each issue's `msg`.
            details={
                "issues": exc.errors(include_url=False, include_input=False, include_context=False)[
                    :10
                ]
            },
        ) from exc

import json

import pytest

from truegrit_api.domain.blocks import (
    BulletListBlock,
    PageLinksBlock,
    RichTextBlock,
    validate_blocks,
)
from truegrit_api.errors import ValidationAppError

HERO = {
    "id": "blk_hero",
    "type": "hero",
    "version": 1,
    "enabled": True,
    "props": {
        "layout": "editorial-split",
        "eyebrow": "Certified organic",
        "heading": "Food grown the way nature intended.",
        "text": "Fresh organic produce with complete transparency.",
        "primaryAction": {"label": "Explore the market", "href": "/shop"},
        "secondaryAction": None,
    },
}


def test_valid_blocks_pass():
    blocks = validate_blocks([HERO])
    assert blocks[0].type == "hero"


def test_unknown_block_type_rejected():
    bad = {
        **HERO,
        "id": "blk_x",
        "type": "custom_html",
        "props": {"html": "<script>alert(1)</script>"},
    }
    with pytest.raises(ValidationAppError):
        validate_blocks([HERO, bad])


def test_unsafe_link_protocols_rejected():
    for href in ("javascript:alert(1)", "data:text/html;base64,x", "//evil.example"):
        bad = {
            **HERO,
            "id": "blk_bad",
            "props": {**HERO["props"], "primaryAction": {"label": "x", "href": href}},
        }
        with pytest.raises(ValidationAppError):
            validate_blocks([bad])


def test_validation_details_survive_json_encoding():
    """A rejected block must come back as a 422 the client can read.

    Failures raised by the custom field validators carry the live ValueError in
    Pydantic's `ctx`, which the JSON error renderer cannot serialise — so an
    ordinary "unsafe href" once surfaced as a 500 instead of a validation error.
    """
    bad = {
        **HERO,
        "id": "blk_bad",
        "props": {**HERO["props"], "primaryAction": {"label": "x", "href": "javascript:alert(1)"}},
    }
    with pytest.raises(ValidationAppError) as caught:
        validate_blocks([bad])
    encoded = json.dumps(caught.value.details)
    assert "Unsafe link destination" in encoded


def test_rich_text_rejects_markup():
    block = {
        "id": "blk_rt",
        "type": "rich_text",
        "version": 1,
        "enabled": True,
        "props": {"paragraphs": ["Fine paragraph.", "<img onerror=alert(1)>"]},
    }
    with pytest.raises(ValidationAppError):
        validate_blocks([block])


def test_rich_text_heading_is_optional_and_stored():
    with_heading = {
        "id": "blk_rt_h",
        "type": "rich_text",
        "version": 1,
        "enabled": True,
        "props": {"heading": "Storage tips", "paragraphs": ["Fine paragraph."]},
    }
    without_heading = {
        **with_heading,
        "id": "blk_rt_nh",
        "props": {"paragraphs": ["Fine paragraph."]},
    }
    validated = validate_blocks([with_heading, without_heading])
    first, second = validated[0], validated[1]
    assert isinstance(first, RichTextBlock)
    assert isinstance(second, RichTextBlock)
    assert first.props.heading == "Storage tips"
    assert second.props.heading is None


def test_bullet_list_accepts_inline_links_and_rejects_markup():
    ok = {
        "id": "blk_bl",
        "type": "bullet_list",
        "version": 1,
        "enabled": True,
        "props": {
            "heading": "Quick checks",
            "items": ["Smell it first.", "See the [Kathiya flour](/product/kathiya-wheat-flour)."],
        },
    }
    validated = validate_blocks([ok])
    block = validated[0]
    assert isinstance(block, BulletListBlock)
    assert block.props.items[1].startswith("See the [Kathiya")

    bad = {
        **ok,
        "id": "blk_bl_bad",
        "props": {**ok["props"], "items": ["<script>alert(1)</script>"]},
    }
    with pytest.raises(ValidationAppError):
        validate_blocks([bad])


def test_bullet_list_requires_at_least_one_item():
    empty = {
        "id": "blk_bl_empty",
        "type": "bullet_list",
        "version": 1,
        "enabled": True,
        "props": {"items": []},
    }
    with pytest.raises(ValidationAppError):
        validate_blocks([empty])


def test_duplicate_block_ids_rejected():
    with pytest.raises(ValidationAppError):
        validate_blocks([HERO, HERO])


def test_non_list_rejected():
    with pytest.raises(ValidationAppError):
        validate_blocks({"blocks": [HERO]})


PAGE_LINKS = {
    "id": "blk_page_links",
    "type": "page_links",
    "version": 1,
    "enabled": True,
    "props": {
        "heading": "Everything else on True Grit",
        "intro": "A one-line tour of the rest of the site.",
        "items": [
            {
                "label": "Shop the market",
                "description": "Every organic product we carry.",
                "href": "/shop",
                "enabled": True,
            }
        ],
    },
}


def test_page_links_block_accepted():
    block = validate_blocks([PAGE_LINKS])[0]
    assert isinstance(block, PageLinksBlock)
    assert block.props.items[0].href == "/shop"


def test_page_links_item_defaults_to_shown():
    """A snippet without an explicit `enabled` is visible, not silently hidden."""
    item = {"label": "Help", "href": "/help"}
    block = validate_blocks([{**PAGE_LINKS, "props": {**PAGE_LINKS["props"], "items": [item]}}])[0]
    assert isinstance(block, PageLinksBlock)
    assert block.props.items[0].enabled is True
    assert block.props.items[0].description == ""


def test_page_links_rejects_unsafe_destinations():
    """A snippet href goes through the same allow-list as every other block link."""
    for href in ("javascript:alert(1)", "data:text/html;base64,x", "//evil.example"):
        bad = {
            **PAGE_LINKS,
            "props": {
                **PAGE_LINKS["props"],
                "items": [{"label": "Anywhere", "description": "", "href": href}],
            },
        }
        with pytest.raises(ValidationAppError):
            validate_blocks([bad])


def test_page_links_requires_at_least_one_item():
    bad = {**PAGE_LINKS, "props": {**PAGE_LINKS["props"], "items": []}}
    with pytest.raises(ValidationAppError):
        validate_blocks([bad])

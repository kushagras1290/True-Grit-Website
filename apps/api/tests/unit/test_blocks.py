import pytest

from truegrit_api.domain.blocks import validate_blocks
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


def test_duplicate_block_ids_rejected():
    with pytest.raises(ValidationAppError):
        validate_blocks([HERO, HERO])


def test_non_list_rejected():
    with pytest.raises(ValidationAppError):
        validate_blocks({"blocks": [HERO]})

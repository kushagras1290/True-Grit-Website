import pytest

from truegrit_api.domain.slugs import slugify, validate_slug
from truegrit_api.errors import ValidationAppError


@pytest.mark.parametrize("slug", ["fresh-fruits", "a", "cold-pressed-oils", "abc123"])
def test_valid_slugs(slug: str):
    assert validate_slug(slug) == slug


@pytest.mark.parametrize(
    "slug",
    ["Fresh-Fruits", "fresh_fruits", "-fruits", "fruits-", "fr--uits", "", "a b", "café"],
)
def test_invalid_slugs(slug: str):
    with pytest.raises(ValidationAppError):
        validate_slug(slug)


def test_slugify_derives_valid_slug():
    assert slugify("Organic Alphonso Mangoes!") == "organic-alphonso-mangoes"
    assert validate_slug(slugify("Crème   Fraîche & Co."))


def test_slugify_rejects_unusable_names():
    with pytest.raises(ValidationAppError):
        slugify("!!!")

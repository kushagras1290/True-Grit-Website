"""Unit tests for mobile number normalisation.

Every phone comparison in the system is an exact string match against
`users.phone_e164`, so "the same number typed two ways lands on the same row" is
load-bearing, not cosmetic: get it wrong and one person ends up with two
accounts, or a rate-limit bucket is trivially sidestepped by adding a space.
"""

from __future__ import annotations

import pytest

from truegrit_api.domain.phone import (
    is_indian_mobile,
    mask_phone,
    national_number,
    normalize_phone,
)
from truegrit_api.errors import ValidationAppError


@pytest.mark.parametrize(
    "typed",
    [
        "9876543210",
        "09876543210",
        "919876543210",
        "+919876543210",
        "+91 9876543210",
        "+91 98765-43210",
        "+91 (98765) 43210",
        "0091 9876543210",
        "  9876543210  ",
        "98765.43210",
    ],
)
def test_indian_forms_collapse_to_one_e164(typed: str):
    assert normalize_phone(typed) == "+919876543210"


@pytest.mark.parametrize("first_digit", ["6", "7", "8", "9"])
def test_all_valid_indian_mobile_prefixes_accepted(first_digit: str):
    assert normalize_phone(f"{first_digit}876543210") == f"+91{first_digit}876543210"


@pytest.mark.parametrize(
    "bad",
    [
        "1234567890",  # 10 digits but not a mobile prefix — must not become +1 …
        "5876543210",
        "987654321",  # 9 digits
        "98765432101",  # 11 digits
        "+91987654321",  # country code + 9 digits
        "+9112345678901",  # country code + non-mobile
        "notaphone",
        "+91abcdefghij",
        "",
        "   ",
        "+",
    ],
)
def test_invalid_numbers_raise(bad: str):
    with pytest.raises(ValidationAppError):
        normalize_phone(bad)


def test_bare_national_number_is_never_read_as_international():
    """A number without "+" is national. Reading "1234567890" as +1 234-567-890
    would text a stranger in North America instead of failing."""
    with pytest.raises(ValidationAppError):
        normalize_phone("1234567890")


def test_explicit_country_code_allows_other_countries():
    assert normalize_phone("+442071838750") == "+442071838750"
    assert is_indian_mobile("+442071838750") is False


def test_overlong_input_rejected():
    with pytest.raises(ValidationAppError):
        normalize_phone("+91" + "9" * 40)


def test_national_number_strips_country_code():
    assert national_number("+919876543210") == "9876543210"


def test_national_number_refuses_non_indian():
    with pytest.raises(ValidationAppError):
        national_number("+442071838750")


def test_mask_keeps_last_four_only():
    masked = mask_phone("+919876543210")
    assert masked.endswith("3210")
    assert "98765" not in masked


def test_mask_handles_short_and_malformed_input():
    assert mask_phone("+12") == "+••"
    assert mask_phone("garbage") == "•••••"

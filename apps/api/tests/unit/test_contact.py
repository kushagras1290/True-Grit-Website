"""Unit tests for the placeholder-email gate.

Phone-only accounts hold a synthetic `@phone.invalid` address purely to satisfy
`users.email NOT NULL` (migration 0016). The one invariant that keeps that trade
honest is that nothing ever sends to or displays one, so these tests guard the
gate rather than the plumbing.
"""

from __future__ import annotations

import pytest

from truegrit_api.services.contact import (
    PLACEHOLDER_EMAIL_DOMAIN,
    contactable_email,
    display_contact,
    is_placeholder_email,
    phone_from_placeholder_email,
    placeholder_email_for_phone,
)


def test_placeholder_is_unique_per_number():
    a = placeholder_email_for_phone("+919876543210")
    b = placeholder_email_for_phone("+919876543211")
    assert a != b
    # Deterministic: the same handset always maps to the same row.
    assert a == placeholder_email_for_phone("+919876543210")


def test_placeholder_uses_reserved_invalid_tld():
    """RFC 2606 reserves `.invalid` so it can never resolve. A real domain here —
    even one we own — would risk mail actually leaving."""
    assert placeholder_email_for_phone("+919876543210").endswith(f"@{PLACEHOLDER_EMAIL_DOMAIN}")
    assert PLACEHOLDER_EMAIL_DOMAIN.endswith(".invalid")


def test_contactable_email_returns_none_for_placeholder():
    placeholder = placeholder_email_for_phone("+919876543210")
    assert contactable_email(placeholder) is None
    assert is_placeholder_email(placeholder) is True


@pytest.mark.parametrize("missing", [None, "", "   "])
def test_contactable_email_returns_none_for_missing(missing):
    assert contactable_email(missing) is None


def test_contactable_email_passes_through_real_addresses():
    assert contactable_email("  Priya@Example.COM ") == "priya@example.com"
    assert is_placeholder_email("priya@example.com") is False


def test_real_address_on_similar_domain_is_not_treated_as_placeholder():
    """Only the exact reserved domain counts — a customer with a lookalike
    address must still receive their order confirmations."""
    assert is_placeholder_email("phone-919876543210@phone.invalid.example.com") is False
    assert is_placeholder_email("phone-1@notphone.invalid") is False
    assert is_placeholder_email("someone@phone.invalid.co") is False


def test_placeholder_roundtrips_to_its_number():
    email = placeholder_email_for_phone("+919876543210")
    assert phone_from_placeholder_email(email) == "+919876543210"
    assert phone_from_placeholder_email("priya@example.com") is None


def test_display_contact_prefers_email_then_phone_never_placeholder():
    assert display_contact("priya@example.com", "+919876543210") == "priya@example.com"
    placeholder = placeholder_email_for_phone("+919876543210")
    assert display_contact(placeholder, "+919876543210") == "+919876543210"
    assert display_contact(None, None) == "no contact on file"

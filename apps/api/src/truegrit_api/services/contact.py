"""Reachable contact details for accounts that may not have every channel.

A customer who signed up with only a mobile number has no email address, but
`users.email` is NOT NULL and cannot be relaxed without a table rebuild that D1
would turn into cascading data loss (see migration 0016 for the full reasoning).
Such accounts therefore hold a synthetic address in the `.invalid` top-level
domain, which RFC 2606 §2 reserves precisely so it can never resolve.

That trade buys a safe migration and costs one invariant, enforced here: nothing
may ever *send* to a placeholder. Every outbound-email caller resolves its
recipient through `contactable_email`, which returns None for an account that has
no real address — and None is a value the caller is forced to handle, unlike a
string that merely happens to be undeliverable.
"""

from __future__ import annotations

import re

from truegrit_api.domain.phone import DEFAULT_COUNTRY_CODE

# RFC 2606 §2 reserves `.invalid` for names guaranteed never to resolve. Using a
# real domain here — even one we own — would risk mail actually leaving.
PLACEHOLDER_EMAIL_DOMAIN = "phone.invalid"

_PLACEHOLDER_RE = re.compile(rf"^phone-\d+@{re.escape(PLACEHOLDER_EMAIL_DOMAIN)}$")


def placeholder_email_for_phone(phone_e164: str) -> str:
    """A unique, permanently-undeliverable stand-in address for a phone-only
    account. Deterministic in the phone number so it satisfies UNIQUE(email)
    without a collision, and so the same handset always maps to the same row."""
    digits = phone_e164.lstrip("+")
    return f"phone-{digits}@{PLACEHOLDER_EMAIL_DOMAIN}"


def is_placeholder_email(email: str | None) -> bool:
    """True when `email` is a synthetic stand-in — or absent, or blank — rather
    than something a customer typed and can receive mail at.

    Blank counts as placeholder: strip first, so "   " is recognised as nothing
    rather than falling through to the regex and being reported as a real
    address.
    """
    if email is None or not email.strip():
        return True
    return bool(_PLACEHOLDER_RE.match(email.strip().lower()))


def contactable_email(email: str | None) -> str | None:
    """The address to send to, or None when this account has no real one.

    Returning None rather than the placeholder is the whole point: a caller that
    forgets to check gets a type error or an obvious crash, not a silent send to
    `phone-919876543210@phone.invalid`.
    """
    if is_placeholder_email(email):
        return None
    assert email is not None  # narrowed by is_placeholder_email
    return email.strip().lower()


def phone_from_placeholder_email(email: str) -> str | None:
    """Recover the E.164 phone a placeholder was minted from, or None if `email`
    is not a placeholder. Useful for back-office display of legacy rows."""
    if not _PLACEHOLDER_RE.match(email.strip().lower()):
        return None
    digits = email.strip().lower().split("@", 1)[0].removeprefix("phone-")
    if not digits.isdigit():
        return None
    return f"+{digits}"


def display_contact(email: str | None, phone_e164: str | None) -> str:
    """What to show a human for this account. Prefers the real address, falls
    back to the mobile, and never surfaces a placeholder."""
    real = contactable_email(email)
    if real is not None:
        return real
    if phone_e164:
        return phone_e164
    return "no contact on file"


def looks_like_indian_number(phone_e164: str | None) -> bool:
    """Cheap guard for callers that only care about the common case."""
    return bool(phone_e164 and phone_e164.startswith(f"+{DEFAULT_COUNTRY_CODE}"))

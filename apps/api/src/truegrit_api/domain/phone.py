"""Mobile number rules: parse anything a customer types, store one canonical form.

Everything downstream — the unique index on `users.phone_e164`, OTP rate-limit
buckets, SMS delivery — compares phone numbers as exact strings. That only holds
if there is exactly one representation of a number, so every entry point funnels
through `normalize_phone` and stores E.164 ("+" then country code then subscriber
digits, no spaces or punctuation).

The store is India-first (INR, COD, Razorpay), so a bare 10-digit entry is read
as Indian and Indian numbers are validated strictly. Other country codes are
accepted against generic E.164 bounds rather than rejected outright, because the
SMS sender — not this module — is the thing that actually knows which
destinations it can reach.
"""

from __future__ import annotations

import re

from truegrit_api.errors import ValidationAppError

# E.164 caps the whole number at 15 digits including the country code; 8 is a
# floor no real mobile falls below. ITU-T E.164 §6.
_E164_MIN_DIGITS = 8
_E164_MAX_DIGITS = 15

DEFAULT_COUNTRY_CODE = "91"

# Indian mobile numbers are exactly 10 digits and start 6-9 (TRAI's National
# Numbering Plan). Landlines never receive SMS, so they are rejected here.
_INDIA_MOBILE_RE = re.compile(r"^[6-9]\d{9}$")

# Anything a human might type between digits: spaces, hyphens, dots, brackets,
# and the "+" we re-add ourselves.
_PUNCTUATION_RE = re.compile(r"[\s\-().]+")

MAX_PHONE_INPUT_LENGTH = 24


def _strip_to_digits(raw: str) -> tuple[str, bool]:
    """Return (digits, had_plus). Distinguishes an explicit international "+"
    prefix from a bare national number, which changes how it is interpreted."""
    cleaned = _PUNCTUATION_RE.sub("", raw.strip())
    had_plus = cleaned.startswith("+")
    if had_plus:
        cleaned = cleaned[1:]
    # A leading "00" is the other common way to write an international prefix.
    elif cleaned.startswith("00"):
        cleaned = cleaned[2:]
        had_plus = True
    if not cleaned.isdigit():
        raise ValidationAppError("Enter a valid mobile number.")
    return cleaned, had_plus


def normalize_phone(raw: str, *, default_country_code: str = DEFAULT_COUNTRY_CODE) -> str:
    """Return `raw` as E.164, or raise ValidationAppError.

    Accepts the forms customers actually type: "9876543210", "09876543210",
    "+91 98765-43210", "0091 9876543210", "91 9876543210".
    """
    if not isinstance(raw, str) or not raw.strip():
        raise ValidationAppError("Enter your mobile number.")
    if len(raw) > MAX_PHONE_INPUT_LENGTH:
        raise ValidationAppError("Enter a valid mobile number.")

    digits, had_plus = _strip_to_digits(raw)
    if not digits:
        raise ValidationAppError("Enter your mobile number.")

    if not had_plus:
        # No "+" means the customer typed a *national* number, and the national
        # numbering plan here is India's. It must therefore be an Indian mobile —
        # falling back to "treat the digits as E.164" would silently read
        # "1234567890" as +1 234-567-890 and text a stranger in North America.
        national = digits.lstrip("0")
        # "919876543210" typed without a "+" still carries the country code.
        if national.startswith(default_country_code) and _INDIA_MOBILE_RE.fullmatch(
            national[len(default_country_code) :]
        ):
            national = national[len(default_country_code) :]
        if not _INDIA_MOBILE_RE.fullmatch(national):
            raise ValidationAppError(
                "Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9, "
                "or include the country code (for example +44…)."
            )
        return f"+{default_country_code}{national}"

    # An explicit "+" means the customer told us the country code.
    if digits.startswith(DEFAULT_COUNTRY_CODE):
        subscriber = digits[len(DEFAULT_COUNTRY_CODE) :]
        if not _INDIA_MOBILE_RE.fullmatch(subscriber):
            raise ValidationAppError(
                "Enter a valid 10-digit Indian mobile number starting with 6, 7, 8 or 9."
            )
        return f"+{digits}"

    if not _E164_MIN_DIGITS <= len(digits) <= _E164_MAX_DIGITS:
        raise ValidationAppError("Enter a valid mobile number with its country code.")
    return f"+{digits}"


def is_indian_mobile(phone_e164: str) -> bool:
    """True when `phone_e164` is an Indian mobile. Callers that can only reach
    Indian destinations (the Fast2SMS OTP route) gate on this."""
    if not phone_e164.startswith(f"+{DEFAULT_COUNTRY_CODE}"):
        return False
    return bool(_INDIA_MOBILE_RE.fullmatch(phone_e164[1 + len(DEFAULT_COUNTRY_CODE) :]))


def national_number(phone_e164: str) -> str:
    """The subscriber digits without the "+" or country code. Fast2SMS's OTP
    route addresses Indian numbers this way (bare 10 digits)."""
    if not is_indian_mobile(phone_e164):
        raise ValidationAppError("Only Indian mobile numbers are supported here.")
    return phone_e164[1 + len(DEFAULT_COUNTRY_CODE) :]


def mask_phone(phone_e164: str) -> str:
    """A display form safe for UI and logs: "+91 ••••• 43210". Enough for a
    customer to recognise their own number, not enough to leak someone else's."""
    if not phone_e164.startswith("+"):
        return "•••••"
    digits = phone_e164[1:]
    if len(digits) <= 4:
        return f"+{'•' * len(digits)}"
    return f"+{digits[:2]} {'•' * (len(digits) - 6)} {digits[-4:]}"

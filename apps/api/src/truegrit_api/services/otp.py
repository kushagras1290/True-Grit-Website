"""One-time passcode challenges for mobile-number verification.

The lifecycle of a challenge is one row in `phone_otp_challenges`:

    issue -> (resend*) -> verify -> redeem

`issue` mints a passcode, stores only its hash, and texts it. `verify` checks a
submitted code and, on success, mints a short-lived *proof token* — again stored
only as a hash. `redeem` exchanges that token for the thing the caller actually
wanted: a session, a new account, or a phone attached to an existing account.

Why the extra token step instead of verify returning a session directly: a
phone-first signup has no account yet, so verify cannot log anyone in. It has to
hand back something the browser can present alongside the profile details that
come next. Splitting it also keeps *proving a phone* separate from *what proving
it entitles you to* — email registration, phone signup, and adding a number to a
Google account all reuse one verified-phone primitive.

Defence in depth, since an OTP is a 6-digit secret guarding a whole account:

* Codes and tokens are stored as SHA-256 hashes; a database leak yields neither.
* Comparison is constant-time — a timing oracle on a 6-digit space is not
  theoretical.
* Three independent ceilings: guesses per challenge (`otp_max_attempts`), texts
  per challenge (`otp_max_resends` + cooldown), and issuance per phone and per IP
  (DB-backed `auth_rate_limits`). The first stops guessing, the second stops
  someone burning our SMS credit or harassing a handset, the third stops
  enumeration across many numbers.
* `issue` never reveals whether the number is registered. Account existence is
  resolved at redeem time, after the caller has proven they hold the handset.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from truegrit_api.auth.rate_limit import RateLimitRule, enforce_rate_limit, hash_identifier
from truegrit_api.auth.sessions import hash_token
from truegrit_api.config import Settings
from truegrit_api.domain.phone import mask_phone
from truegrit_api.errors import ValidationAppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.sms import send_sms
from truegrit_api.util.ids import new_id
from truegrit_api.util.timeutil import utc_now_iso

_ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# How long a proof token stays exchangeable after the code is accepted. Long
# enough to type a name and pick a password, short enough that an abandoned tab
# is not a standing credential.
_TOKEN_LIFETIME_SECONDS = 900

PURPOSE_SIGN_IN = "sign_in"
PURPOSE_REGISTER = "register"
PURPOSE_ADD_PHONE = "add_phone"
_PURPOSES = frozenset({PURPOSE_SIGN_IN, PURPOSE_REGISTER, PURPOSE_ADD_PHONE})


class PhoneVerificationRequiredError(ValidationAppError):
    """The proof token is missing, spent, expired, or for another purpose.

    Distinct from a plain validation error so the browser can tell "start the SMS
    dance again" apart from "fix this field". Without it, a duplicate-email
    rejection and a burnt token look identical, and the UI would send a second
    (chargeable) text to recover from a typo.
    """

    code = "phone_verification_required"


@dataclass(frozen=True)
class IssuedChallenge:
    """What the browser needs to drive the code-entry screen. Deliberately
    carries no hint about whether the number is registered."""

    challenge_id: str
    phone_masked: str
    expires_at: str
    resends_remaining: int


@dataclass(frozen=True)
class VerifiedPhone:
    """Proof that the caller holds `phone_e164`, exchangeable once."""

    phone_e164: str
    purpose: str
    user_id: str | None
    verification_token: str
    token_expires_at: str


@dataclass(frozen=True)
class RedeemedPhone:
    phone_e164: str
    purpose: str
    user_id: str | None


def _iso(moment: datetime) -> str:
    return moment.strftime(_ISO_FORMAT)


def _generate_code(length: int) -> str:
    """A uniformly random decimal passcode, zero-padded to `length`.

    `secrets.randbelow` over the full range keeps every code equally likely,
    including ones with leading zeros — building it digit-by-digit or reaching
    for `randint` invites subtle bias.
    """
    if length < 4:
        raise ValueError("OTP length must be at least 4 digits.")
    return str(secrets.randbelow(10**length)).zfill(length)


async def _enforce_issue_limits(
    db: Database, *, phone_e164: str, client_ip_value: str, settings: Settings
) -> None:
    """Cap issuance per handset and per caller. Both matter: the phone bucket
    protects the number's owner and our SMS bill, the IP bucket stops one host
    sweeping many numbers."""
    if not settings.rate_limit_enabled:
        return
    rule = RateLimitRule(settings.rate_limit_otp_per_phone, settings.rate_limit_otp_window_seconds)
    await enforce_rate_limit(db, key=f"otp:phone:{hash_identifier(phone_e164)}", rule=rule)
    await enforce_rate_limit(
        db,
        key=f"otp:ip:{hash_identifier(client_ip_value)}",
        rule=RateLimitRule(settings.rate_limit_otp_per_ip, settings.rate_limit_otp_window_seconds),
    )


async def issue_challenge(
    db: Database,
    *,
    phone_e164: str,
    purpose: str,
    client_ip_value: str,
    settings: Settings,
    user_id: str | None = None,
) -> IssuedChallenge:
    """Mint a passcode for `phone_e164` and text it.

    Raises SmsDeliveryError / SmsConfigurationError if the message cannot be
    sent — the row is written first so a delivery failure still counts against
    the rate limit and cannot be used as a free retry oracle.
    """
    if purpose not in _PURPOSES:
        raise ValueError(f"Unknown OTP purpose: {purpose!r}")

    await _enforce_issue_limits(
        db, phone_e164=phone_e164, client_ip_value=client_ip_value, settings=settings
    )

    now = datetime.now(UTC)
    code = _generate_code(settings.otp_length)
    challenge_id = new_id("otp")
    expires_at = _iso(now + timedelta(seconds=settings.otp_lifetime_seconds))

    await db.execute(
        """
        INSERT INTO phone_otp_challenges (
          id, phone_e164, user_id, purpose, code_hash, attempt_count, resend_count,
          last_sent_at, expires_at, verified_at, verification_token_hash,
          token_expires_at, redeemed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?, NULL, NULL, NULL, NULL, ?)
        """,
        (
            challenge_id,
            phone_e164,
            user_id,
            purpose,
            hash_token(code),
            _iso(now),
            expires_at,
            _iso(now),
        ),
    )

    await send_sms(phone_e164, code, settings)
    log_event(
        "info",
        "otp_issued",
        challenge_id=challenge_id,
        purpose=purpose,
        to=mask_phone(phone_e164),
    )
    return IssuedChallenge(
        challenge_id=challenge_id,
        phone_masked=mask_phone(phone_e164),
        expires_at=expires_at,
        resends_remaining=settings.otp_max_resends,
    )


async def resend_challenge(
    db: Database, *, challenge_id: str, settings: Settings
) -> IssuedChallenge:
    """Text a *fresh* passcode for an existing challenge.

    A new code — not the old one — because we only ever stored the old one's
    hash. That is a feature: a resend invalidates whatever was in the earlier
    message, so an SMS sitting in a notification shade goes stale.
    """
    row = await db.fetch_one(
        """
        SELECT id, phone_e164, purpose, resend_count, last_sent_at, expires_at, verified_at
        FROM phone_otp_challenges WHERE id = ?
        """,
        (challenge_id,),
    )
    if row is None or row["verified_at"] is not None:
        raise ValidationAppError("That code request is no longer valid. Start again.")

    now = datetime.now(UTC)
    if row["expires_at"] <= _iso(now):
        raise ValidationAppError("That code has expired. Request a new one.")
    if row["resend_count"] >= settings.otp_max_resends:
        raise ValidationAppError(
            "You've requested too many codes. Please start again in a few minutes."
        )
    cooldown_ends = _iso(now - timedelta(seconds=settings.otp_resend_cooldown_seconds))
    if row["last_sent_at"] > cooldown_ends:
        raise ValidationAppError(
            f"Please wait {settings.otp_resend_cooldown_seconds} seconds before asking again."
        )

    code = _generate_code(settings.otp_length)
    expires_at = _iso(now + timedelta(seconds=settings.otp_lifetime_seconds))
    # Reset the guess budget alongside the new code: the customer is starting
    # over on a code they can actually read, and attempts spent on the previous
    # one should not strand them.
    await db.execute(
        """
        UPDATE phone_otp_challenges
        SET code_hash = ?, expires_at = ?, last_sent_at = ?,
            resend_count = resend_count + 1, attempt_count = 0
        WHERE id = ? AND verified_at IS NULL
        """,
        (hash_token(code), expires_at, _iso(now), challenge_id),
    )

    await send_sms(row["phone_e164"], code, settings)
    log_event("info", "otp_resent", challenge_id=challenge_id, to=mask_phone(row["phone_e164"]))
    return IssuedChallenge(
        challenge_id=challenge_id,
        phone_masked=mask_phone(row["phone_e164"]),
        expires_at=expires_at,
        resends_remaining=max(0, settings.otp_max_resends - (int(row["resend_count"]) + 1)),
    )


async def verify_challenge(
    db: Database, *, challenge_id: str, code: str, settings: Settings
) -> VerifiedPhone:
    """Check `code` against the challenge and mint a proof token on success."""
    row = await db.fetch_one(
        """
        SELECT id, phone_e164, user_id, purpose, code_hash, attempt_count,
               expires_at, verified_at
        FROM phone_otp_challenges WHERE id = ?
        """,
        (challenge_id,),
    )
    # One message for "no such challenge", "already used" and "expired": which of
    # those it is tells an attacker something and tells a customer nothing they
    # can act on differently.
    if row is None or row["verified_at"] is not None:
        raise ValidationAppError("That code is not valid. Request a new one.")

    now = datetime.now(UTC)
    if row["expires_at"] <= _iso(now):
        raise ValidationAppError("That code has expired. Request a new one.")
    if int(row["attempt_count"]) >= settings.otp_max_attempts:
        raise ValidationAppError("Too many incorrect attempts. Request a new code.")

    # Spend the attempt before judging it, so a crash or a dropped connection
    # mid-verify cannot hand back a free guess.
    await db.execute(
        "UPDATE phone_otp_challenges SET attempt_count = attempt_count + 1 WHERE id = ?",
        (challenge_id,),
    )

    submitted = (code or "").strip()
    if not hmac.compare_digest(hash_token(submitted), str(row["code_hash"])):
        remaining = settings.otp_max_attempts - (int(row["attempt_count"]) + 1)
        log_event(
            "warning",
            "otp_incorrect",
            challenge_id=challenge_id,
            to=mask_phone(row["phone_e164"]),
            attempts_remaining=max(0, remaining),
        )
        if remaining <= 0:
            raise ValidationAppError("Too many incorrect attempts. Request a new code.")
        raise ValidationAppError("That code is not correct.")

    token = secrets.token_urlsafe(32)
    token_expires_at = _iso(now + timedelta(seconds=_TOKEN_LIFETIME_SECONDS))
    await db.execute(
        """
        UPDATE phone_otp_challenges
        SET verified_at = ?, verification_token_hash = ?, token_expires_at = ?
        WHERE id = ? AND verified_at IS NULL
        """,
        (_iso(now), hash_token(token), token_expires_at, challenge_id),
    )
    log_event(
        "info",
        "otp_verified",
        challenge_id=challenge_id,
        purpose=row["purpose"],
        to=mask_phone(row["phone_e164"]),
    )
    return VerifiedPhone(
        phone_e164=row["phone_e164"],
        purpose=row["purpose"],
        user_id=row["user_id"],
        verification_token=token,
        token_expires_at=token_expires_at,
    )


async def redeem_token(
    db: Database, *, token: str, expected_purpose: str | None = None
) -> RedeemedPhone:
    """Consume a proof token exactly once and return the phone it proves.

    The single-use guarantee rests on the conditional UPDATE below rather than a
    read-then-write: two tabs racing the same token must not both create an
    account. `changes == 0` means somebody else got there first.
    """
    row = await db.fetch_one(
        """
        SELECT id, phone_e164, user_id, purpose, token_expires_at, redeemed_at
        FROM phone_otp_challenges
        WHERE verification_token_hash = ? AND verified_at IS NOT NULL
        """,
        (hash_token(token or ""),),
    )
    if row is None or row["redeemed_at"] is not None:
        raise PhoneVerificationRequiredError(
            "Your verification has expired. Please verify your number again."
        )
    if str(row["token_expires_at"]) <= utc_now_iso():
        raise PhoneVerificationRequiredError(
            "Your verification has expired. Please verify your number again."
        )
    if expected_purpose is not None and row["purpose"] != expected_purpose:
        raise PhoneVerificationRequiredError("Your verification does not match this request.")

    changed = await db.execute(
        "UPDATE phone_otp_challenges SET redeemed_at = ? WHERE id = ? AND redeemed_at IS NULL",
        (utc_now_iso(), row["id"]),
    )
    if changed == 0:
        raise PhoneVerificationRequiredError("Your verification has already been used.")

    return RedeemedPhone(
        phone_e164=row["phone_e164"], purpose=row["purpose"], user_id=row["user_id"]
    )

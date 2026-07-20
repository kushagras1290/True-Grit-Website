"""Mobile-number authentication: sign in, sign up, and verify by SMS passcode.

Three entry points, one primitive:

    POST /phone/start    -> text a passcode              (unauthenticated)
    POST /phone/resend   -> text a fresh passcode        (unauthenticated)
    POST /phone/verify   -> exchange passcode for proof  (unauthenticated)
    POST /phone/complete -> proof -> session             (unauthenticated)
    POST /phone/attach   -> proof -> phone on my account (authenticated)

`verify` deliberately does not log anyone in. A phone-first customer may not have
an account yet, so verify returns a single-use proof token and `complete` decides
what it is worth: sign the existing holder in, or create an account once the
customer supplies a name. The same proof also feeds email registration
(`/auth/register`) and `attach`.

Account existence is never revealed before the caller proves they hold the
handset — `start` answers identically for a registered and an unregistered
number, so the endpoint cannot be used to enumerate customers.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from truegrit_api.auth.dependencies import get_current_customer, get_database
from truegrit_api.auth.principal import Principal
from truegrit_api.auth.rate_limit import client_ip
from truegrit_api.auth.sessions import start_session
from truegrit_api.config import get_settings
from truegrit_api.domain.phone import MAX_PHONE_INPUT_LENGTH, normalize_phone
from truegrit_api.errors import AuthenticationError, ValidationAppError
from truegrit_api.platform.database import Database
from truegrit_api.services import otp as otp_service
from truegrit_api.services.phone_accounts import (
    account_payload,
    attach_verified_phone,
    create_phone_only_account,
    find_user_by_phone,
    get_account,
)

router = APIRouter(tags=["phone-auth"])

_MAX_NAME_LENGTH = 120
_MAX_CODE_LENGTH = 12
_MAX_TOKEN_LENGTH = 128
_MAX_CHALLENGE_ID_LENGTH = 64


class _CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class PhoneStartRequest(_CamelModel):
    phone: str = Field(min_length=1, max_length=MAX_PHONE_INPUT_LENGTH)


class PhoneResendRequest(_CamelModel):
    challenge_id: str = Field(min_length=1, max_length=_MAX_CHALLENGE_ID_LENGTH)


class PhoneVerifyRequest(_CamelModel):
    challenge_id: str = Field(min_length=1, max_length=_MAX_CHALLENGE_ID_LENGTH)
    code: str = Field(min_length=1, max_length=_MAX_CODE_LENGTH)


class PhoneCompleteRequest(_CamelModel):
    verification_token: str = Field(min_length=1, max_length=_MAX_TOKEN_LENGTH)
    # Only consulted when the number turns out to be new. Sending it up front
    # keeps the browser from having to ask whether the account exists — which is
    # exactly the question we refuse to answer before verification.
    name: str | None = Field(default=None, max_length=_MAX_NAME_LENGTH)


class PhoneAttachRequest(_CamelModel):
    verification_token: str = Field(min_length=1, max_length=_MAX_TOKEN_LENGTH)


def _challenge_payload(challenge: otp_service.IssuedChallenge) -> dict[str, Any]:
    return {
        "challengeId": challenge.challenge_id,
        "phoneMasked": challenge.phone_masked,
        "expiresAt": challenge.expires_at,
        "resendsRemaining": challenge.resends_remaining,
    }


@router.post("/phone/start")
async def phone_start(
    payload: PhoneStartRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Text a passcode to `phone`, for signing in or signing up.

    The response is identical whether or not the number has an account.
    """
    settings = get_settings()
    phone_e164 = normalize_phone(payload.phone)
    challenge = await otp_service.issue_challenge(
        db,
        phone_e164=phone_e164,
        purpose=otp_service.PURPOSE_SIGN_IN,
        client_ip_value=client_ip(request),
        settings=settings,
    )
    return {"ok": True, **_challenge_payload(challenge)}


@router.post("/phone/resend")
async def phone_resend(
    payload: PhoneResendRequest,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    challenge = await otp_service.resend_challenge(
        db, challenge_id=payload.challenge_id, settings=get_settings()
    )
    return {"ok": True, **_challenge_payload(challenge)}


@router.post("/phone/verify")
async def phone_verify(
    payload: PhoneVerifyRequest,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Check the passcode and return single-use proof of the number.

    `registered` tells the browser whether to ask for a name next. It is safe to
    disclose here and only here: the caller has just demonstrated they hold the
    handset, so it is their own account status they are learning.
    """
    verified = await otp_service.verify_challenge(
        db, challenge_id=payload.challenge_id, code=payload.code, settings=get_settings()
    )
    registered = await find_user_by_phone(db, verified.phone_e164) is not None
    return {
        "ok": True,
        "verificationToken": verified.verification_token,
        "expiresAt": verified.token_expires_at,
        "registered": registered,
    }


@router.post("/phone/complete")
async def phone_complete(
    payload: PhoneCompleteRequest,
    response: Response,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Exchange proof of a number for a session — signing in or signing up."""
    settings = get_settings()
    redeemed = await otp_service.redeem_token(
        db, token=payload.verification_token, expected_purpose=otp_service.PURPOSE_SIGN_IN
    )

    user = await find_user_by_phone(db, redeemed.phone_e164)
    if user is None:
        name = (payload.name or "").strip()
        if not name:
            # The browser asks for a name once `verify` reports registered=false;
            # reaching here without one means it skipped that step.
            raise ValidationAppError("Enter your name to finish creating your account.")
        user = await create_phone_only_account(
            db, phone_e164=redeemed.phone_e164, display_name=name
        )
        summary = "customer-phone-register"
    else:
        summary = "customer-phone-login"

    await start_session(
        db, response, user_id=user["id"], settings=settings, user_agent_summary=summary
    )
    return {"ok": True, "customer": account_payload(user)}


@router.post("/phone/attach")
async def phone_attach(
    payload: PhoneAttachRequest,
    principal: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Record a verified mobile against the signed-in account.

    This is the path for accounts that predate phone verification and for Google
    sign-ups, which arrive with an email and no number.
    """
    redeemed = await otp_service.redeem_token(
        db, token=payload.verification_token, expected_purpose=otp_service.PURPOSE_ADD_PHONE
    )
    if redeemed.user_id is not None and redeemed.user_id != principal.user_id:
        # The challenge was issued to a different session. Refuse rather than
        # trust the token alone.
        raise AuthenticationError("That verification belongs to a different account.")

    await attach_verified_phone(db, user_id=principal.user_id, phone_e164=redeemed.phone_e164)
    user = await get_account(db, principal.user_id)
    if user is None:
        raise AuthenticationError("This account is not available.")
    return {"ok": True, "customer": account_payload(user)}


@router.post("/phone/attach/start")
async def phone_attach_start(
    payload: PhoneStartRequest,
    request: Request,
    principal: Annotated[Principal, Depends(get_current_customer)],
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Text a passcode to a number the signed-in customer wants to add."""
    settings = get_settings()
    phone_e164 = normalize_phone(payload.phone)
    challenge = await otp_service.issue_challenge(
        db,
        phone_e164=phone_e164,
        purpose=otp_service.PURPOSE_ADD_PHONE,
        client_ip_value=client_ip(request),
        settings=settings,
        user_id=principal.user_id,
    )
    return {"ok": True, **_challenge_payload(challenge)}


@router.post("/phone/register/start")
async def phone_register_start(
    payload: PhoneStartRequest,
    request: Request,
    db: Annotated[Database, Depends(get_database)],
) -> Any:
    """Text a passcode for a number being verified during email registration.

    Separate from `/phone/start` because the proof it yields is scoped to
    registration: it can create an email+password account but cannot, on its own,
    sign anyone in.
    """
    settings = get_settings()
    phone_e164 = normalize_phone(payload.phone)
    challenge = await otp_service.issue_challenge(
        db,
        phone_e164=phone_e164,
        purpose=otp_service.PURPOSE_REGISTER,
        client_ip_value=client_ip(request),
        settings=settings,
    )
    return {"ok": True, **_challenge_payload(challenge)}

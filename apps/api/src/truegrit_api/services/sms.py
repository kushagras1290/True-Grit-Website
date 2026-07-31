"""Transactional SMS (one-time passcodes).

Mirrors `services.email`: a narrow `SmsSender` protocol with a real provider when
configured and a console sender that logs the message otherwise, so the whole
phone-verification flow is exercisable locally with no account and no spend.

Two things differ from email, both deliberate:

* **Delivery failures raise.** A dropped order email is a nuisance the customer
  can work around; a dropped OTP is a dead end — they would sit staring at a code
  field waiting for a message that is never coming. Callers need to know, so
  errors propagate instead of being swallowed.
* **The console sender is refused in production.** It writes the passcode to the
  log, which is fine on a laptop and an account-takeover vector anywhere real:
  anyone with log access could read live OTPs. Better to fail loudly at the first
  send than to silently ship that.

Provider choice: Cloudflare Workers cannot open raw sockets, so the provider must
speak HTTP — `platform.http.post_json_async` handles both the Workers `fetch` and
the local stdlib path. Fast2SMS is wired because its `route=otp` reaches Indian
mobiles on the provider's own pre-approved DLT header, so there is no ₹5,900 TRAI
DLT registration to complete before going live. We generate and verify the code
ourselves and hand the provider only the delivery job, which keeps verification
in our database and makes swapping providers a single class.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from truegrit_api.config import Settings, get_settings
from truegrit_api.domain.phone import is_indian_mobile, mask_phone, national_number
from truegrit_api.errors import AppError
from truegrit_api.logging import log_event
from truegrit_api.platform.http import HttpError, post_json_async

_FAST2SMS_ENDPOINT = "https://www.fast2sms.com/dev/bulkV2"
_FAST2SMS_OTP_ROUTE = "otp"


class SmsConfigurationError(AppError):
    """No usable SMS sender for this environment. Operator error, not customer
    error, so it must never read like the customer did something wrong."""

    code = "sms_unavailable"
    http_status = 503

    def __init__(self, message: str = "Text-message sending is not available right now."):
        super().__init__(message)


class SmsDeliveryError(AppError):
    """The provider was reached but would not deliver the message."""

    code = "sms_delivery_failed"
    http_status = 502

    def __init__(self, message: str = "We could not send that text message. Please try again."):
        super().__init__(message)


@dataclass(frozen=True)
class OutboundSms:
    to_e164: str
    body: str


class SmsSender(Protocol):
    async def send(self, message: OutboundSms) -> None: ...


class ConsoleSmsSender:
    """Logs the message instead of sending it. Default when no provider is
    configured; `get_sms_sender` refuses to hand this out in production."""

    async def send(self, message: OutboundSms) -> None:
        log_event(
            "warning",
            "sms_console",
            to=mask_phone(message.to_e164),
            body=message.body,
            note="SMS provider not configured; message logged, not delivered",
        )


class Fast2SmsSender:
    """Fast2SMS `route=otp`.

    The route takes a bare 10-digit Indian number (no country code) and renders
    the value into the provider's pre-approved template as "Your OTP: {#var#}",
    which is why the code — not the full sentence — is what gets sent.
    """

    def __init__(self, settings: Settings) -> None:
        self._api_key = settings.fast2sms_api_key

    async def send(self, message: OutboundSms) -> None:
        if not is_indian_mobile(message.to_e164):
            # Route limitation, not a bad number: say so precisely.
            raise SmsDeliveryError("We can only text Indian mobile numbers at the moment.")
        payload: dict[str, Any] = {
            "route": _FAST2SMS_OTP_ROUTE,
            "variables_values": message.body,
            "numbers": national_number(message.to_e164),
        }
        try:
            response = await post_json_async(
                _FAST2SMS_ENDPOINT,
                body=payload,
                headers={"authorization": self._api_key},
            )
        except HttpError as exc:
            # The exception text can carry a fragment of the provider response;
            # log the type only so an API key or code never lands in the log.
            log_event(
                "error",
                "sms_send_failed",
                provider="fast2sms",
                to=mask_phone(message.to_e164),
                error_type=type(exc).__name__,
            )
            raise SmsDeliveryError() from exc

        # Fast2SMS answers 200 with {"return": false, ...} on rejection, so the
        # HTTP status alone does not mean the message went anywhere.
        if not (isinstance(response, dict) and response.get("return") is True):
            log_event(
                "error",
                "sms_rejected",
                provider="fast2sms",
                to=mask_phone(message.to_e164),
                provider_message=str(response)[:200] if response is not None else "",
            )
            raise SmsDeliveryError()

        log_event(
            "info",
            "sms_sent",
            provider="fast2sms",
            to=mask_phone(message.to_e164),
            request_id=str(response.get("request_id", ""))[:64],
        )


def get_sms_sender(settings: Settings | None = None) -> SmsSender:
    """The configured provider, or the console sender outside production.

    Raises SmsConfigurationError rather than returning a console sender in
    staging/production: logging live passcodes there is worse than an outage.
    """
    settings = settings or get_settings()
    if settings.fast2sms_enabled:
        return Fast2SmsSender(settings)
    if settings.app_env in {"staging", "production"}:
        log_event("error", "sms_provider_missing", app_env=settings.app_env)
        raise SmsConfigurationError()
    return ConsoleSmsSender()


async def send_sms(to_e164: str, body: str, settings: Settings | None = None) -> None:
    """Send `body` to `to_e164`. Raises on any failure — see the module docstring
    for why this does not follow email's best-effort convention."""
    await get_sms_sender(settings).send(OutboundSms(to_e164=to_e164, body=body))

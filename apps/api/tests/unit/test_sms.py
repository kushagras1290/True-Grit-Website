"""Unit tests for SMS delivery.

The rule worth guarding here is the one that is easy to regress and expensive to
discover: the console sender writes live passcodes into the log, so it must never
be reachable in staging or production.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import pytest

from truegrit_api.config import Settings
from truegrit_api.services.sms import (
    ConsoleSmsSender,
    Fast2SmsSender,
    OutboundSms,
    SmsConfigurationError,
    SmsDeliveryError,
    get_sms_sender,
)

AppEnv = Literal["development", "test", "staging", "production"]


def settings_for(app_env: AppEnv, api_key: str = "") -> Settings:
    return Settings(app_env=app_env, fast2sms_api_key=api_key)


@pytest.mark.parametrize("app_env", ["development", "test"])
def test_console_sender_is_the_local_fallback(app_env: AppEnv):
    assert isinstance(get_sms_sender(settings_for(app_env)), ConsoleSmsSender)


@pytest.mark.parametrize("app_env", ["staging", "production"])
def test_console_sender_is_refused_outside_development(app_env: AppEnv):
    """Logging a live OTP is an account-takeover vector for anyone with log
    access. An outage is the better failure."""
    with pytest.raises(SmsConfigurationError):
        get_sms_sender(settings_for(app_env))


@pytest.mark.parametrize("app_env", ["development", "staging", "production"])
def test_configured_provider_wins_everywhere(app_env: AppEnv):
    assert isinstance(get_sms_sender(settings_for(app_env, "key-123")), Fast2SmsSender)


def test_sms_enabled_reflects_whether_a_handset_can_be_reached():
    assert settings_for("production").sms_enabled is False
    assert settings_for("production", "key-123").sms_enabled is True
    # Locally the console sender stands in, so the flow stays exercisable.
    assert settings_for("development").sms_enabled is True


def test_fast2sms_rejects_non_indian_numbers():
    """`route=otp` only addresses Indian mobiles, so fail before spending a
    request rather than letting the provider reject it."""
    sender = Fast2SmsSender(settings_for("production", "key-123"))
    with pytest.raises(SmsDeliveryError):
        asyncio.run(sender.send(OutboundSms(to_e164="+442071838750", body="123456")))


def test_fast2sms_treats_a_200_with_return_false_as_failure(monkeypatch):
    """The provider answers HTTP 200 with {"return": false} on rejection, so the
    status code alone does not mean the text was delivered."""
    calls: list[dict] = []

    async def fake_post(_url, *, body, headers=None):
        calls.append(body)
        return {"return": False, "message": ["Insufficient balance"]}

    monkeypatch.setattr("truegrit_api.services.sms.post_json_async", fake_post)
    sender = Fast2SmsSender(settings_for("production", "key-123"))
    with pytest.raises(SmsDeliveryError):
        asyncio.run(sender.send(OutboundSms(to_e164="+919876543210", body="123456")))
    assert calls[0]["numbers"] == "9876543210"  # bare national digits
    assert calls[0]["route"] == "otp"


def test_fast2sms_sends_national_digits_and_the_code(monkeypatch):
    sent: list[dict] = []

    async def fake_post(url, *, body, headers=None):
        sent.append({"url": url, "body": body, "headers": headers})
        return {"return": True, "request_id": "abc123"}

    monkeypatch.setattr("truegrit_api.services.sms.post_json_async", fake_post)
    sender = Fast2SmsSender(settings_for("production", "key-123"))
    asyncio.run(sender.send(OutboundSms(to_e164="+919876543210", body="654321")))

    assert sent[0]["headers"]["authorization"] == "key-123"
    assert sent[0]["body"]["variables_values"] == "654321"
    assert sent[0]["body"]["numbers"] == "9876543210"

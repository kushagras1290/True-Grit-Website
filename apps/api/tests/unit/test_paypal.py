"""Unit tests for the PayPal (international) lane.

Two things are worth guarding here. The visibility gate, because keys alone must
never put a half-built gateway in front of customers. And the INR -> foreign
currency conversion, because it is the only place in the system that invents a
number a customer is charged — an error here is money, silently, every order.
"""

from __future__ import annotations

import asyncio
from typing import Literal

import pytest

from truegrit_api.config import Settings
from truegrit_api.services.payments import (
    PaymentError,
    convert_inr_minor_to_paypal_minor,
    create_paypal_order,
    format_paypal_amount,
)

AppEnv = Literal["development", "test", "staging", "production"]


def paypal_settings(**overrides) -> Settings:
    base: dict = {
        "paypal_client_id": "client-123",
        "paypal_secret": "secret-123",
        "paypal_inr_per_unit": 88.0,
        "paypal_currency": "USD",
        "payment_paypal_visible": True,
    }
    base.update(overrides)
    return Settings(**base)


# --- Visibility gate --------------------------------------------------------


def test_keys_alone_do_not_expose_paypal():
    """The whole point of the flag: pasting a key into .env must not put an
    unfinished gateway in front of customers."""
    configured_but_hidden = paypal_settings(payment_paypal_visible=False)
    assert configured_but_hidden.paypal_configured is True
    assert configured_but_hidden.paypal_enabled is False
    assert "paypal" not in configured_but_hidden.enabled_payment_methods


def test_visible_flag_alone_does_not_expose_paypal():
    no_keys = paypal_settings(paypal_client_id="", paypal_secret="")
    assert no_keys.paypal_enabled is False
    assert "paypal" not in no_keys.enabled_payment_methods


def test_paypal_offered_only_when_configured_and_visible():
    assert "paypal" in paypal_settings().enabled_payment_methods


def test_missing_rate_counts_as_unconfigured():
    """Without a rate the charge cannot be priced, and guessing one would
    mischarge every overseas customer."""
    assert paypal_settings(paypal_inr_per_unit=0.0).paypal_configured is False
    assert paypal_settings(paypal_inr_per_unit=0.0).paypal_enabled is False


def test_inr_presentment_is_refused():
    """PayPal cannot settle a domestic INR payment to an Indian merchant, so an
    INR-denominated PayPal config is a misconfiguration, not an option."""
    assert paypal_settings(paypal_currency="INR").paypal_configured is False


def test_stripe_has_the_same_gate():
    configured = Settings(stripe_secret_key="sk_test_123", payment_stripe_visible=False)
    assert configured.stripe_configured is True
    assert configured.stripe_enabled is False
    assert "stripe" not in configured.enabled_payment_methods


def test_api_base_follows_environment():
    assert "sandbox" in paypal_settings(paypal_environment="sandbox").paypal_api_base
    assert "sandbox" not in paypal_settings(paypal_environment="live").paypal_api_base


# --- Money ------------------------------------------------------------------


def test_conversion_uses_the_configured_rate():
    settings = paypal_settings(paypal_inr_per_unit=88.0)
    # ₹948.00 / 88 = $10.77 (10.7727... -> half-up)
    assert convert_inr_minor_to_paypal_minor(settings, 94800) == 1077


def test_conversion_rounds_half_up_not_toward_even():
    settings = paypal_settings(paypal_inr_per_unit=100.0)
    # ₹1.005 -> $0.01005 -> 1.005 cents, which must round to 2, not down to 1.
    assert convert_inr_minor_to_paypal_minor(settings, 100) == 1
    # ₹0.15 at rate 10 -> 1.5 cents -> half-up = 2.
    assert convert_inr_minor_to_paypal_minor(paypal_settings(paypal_inr_per_unit=10.0), 15) == 2


def test_a_paid_order_never_converts_to_free():
    """A tiny total against a large rate must still cost something — charging
    zero would ship goods for nothing."""
    settings = paypal_settings(paypal_inr_per_unit=10000.0)
    assert convert_inr_minor_to_paypal_minor(settings, 1) == 1


def test_zero_stays_zero():
    assert convert_inr_minor_to_paypal_minor(paypal_settings(), 0) == 0


def test_conversion_is_exact_for_values_a_float_would_mangle():
    settings = paypal_settings(paypal_inr_per_unit=1.0)
    # At rate 1 the amounts are identical; a float path drifts here.
    for minor in (1, 7, 70, 115, 1_000_003):
        assert convert_inr_minor_to_paypal_minor(settings, minor) == minor


def test_unsupported_presentment_currency_is_refused():
    """JPY is zero-decimal; treating it as two-decimal would mischarge by 100x,
    so it is refused rather than silently mispriced."""
    with pytest.raises(PaymentError):
        convert_inr_minor_to_paypal_minor(paypal_settings(paypal_currency="JPY"), 94800)


def test_amount_is_formatted_as_a_fixed_decimal_string():
    assert format_paypal_amount(1077) == "10.77"
    assert format_paypal_amount(1000) == "10.00"
    assert format_paypal_amount(5) == "0.05"
    assert format_paypal_amount(0) == "0.00"


# --- Order creation ---------------------------------------------------------


def test_create_refuses_a_non_inr_order():
    """The conversion assumes an INR order; anything else must fail loudly
    rather than charge a number derived from the wrong base currency."""
    with pytest.raises(PaymentError):
        asyncio.run(
            create_paypal_order(
                paypal_settings(), amount_minor=1000, currency="USD", reference="TG-1"
            )
        )


def test_create_refuses_when_hidden():
    with pytest.raises(PaymentError):
        asyncio.run(
            create_paypal_order(
                paypal_settings(payment_paypal_visible=False),
                amount_minor=94800,
                currency="INR",
                reference="TG-1",
            )
        )


def test_create_sends_the_converted_amount(monkeypatch):
    posted: list[dict] = []

    async def fake_form(url, *, form, headers=None):
        return {"access_token": "tok-123"}

    async def fake_json(url, *, body, headers=None):
        posted.append({"url": url, "body": body, "headers": headers})
        return {"id": "PAYPAL-ORDER-1", "status": "CREATED"}

    monkeypatch.setattr("truegrit_api.services.payments.post_form_async", fake_form)
    monkeypatch.setattr("truegrit_api.services.payments.post_json_async", fake_json)

    result = asyncio.run(
        create_paypal_order(
            paypal_settings(), amount_minor=94800, currency="INR", reference="TG-1001"
        )
    )
    assert result == {
        "paypalOrderId": "PAYPAL-ORDER-1",
        "chargeMinor": 1077,
        "chargeCurrency": "USD",
    }
    amount = posted[0]["body"]["purchase_units"][0]["amount"]
    # The buyer is charged in USD, never the INR order total.
    assert amount == {"currency_code": "USD", "value": "10.77"}
    assert posted[0]["headers"]["authorization"] == "Bearer tok-123"

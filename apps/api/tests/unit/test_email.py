"""Transactional email transport selection and message shape.

The two things that made sign-up and invitation mail silently fail were both
here: a plaintext client talking to an implicit-TLS port, and messages missing
the headers providers score against. Both are cheap to regress and expensive to
notice, hence these tests.
"""

from __future__ import annotations

import json
import smtplib
import ssl
from typing import Any

import pytest

from truegrit_api.config import Settings
from truegrit_api.services.email import (
    BrevoEmailSender,
    ConsoleEmailSender,
    OutboundEmail,
    ResendEmailSender,
    SmtpEmailSender,
    choose_provider,
    email_transport_name,
    get_email_sender,
    send_email,
    split_from_address,
)


def settings(**overrides: Any) -> Settings:
    """Settings built from explicit values only — never the developer's `.env`,
    which may well hold real SMTP credentials."""
    base: dict[str, Any] = {
        "resend_api_key": "",
        "smtp_host": "",
        "smtp_port": 587,
        "smtp_username": "",
        "smtp_password": "",
        "smtp_use_tls": True,
        "smtp_implicit_tls_override": None,
        "email_from": "True Grit <no-reply@truegrit.test>",
    }
    base.update(overrides)
    return Settings(**base)


# --- Transport selection -----------------------------------------------------


def test_console_sender_when_nothing_is_configured():
    assert isinstance(get_email_sender(settings()), ConsoleEmailSender)
    assert email_transport_name(settings()) == "console"


def test_smtp_sender_when_a_host_is_configured():
    configured = settings(smtp_host="smtp.example.test")
    assert isinstance(get_email_sender(configured), SmtpEmailSender)
    assert email_transport_name(configured) == "smtp"


def test_resend_wins_over_smtp():
    """Workers cannot open raw sockets, so an HTTP API takes precedence
    wherever both are configured."""
    configured = settings(resend_api_key="re_test", smtp_host="smtp.example.test")
    assert isinstance(get_email_sender(configured), ResendEmailSender)
    assert email_transport_name(configured) == "resend"


# --- Implicit TLS ------------------------------------------------------------


def test_port_465_means_implicit_tls():
    """Port 465 is SMTPS. Talking plaintext to it hangs until the timeout, which
    is what "the invite just doesn't send" usually turns out to be."""
    assert settings(smtp_host="smtp.example.test", smtp_port=465).smtp_implicit_tls is True


def test_port_587_means_starttls():
    assert settings(smtp_host="smtp.example.test", smtp_port=587).smtp_implicit_tls is False


def test_override_beats_the_port_inference():
    """For a server on a non-standard port, the operator gets the last word."""
    assert (
        settings(
            smtp_host="smtp.example.test", smtp_port=2525, smtp_implicit_tls_override=True
        ).smtp_implicit_tls
        is True
    )
    assert (
        settings(
            smtp_host="smtp.example.test", smtp_port=465, smtp_implicit_tls_override=False
        ).smtp_implicit_tls
        is False
    )


class FakeSmtp:
    """Records the conversation so a test can assert on the sequence rather than
    on a live socket."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.sent: list[Any] = []

    def __enter__(self) -> FakeSmtp:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.calls.append("quit")

    def starttls(self, context: ssl.SSLContext | None = None) -> None:
        self.calls.append("starttls")

    def ehlo(self) -> None:
        self.calls.append("ehlo")

    def login(self, username: str, password: str) -> None:
        self.calls.append("login")

    def send_message(self, message: Any) -> None:
        self.calls.append("send")
        self.sent.append(message)


def send_via_fake(configured: Settings, monkeypatch: pytest.MonkeyPatch) -> FakeSmtp:
    fake = FakeSmtp()
    monkeypatch.setattr("smtplib.SMTP", lambda *args, **kwargs: fake)
    monkeypatch.setattr("smtplib.SMTP_SSL", lambda *args, **kwargs: fake)
    SmtpEmailSender(configured).send(
        OutboundEmail(to="member@example.test", subject="Hello", body="Body")
    )
    return fake


def test_starttls_is_issued_on_587_and_followed_by_ehlo(monkeypatch: pytest.MonkeyPatch):
    """RFC 3207: the upgrade discards everything learned before it, including
    the AUTH mechanisms the login depends on."""
    fake = send_via_fake(
        settings(smtp_host="smtp.example.test", smtp_port=587, smtp_username="user"), monkeypatch
    )
    assert fake.calls[:4] == ["starttls", "ehlo", "login", "send"]


def test_starttls_is_not_issued_on_an_implicit_tls_port(monkeypatch: pytest.MonkeyPatch):
    """The socket is already encrypted; sending STARTTLS on it is an error."""
    fake = send_via_fake(
        settings(smtp_host="smtp.example.test", smtp_port=465, smtp_username="user"), monkeypatch
    )
    assert "starttls" not in fake.calls
    assert fake.calls[:2] == ["login", "send"]


def test_login_is_skipped_without_a_username(monkeypatch: pytest.MonkeyPatch):
    fake = send_via_fake(settings(smtp_host="smtp.example.test", smtp_port=25), monkeypatch)
    assert "login" not in fake.calls


# --- Message shape -----------------------------------------------------------


def test_message_carries_date_and_a_message_id_from_the_from_domain(
    monkeypatch: pytest.MonkeyPatch,
):
    """`make_msgid()` otherwise uses the machine hostname, which on a container
    matches nothing in DNS — exactly the shape spam filters penalise."""
    fake = send_via_fake(settings(smtp_host="smtp.example.test"), monkeypatch)
    message = fake.sent[0]
    assert message["Date"]
    assert message["Message-ID"].endswith("@truegrit.test>")


def test_html_alternative_is_attached(monkeypatch: pytest.MonkeyPatch):
    fake = FakeSmtp()
    monkeypatch.setattr("smtplib.SMTP", lambda *args, **kwargs: fake)
    SmtpEmailSender(settings(smtp_host="smtp.example.test")).send(
        OutboundEmail(to="member@example.test", subject="Hi", body="Plain", html_body="<p>Rich</p>")
    )
    assert fake.sent[0].get_content_type() == "multipart/alternative"


# --- Failure handling --------------------------------------------------------


def test_send_email_never_raises_and_reports_failure(monkeypatch: pytest.MonkeyPatch):
    """A mail outage must not turn a successful order or sign-up into a failed
    request, so the error is swallowed — but the caller still learns about it."""

    def explode(*_args: object, **_kwargs: object) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"bad credentials")

    monkeypatch.setattr("smtplib.SMTP", explode)
    assert send_email("a@b.test", "s", "b", settings(smtp_host="smtp.example.test")) is False


def test_console_sender_reports_success_without_delivering():
    """The behaviour the admin console has to disclose: this "sends" fine and
    nothing arrives."""
    assert send_email("a@b.test", "s", "b", settings()) is True
    assert email_transport_name(settings()) == "console"
    assert isinstance(get_email_sender(settings()), ConsoleEmailSender)


# --- Provider precedence (services.email.choose_provider) -------------------


def test_brevo_wins_over_resend_when_both_are_configured():
    """Brevo's free tier is the reason this integration exists; with no
    admin preference set, it should be what a fresh deploy actually uses."""
    assert choose_provider(None, has_brevo=True, has_resend=True, has_smtp=True) == "brevo"


def test_resend_wins_over_smtp_when_brevo_is_not_configured():
    assert choose_provider(None, has_brevo=False, has_resend=True, has_smtp=True) == "resend"


def test_falls_through_to_smtp_then_console():
    assert choose_provider(None, has_brevo=False, has_resend=False, has_smtp=True) == "smtp"
    assert choose_provider(None, has_brevo=False, has_resend=False, has_smtp=False) == "console"


def test_admin_preference_wins_only_when_that_provider_is_configured():
    """A preference cannot conjure a missing API key -- same 'a switch can
    only take something away' rule feature_settings.py documents."""
    assert choose_provider("resend", has_brevo=True, has_resend=True, has_smtp=False) == "resend"
    # Preferred Resend but no Resend key: falls through to whatever else works.
    assert choose_provider("resend", has_brevo=True, has_resend=False, has_smtp=False) == "brevo"
    assert choose_provider("brevo", has_brevo=False, has_resend=True, has_smtp=False) == "resend"


# --- Brevo transport ----------------------------------------------------------


class FakeHttpResponse:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> FakeHttpResponse:
        return self

    def __exit__(self, *_exc: object) -> bool:
        return False


def test_brevo_sender_posts_split_sender_and_api_key_header(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float | None = None) -> FakeHttpResponse:
        captured["request"] = request
        return FakeHttpResponse(200)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    BrevoEmailSender(
        settings(brevo_api_key="brevo_test", email_from="True Grit <no-reply@truegrit.test>")
    ).send(OutboundEmail(to="a@b.test", subject="Hi", body="Body", html_body="<p>Hi</p>"))

    request = captured["request"]
    assert request.full_url == "https://api.brevo.com/v3/smtp/email"
    assert request.get_header("Api-key") == "brevo_test"
    payload = json.loads(request.data)
    assert payload["sender"] == {"email": "no-reply@truegrit.test", "name": "True Grit"}
    assert payload["to"] == [{"email": "a@b.test"}]
    assert payload["textContent"] == "Body"
    assert payload["htmlContent"] == "<p>Hi</p>"


def test_brevo_sender_raises_on_http_error(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("urllib.request.urlopen", lambda *a, **k: FakeHttpResponse(422))
    with pytest.raises(OSError):
        BrevoEmailSender(settings(brevo_api_key="brevo_test")).send(
            OutboundEmail(to="a@b.test", subject="Hi", body="Body")
        )


def test_split_from_address_separates_name_and_address():
    assert split_from_address("True Grit <no-reply@x.test>") == ("True Grit", "no-reply@x.test")
    assert split_from_address("bare@x.test") == ("", "bare@x.test")


def test_brevo_is_picked_over_resend_end_to_end():
    configured = settings(brevo_api_key="brevo_test", resend_api_key="re_test")
    assert isinstance(get_email_sender(configured), BrevoEmailSender)
    assert email_transport_name(configured) == "brevo"


def test_preferred_provider_is_forwarded_through_send_email(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: float | None = None) -> FakeHttpResponse:
        captured["url"] = request.full_url
        return FakeHttpResponse(200)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    configured = settings(brevo_api_key="brevo_test", resend_api_key="re_test")
    assert send_email("a@b.test", "s", "b", configured, preferred_provider="resend") is True
    assert captured["url"] == configured.resend_api_url

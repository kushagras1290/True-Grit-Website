"""Transactional email (order notifications, password resets).

Cloudflare Workers cannot open raw SMTP sockets, so production on Workers should
use an HTTP email API; locally (uvicorn) stdlib ``smtplib`` works. This module
hides that behind a tiny ``EmailSender`` protocol: a real SMTP sender when
``smtp_host`` is configured, otherwise a console sender that logs the message —
dev-safe and keeps the flows that trigger email fully testable.

Sending is best-effort: a failure is logged, never raised into the caller, so a
mail outage can never break an order or a password reset. `send_email` reports
what actually happened via its return value (`True` delivered, `False` failed)
so callers that need to know -- e.g. to tell a user "invite created but the
email could not be confirmed sent" -- can check it. Fire-and-forget callers
(most background-task sends) can keep ignoring the return value exactly as
before; nothing about their behaviour changes.
"""

from __future__ import annotations

import json
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Protocol

from truegrit_api.config import Settings, get_settings
from truegrit_api.logging import log_event


@dataclass(frozen=True)
class OutboundEmail:
    to: str
    subject: str
    body: str
    html_body: str | None = None


class EmailSender(Protocol):
    def send(self, message: OutboundEmail) -> None: ...


class ConsoleEmailSender:
    """Logs the email instead of sending it. Default when SMTP is unconfigured."""

    def send(self, message: OutboundEmail) -> None:
        log_event(
            "info",
            "email_console",
            to=message.to,
            subject=message.subject,
            preview=message.body[:200],
        )


class SmtpEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: OutboundEmail) -> None:
        settings = self._settings
        email = EmailMessage()
        email["From"] = settings.email_from
        email["To"] = message.to
        email["Subject"] = message.subject
        email.set_content(message.body)

        if message.html_body:
            email.add_alternative(message.html_body, subtype="html")

        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(email)


class ResendEmailSender:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def send(self, message: OutboundEmail) -> None:
        settings = self._settings
        payload: dict[str, object] = {
            "from": settings.email_from,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }
        if message.html_body:
            payload["html"] = message.html_body
        request = urllib.request.Request(
            settings.resend_api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "authorization": f"Bearer {settings.resend_api_key}",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=settings.smtp_timeout_seconds) as response:
            if response.status >= 400:
                raise OSError(f"Resend API returned HTTP {response.status}")


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    settings = settings or get_settings()
    if settings.resend_api_key:
        return ResendEmailSender(settings)
    if settings.smtp_host:
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()


def send_email(
    to: str, subject: str, body: str, settings: Settings | None = None, html_body: str | None = None
) -> bool:
    """Best-effort send. Logs and swallows transport errors so the caller's
    primary action (order, reset) is never blocked by mail delivery.

    Returns True if the configured transport accepted the message, False if it
    raised. Never raises itself -- callers that only want fire-and-forget
    semantics (e.g. `BackgroundTasks.add_task(send_email, ...)`) can continue to
    ignore the return value with no change in behaviour."""
    try:
        get_email_sender(settings).send(
            OutboundEmail(to=to, subject=subject, body=body, html_body=html_body)
        )
        return True
    except (smtplib.SMTPException, OSError, ssl.SSLError, urllib.error.URLError) as exc:
        log_event("error", "email_send_failed", to=to, error_type=type(exc).__name__)
        return False

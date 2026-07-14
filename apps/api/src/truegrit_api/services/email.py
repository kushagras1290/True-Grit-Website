"""Transactional email (order notifications, password resets).

Cloudflare Workers cannot open raw SMTP sockets, so production on Workers should
use an HTTP email API; locally (uvicorn) stdlib ``smtplib`` works. This module
hides that behind a tiny ``EmailSender`` protocol: a real SMTP sender when
``smtp_host`` is configured, otherwise a console sender that logs the message —
dev-safe and keeps the flows that trigger email fully testable.

Sending is best-effort: a failure is logged, never raised into the caller, so a
mail outage can never break an order or a password reset.
"""

from __future__ import annotations

import smtplib
import ssl
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

        with smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        ) as server:
            if settings.smtp_use_tls:
                server.starttls(context=ssl.create_default_context())
            if settings.smtp_username:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(email)


def get_email_sender(settings: Settings | None = None) -> EmailSender:
    settings = settings or get_settings()
    if settings.smtp_host:
        return SmtpEmailSender(settings)
    return ConsoleEmailSender()


def send_email(to: str, subject: str, body: str, settings: Settings | None = None) -> None:
    """Best-effort send. Logs and swallows transport errors so the caller's
    primary action (order, reset) is never blocked by mail delivery."""
    try:
        get_email_sender(settings).send(OutboundEmail(to=to, subject=subject, body=body))
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        log_event("error", "email_send_failed", to=to, error_type=type(exc).__name__)

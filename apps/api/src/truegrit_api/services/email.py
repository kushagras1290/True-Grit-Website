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
from email.utils import formatdate, make_msgid, parseaddr
from typing import Protocol

from truegrit_api.config import Settings, get_settings
from truegrit_api.logging import log_event

_FALLBACK_MESSAGE_ID_DOMAIN = "truegrit.local"


def _message_id_domain(email_from: str) -> str:
    """Domain for the generated Message-ID, taken from the From address.

    `make_msgid()` otherwise uses the machine's hostname, which on a container
    or a Worker is an opaque id that matches nothing in DNS — exactly the shape
    spam filters penalise.
    """
    _, address = parseaddr(email_from)
    _, _, domain = address.partition("@")
    domain = domain.strip()
    return domain or _FALLBACK_MESSAGE_ID_DOMAIN


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
    """stdlib SMTP, covering both transport styles providers actually use.

    Port 465 is *implicit* TLS: the connection is encrypted from the first byte
    and there is no STARTTLS command. Talking plain ``SMTP`` to it — which is
    what this did — makes the server wait for a TLS handshake that never comes,
    so the send hangs until the timeout and then fails with a socket error. That
    is one of the two reasons sign-up and invitation mail silently went nowhere
    on a Gmail/SES-style configuration; the other was the missing ``Message-ID``
    and ``Date`` below, which many providers treat as a spam signal and drop.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def _build(self, message: OutboundEmail) -> EmailMessage:
        settings = self._settings
        email = EmailMessage()
        email["From"] = settings.email_from
        email["To"] = message.to
        email["Subject"] = message.subject
        # Providers score mail without a Date or Message-ID as suspicious, and
        # some reject it outright. `smtplib` adds neither.
        email["Date"] = formatdate(localtime=False)
        email["Message-ID"] = make_msgid(domain=_message_id_domain(settings.email_from))
        email.set_content(message.body)
        if message.html_body:
            email.add_alternative(message.html_body, subtype="html")
        return email

    def _connect(self) -> smtplib.SMTP:
        settings = self._settings
        if settings.smtp_implicit_tls:
            return smtplib.SMTP_SSL(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        return smtplib.SMTP(
            settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
        )

    def send(self, message: OutboundEmail) -> None:
        settings = self._settings
        email = self._build(message)
        with self._connect() as server:
            # STARTTLS upgrades a plaintext connection; on an implicit-TLS port
            # the socket is already encrypted and issuing it is an error.
            if settings.smtp_use_tls and not settings.smtp_implicit_tls:
                server.starttls(context=ssl.create_default_context())
                # RFC 3207: everything learned before the upgrade is discarded,
                # including the AUTH mechanisms this login depends on.
                server.ehlo()
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
    resolved = settings or get_settings()
    try:
        get_email_sender(resolved).send(
            OutboundEmail(to=to, subject=subject, body=body, html_body=html_body)
        )
        return True
    except (smtplib.SMTPException, OSError, ssl.SSLError, urllib.error.URLError) as exc:
        # The exception type alone ("OSError") is not enough to tell a wrong
        # password from a blocked port from an unresolvable host, which is what
        # anyone debugging "mail isn't sending" actually needs. The transport
        # and its shape go in too; credentials never do.
        log_event(
            "error",
            "email_send_failed",
            to=to,
            subject=subject,
            transport=email_transport_name(resolved),
            smtp_host=resolved.smtp_host,
            smtp_port=resolved.smtp_port,
            smtp_implicit_tls=resolved.smtp_implicit_tls,
            smtp_starttls=resolved.smtp_use_tls and not resolved.smtp_implicit_tls,
            smtp_authenticated=bool(resolved.smtp_username),
            error_type=type(exc).__name__,
            error=str(exc)[:300],
        )
        return False


def email_transport_name(settings: Settings | None = None) -> str:
    """Which sender `get_email_sender` would pick: "resend", "smtp" or "console".

    Callers that report delivery to a human need this, because the console
    sender *succeeds* without delivering anything: "invitation sent" with no
    transport configured is a message that never arrives, and the operator has
    no way to tell from the result alone.
    """
    resolved = settings or get_settings()
    if resolved.resend_api_key:
        return "resend"
    if resolved.smtp_host:
        return "smtp"
    return "console"

"""Manual smoke check for the HTML email templates.

Renders each transactional template and sends it, so the layouts can be
eyeballed in a real client. Not a pytest module despite the name (pytest only
collects `tests/`). Run it by hand:

    uv run python test_html_email.py --to someone@example.test
"""

from __future__ import annotations

import argparse
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

sys.path.insert(0, str(Path(__file__).with_name("src")))

from test_email import DEFAULT_ENV_PATH, DEFAULT_SMTP_PORT, load_env

from truegrit_api.services.email_templates import (
    render_farm_order_notification,
    render_order_confirmation,
    render_password_reset,
)

RESET_TOKEN_TTL_MINUTES = 30


def build_samples(admin_url: str) -> list[tuple[str, str, str]]:
    """(subject, plain-text fallback, rendered HTML) for each template."""
    return [
        (
            "UI Test: Password Reset",
            "Plain text fallback: reset your password.",
            render_password_reset(
                "http://localhost:5173/reset-password?token=test", RESET_TOKEN_TTL_MINUTES
            ),
        ),
        (
            "UI Test: Order Confirmation",
            "Plain text fallback: order confirmed.",
            render_order_confirmation("John Doe", "ORD-12345", "150.00 INR"),
        ),
        (
            "UI Test: Order Received (Farm Owner)",
            "Plain text fallback: order received for your farm.",
            render_farm_order_notification(
                "Jane Smith", "Green Acres Farm", "ORD-12345", admin_url
            ),
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--to", required=True, help="Recipient address")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV_PATH, help="Path to .env")
    args = parser.parse_args()

    if not args.env.exists():
        print(f"No env file at {args.env}", file=sys.stderr)
        return 1

    env = load_env(args.env)
    host = env.get("SMTP_HOST")
    user = env.get("SMTP_USERNAME")
    password = env.get("SMTP_PASSWORD")
    if not host or not user or not password:
        print(
            "SMTP_HOST, SMTP_USERNAME and SMTP_PASSWORD must all be set.",
            file=sys.stderr,
        )
        return 1

    port = int(env.get("SMTP_PORT", DEFAULT_SMTP_PORT))
    use_tls = env.get("SMTP_USE_TLS", "true").lower() == "true"
    email_from = env.get("EMAIL_FROM", user)
    admin_url = env.get("PUBLIC_ADMIN_URL", "http://localhost:5174")

    try:
        print(f"Connecting to {host}:{port}...")
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                server.starttls()
            server.login(user, password)
            for subject, fallback, html in build_samples(admin_url):
                message = EmailMessage()
                message["Subject"] = subject
                message["From"] = email_from
                message["To"] = args.to
                message.set_content(fallback)
                message.add_alternative(html, subtype="html")
                server.send_message(message)
                print(f"Sent: {subject}")
    except (smtplib.SMTPException, OSError) as error:
        print(f"Failed to send email: {error}", file=sys.stderr)
        return 1

    print(f"All test HTML emails sent successfully to {args.to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

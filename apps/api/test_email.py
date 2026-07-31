"""Manual SMTP smoke check — sends one plain-text email using the .env config.

Not a pytest module despite the name (pytest only collects `tests/`). Run it by
hand after changing SMTP settings:

    uv run python test_email.py --to someone@example.test
"""

from __future__ import annotations

import argparse
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

DEFAULT_ENV_PATH = Path(__file__).with_name(".env")
DEFAULT_SMTP_PORT = 587


def load_env(filepath: Path) -> dict[str, str]:
    """Minimal KEY=VALUE reader. Deliberately not a dotenv dependency: this
    script exists to test SMTP settings, not to replicate config loading."""
    env: dict[str, str] = {}
    with open(filepath, encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            key, separator, value = stripped.partition("=")
            if separator:
                env[key] = value
    return env


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

    message = EmailMessage()
    message.set_content(
        "This is a test email from the True Grit API to confirm SMTP settings are working."
    )
    message["Subject"] = "SMTP Test - True Grit API"
    message["From"] = env.get("EMAIL_FROM", user)
    message["To"] = args.to

    try:
        print(f"Connecting to {host}:{port}...")
        with smtplib.SMTP(host, port, timeout=30) as server:
            if use_tls:
                print("Starting TLS...")
                server.starttls()
            print("Logging in...")
            server.login(user, password)
            print("Sending email...")
            server.send_message(message)
    except (smtplib.SMTPException, OSError) as error:
        print(f"Failed to send email: {error}", file=sys.stderr)
        return 1

    print(f"Email sent successfully to {args.to}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

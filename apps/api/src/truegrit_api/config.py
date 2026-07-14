"""Validated application configuration.

Cloudflare bindings are not ordinary environment variables; they are resolved in
the platform layer. Everything here is plain configuration, validated once.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    public_storefront_url: str = "http://localhost:5173"
    public_admin_url: str = "http://localhost:5174"
    default_market: str = "IN"
    default_currency: str = "INR"
    session_cookie_name: str = "tg_session"
    session_lifetime_hours: int = 72
    preview_token_lifetime_minutes: int = 30
    admin_login_email: str = "admin@truegrit.test"
    admin_login_password: str = "admin123"

    # Session cookie cross-site policy. Use "lax" when the storefront/admin and
    # API share a registrable domain (subdomains are same-site). Use "none" when
    # they are on different domains — then the cookie must also be Secure, which
    # `cookie_secure` enforces.
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Storefront customer authentication.
    # Empty google_client_id disables federated sign-in (the API rejects Google
    # tokens); the storefront then shows the button in a "not configured" state.
    google_client_id: str = ""
    # PBKDF2-HMAC-SHA256 work factor. OWASP baseline is 600k iterations for
    # SHA-256; raise as hardware improves. Tests override this to stay fast.
    pbkdf2_iterations: int = 600_000
    # Minimum customer password length enforced at registration.
    password_min_length: int = 10

    # Authentication rate limiting (fixed window, DB-backed). Set
    # rate_limit_enabled=false only for controlled test environments.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 900
    rate_limit_login_per_account: int = 5
    rate_limit_login_per_ip: int = 20
    rate_limit_register_per_ip: int = 10
    rate_limit_register_window_seconds: int = 3600
    rate_limit_google_per_ip: int = 30

    # Global per-IP request ceiling applied to every route by middleware.
    # In-memory on purpose: a flood must not amplify into database load. On
    # multi-isolate Workers each isolate keeps its own counter (higher effective
    # ceiling); front it with Cloudflare's edge rate limiting for a hard cap.
    rate_limit_global_per_ip: int = 300
    rate_limit_global_window_seconds: int = 60

    # Transactional email (order notifications, password resets). Empty smtp_host
    # falls back to a console sender that logs the message — safe for local dev
    # and keeps email-triggering flows testable without a real mail server.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_timeout_seconds: int = 10
    email_from: str = "True Grit <no-reply@truegrit.test>"
    contact_recipient_email: str = ""

    # Password reset token lifetime.
    password_reset_lifetime_minutes: int = 30

    # Payments. Cash-on-delivery is always available; each online gateway turns
    # on only when its keys are present. Secrets come from env vars / Worker
    # secrets (`wrangler secret put`) and are never committed. Use test-mode keys
    # until go-live. Amounts are charged in `payment_currency` minor units.
    payment_currency: str = "INR"
    payment_cod_enabled: bool = True
    # Razorpay (UPI, cards, netbanking, wallets — primary for India).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # Stripe (cards, global).
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # PayPal (PayPal balance + cards, global).
    paypal_client_id: str = ""
    paypal_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_environment: Literal["sandbox", "live"] = "sandbox"

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def stripe_enabled(self) -> bool:
        return bool(self.stripe_secret_key)

    @property
    def paypal_enabled(self) -> bool:
        return bool(self.paypal_client_id and self.paypal_secret)

    @property
    def enabled_payment_methods(self) -> list[str]:
        methods: list[str] = []
        if self.payment_cod_enabled:
            methods.append("cod")
        if self.razorpay_enabled:
            methods.append("razorpay")
        if self.stripe_enabled:
            methods.append("stripe")
        if self.paypal_enabled:
            methods.append("paypal")
        return methods

    @property
    def allowed_origins(self) -> list[str]:
        # Accept the sibling loopback host (localhost <-> 127.0.0.1) so a browser
        # hitting one while the app is configured for the other does not trip
        # CORS in local development. Real domains are unaffected.
        origins: list[str] = []
        for url in (self.public_storefront_url, self.public_admin_url):
            origins.append(url)
            if "127.0.0.1" in url:
                origins.append(url.replace("127.0.0.1", "localhost"))
            elif "localhost" in url:
                origins.append(url.replace("localhost", "127.0.0.1"))
        return list(dict.fromkeys(origins))

    @property
    def google_sign_in_enabled(self) -> bool:
        return bool(self.google_client_id)

    @property
    def cookie_secure(self) -> bool:
        # SameSite=None cookies are rejected by browsers unless Secure is set.
        return self.session_cookie_samesite == "none" or self.app_env in {"staging", "production"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

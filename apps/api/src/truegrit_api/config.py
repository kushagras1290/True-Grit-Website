"""Validated application configuration.

Cloudflare bindings are not ordinary environment variables; they are resolved in
the platform layer. Everything here is plain configuration, validated once.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Standard implicit-TLS ("SMTPS") port. 587 and 25 are the STARTTLS ports.
SMTPS_PORT = 465


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="", extra="ignore")

    app_env: Literal["development", "test", "staging", "production"] = "development"
    public_storefront_url: str = "http://localhost:5173"
    public_admin_url: str = "http://localhost:5174"
    public_process_url: str = "http://localhost:5175"
    default_market: str = "IN"
    default_currency: str = "INR"
    session_cookie_name: str = "tg_session"
    session_lifetime_hours: int = 72
    preview_token_lifetime_minutes: int = 30
    admin_login_email: str = "admin@truegrit.test"
    admin_login_password: str = "admin123"

    # Release cockpit. GITHUB_TOKEN is a server-side secret with repository
    # Contents (read/write), Commit statuses (read/write), and Actions (read).
    github_repository: str = "kushagras1290/True-Grit-Website"
    github_token: str = ""
    github_api_version: str = "2026-03-10"
    deployment_testing_url: str = ""
    deployment_staging_url: str = "https://truegrit-storefront-staging.kushagras1234890.workers.dev"
    deployment_main_url: str = "https://truegritin.com"

    # Session cookie cross-site policy. Use "lax" when the storefront/admin and
    # API share a registrable domain (subdomains are same-site). Use "none" when
    # they are on different domains — then the cookie must also be Secure, which
    # `cookie_secure` enforces.
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"

    # Storefront customer authentication.
    # Empty provider ids/secrets disable federated sign-in; the storefront then
    # shows those buttons in a "not configured" state.
    google_client_id: str = ""
    facebook_app_id: str = ""
    facebook_app_secret: str = ""
    # PBKDF2-HMAC-SHA256 work factor. Python Workers need a conservative budget
    # or password verification can hit CPU limits before CORS headers are sent.
    pbkdf2_iterations: int = 50_000
    pbkdf2_verify_max_iterations: int = 50_000
    # Minimum customer password length enforced at registration.
    password_min_length: int = 10

    @property
    def pbkdf2_write_iterations(self) -> int:
        """Never create a password hash that this runtime refuses to verify.

        The verification ceiling protects the Worker from an unexpectedly
        expensive stored hash. A stale, higher PBKDF2_ITERATIONS environment
        value must therefore be capped for new writes, not produce accounts
        that fail their very first login.
        """
        return min(self.pbkdf2_iterations, self.pbkdf2_verify_max_iterations)

    # Authentication rate limiting (fixed window, DB-backed). Set
    # rate_limit_enabled=false only for controlled test environments.
    rate_limit_enabled: bool = True
    rate_limit_window_seconds: int = 900
    rate_limit_login_per_account: int = 5
    rate_limit_login_per_ip: int = 20
    rate_limit_register_per_ip: int = 10
    rate_limit_register_window_seconds: int = 3600
    rate_limit_google_per_ip: int = 30
    rate_limit_facebook_per_ip: int = 30

    # Global per-IP request ceiling applied to every route by middleware.
    # In-memory on purpose: a flood must not amplify into database load. On
    # multi-isolate Workers each isolate keeps its own counter (higher effective
    # ceiling); front it with Cloudflare's edge rate limiting for a hard cap.
    rate_limit_global_per_ip: int = 300
    rate_limit_global_window_seconds: int = 60

    # Transactional email (order notifications, password resets). Empty smtp_host
    # falls back to a console sender that logs the message — safe for local dev
    # and keeps email-triggering flows testable without a real mail server.
    resend_api_key: str = ""
    resend_api_url: str = "https://api.resend.com/emails"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    # STARTTLS: connect in plaintext on 587/25, then upgrade. Leave on unless
    # the server genuinely has no TLS (a local mail catcher).
    smtp_use_tls: bool = True
    # Implicit TLS ("SMTPS"): the socket is encrypted from the first byte and
    # STARTTLS must NOT be sent. This is what port 465 means. Left unset it is
    # inferred from the port, because getting it wrong is silent — a plaintext
    # client on 465 simply waits for a handshake that never arrives and dies at
    # the timeout, which is how invitation mail can appear to "just not send".
    smtp_implicit_tls_override: bool | None = None
    smtp_timeout_seconds: int = 10
    email_from: str = "True Grit <no-reply@truegrit.test>"
    contact_recipient_email: str = ""

    # Password reset token lifetime.
    password_reset_lifetime_minutes: int = 30

    # Mobile number verification (one-time passcodes over SMS).
    #
    # Delivery: empty fast2sms_api_key falls back to a console sender that logs
    # the passcode — dev-safe, and `services.sms.get_sms_sender` refuses that
    # fallback in staging/production so live OTPs can never reach a log. Fast2SMS
    # is used on its `route=otp`, which rides the provider's own approved DLT
    # header, so no TRAI DLT registration is needed to go live. The key is a
    # secret: supply it via `wrangler secret put FAST2SMS_API_KEY`, never in
    # source or wrangler.jsonc.
    fast2sms_api_key: str = ""
    # 6 digits is the Indian norm and what customers expect to type. Shorter is
    # materially weaker: with otp_max_attempts=5, a 4-digit code gives an
    # attacker a 1-in-2000 shot per challenge, a 6-digit code 1-in-200,000.
    otp_length: int = 6
    otp_lifetime_seconds: int = 300
    # Guesses allowed against a single challenge before it is burned.
    otp_max_attempts: int = 5
    # Resends allowed on one challenge before a fresh one must be requested.
    # Each resend is a real SMS with a real cost, hence the tight cap.
    otp_max_resends: int = 3
    # Seconds a customer must wait between resend requests.
    otp_resend_cooldown_seconds: int = 30
    # Issuance ceilings. Per-phone stops one number being used to burn credit or
    # to harass its owner; per-IP stops one host enumerating many numbers.
    rate_limit_otp_per_phone: int = 5
    rate_limit_otp_per_ip: int = 20
    rate_limit_otp_window_seconds: int = 3600
    # Require a verified mobile before a new account is considered complete.
    # Existing accounts are prompted but may skip — see `phone_required_at_checkout`.
    phone_required_at_registration: bool = True
    # Gate checkout on a verified mobile. Delivery and COD both depend on being
    # able to reach the customer, so this is where an unverified legacy account
    # is finally asked to verify.
    phone_required_at_checkout: bool = True

    # Payments. Cash-on-delivery is always available; each online gateway turns
    # on only when its keys are present. Secrets come from env vars / Worker
    # secrets (`wrangler secret put`) and are never committed. Use test-mode keys
    # until go-live. Amounts are charged in `payment_currency` minor units.
    payment_currency: str = "INR"
    payment_cod_enabled: bool = True
    # Cash-on-delivery ceiling (minor units). Orders above this must pay online.
    # Default 39900 = ₹399. (Customers may also hold only one unpaid COD order at
    # a time — enforced in services.checkout.)
    payment_cod_max_minor: int = 39900
    # Razorpay (UPI, cards, netbanking, wallets — primary for India).
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""
    # Stripe (cards, global).
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    stripe_webhook_secret: str = ""
    # PayPal — cross-border only.
    #
    # PayPal closed its domestic India business on 1 April 2021: an Indian
    # merchant can no longer take an INR payment from an Indian customer. What
    # still works is the reverse direction — someone abroad paying an Indian
    # merchant in a foreign currency — which is exactly the NRI-gifting case
    # (pay from the US, deliver to family in Mumbai). PayPal is therefore offered
    # only as an international option; domestic customers use Razorpay or COD.
    paypal_client_id: str = ""
    paypal_secret: str = ""
    paypal_webhook_id: str = ""
    paypal_environment: Literal["sandbox", "live"] = "sandbox"
    # What an overseas buyer is charged in. Cannot be INR: PayPal will not settle
    # a domestic INR payment to an Indian merchant.
    paypal_currency: str = "USD"
    # How many rupees one unit of `paypal_currency` is worth (e.g. 88.5 INR per
    # USD). Orders are priced in INR, so a cross-border charge has to be
    # converted, and there is no way to do that without a rate.
    #
    # Deliberately a fixed, operator-set number rather than a live FX lookup: an
    # exchange-rate API is another dependency, another key and another outage on
    # the checkout path, and a rate that silently moves makes order totals
    # unreproducible. Set it slightly in the store's favour to absorb drift, and
    # review it when the rate moves. Zero disables PayPal — see
    # `paypal_configured`, which refuses to offer a gateway it cannot price.
    paypal_inr_per_unit: float = 0.0

    # Explicit go-live switches for the gateways that are still scaffolding.
    #
    # Keys alone must NOT put a gateway in front of customers. Only Razorpay has
    # a real checkout implementation (`services.payments`); PayPal and Stripe are
    # configuration with no order-creation or verification behind them. Without
    # these flags, merely pasting a key into `.env` would advertise the method on
    # `/payment-methods`, let checkout accept it, and strand the customer with an
    # order stuck in `pending_payment` that they have no way to pay — cart
    # cleared, money never taken.
    #
    # Same shape as the storefront's `PUBLIC_FACEBOOK_LOGIN_VISIBLE`: configure
    # first, reveal deliberately. Flip these on only once the gateway's checkout
    # flow actually exists and has been tested end to end.
    payment_paypal_visible: bool = False
    payment_stripe_visible: bool = False

    @property
    def smtp_implicit_tls(self) -> bool:
        """Whether to open the SMTP socket already wrapped in TLS.

        Defaults to "port 465 means SMTPS", which is true of every mainstream
        provider, and stays overridable for the rare server on a non-standard
        port. `SMTP_IMPLICIT_TLS_OVERRIDE=true|false` wins when set.
        """
        if self.smtp_implicit_tls_override is not None:
            return self.smtp_implicit_tls_override
        return self.smtp_port == SMTPS_PORT

    @property
    def email_configured(self) -> bool:
        """True when a real transport is available. False means the console
        sender, which logs the message instead of delivering it."""
        return bool(self.resend_api_key or self.smtp_host)

    @property
    def fast2sms_enabled(self) -> bool:
        return bool(self.fast2sms_api_key)

    @property
    def sms_enabled(self) -> bool:
        """True when a passcode can actually reach a handset. Outside production
        the console sender stands in, so phone verification stays exercisable
        with no provider account."""
        return self.fast2sms_enabled or self.app_env not in {"staging", "production"}

    @property
    def razorpay_enabled(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def stripe_configured(self) -> bool:
        """Keys are present. Not the same as being offered to customers."""
        return bool(self.stripe_secret_key)

    @property
    def stripe_enabled(self) -> bool:
        return self.stripe_configured and self.payment_stripe_visible

    @property
    def paypal_configured(self) -> bool:
        """Keys are present and the cross-border charge can actually be priced.

        A missing rate counts as unconfigured rather than defaulting to
        something: guessing an exchange rate would silently mischarge every
        overseas customer.
        """
        return bool(
            self.paypal_client_id
            and self.paypal_secret
            and self.paypal_inr_per_unit > 0
            and self.paypal_currency.upper() != "INR"
        )

    @property
    def paypal_enabled(self) -> bool:
        return self.paypal_configured and self.payment_paypal_visible

    @property
    def paypal_api_base(self) -> str:
        if self.paypal_environment == "live":
            return "https://api-m.paypal.com"
        return "https://api-m.sandbox.paypal.com"

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
        for url in (self.public_storefront_url, self.public_admin_url, self.public_process_url):
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
    def facebook_sign_in_enabled(self) -> bool:
        return bool(self.facebook_app_id and self.facebook_app_secret)

    @property
    def cookie_secure(self) -> bool:
        # SameSite=None cookies are rejected by browsers unless Secure is set.
        return self.session_cookie_samesite == "none" or self.app_env in {"staging", "production"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

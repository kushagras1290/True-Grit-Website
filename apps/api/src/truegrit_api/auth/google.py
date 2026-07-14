"""Verify "Sign in with Google" ID tokens (Google Identity Services).

The storefront uses Google Identity Services: the browser obtains a signed JWT
(an OpenID Connect ID token) and posts it here. We verify it fully server-side
per Google's guidance — signature against Google's published keys, then the
`iss`, `aud`, and `exp` claims:
https://developers.google.com/identity/gsi/web/guides/verify-google-id-token

Signature verification is RSASSA-PKCS1-v1.5 with SHA-256 (RS256). It is done in
pure Python (`pow` over the JWK modulus) so the API needs no native crypto
dependency in the Cloudflare Workers runtime. JWKS are cached with a TTL to
avoid a network round-trip on every sign-in.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from truegrit_api.errors import AuthenticationError
from truegrit_api.platform.http import HttpError, get_json

GOOGLE_JWKS_URI = "https://www.googleapis.com/oauth2/v3/certs"
GOOGLE_ISSUERS = frozenset({"accounts.google.com", "https://accounts.google.com"})

# DER prefix for DigestInfo(SHA-256) in EMSA-PKCS1-v1_5 (RFC 8017, §9.2).
_SHA256_DIGEST_INFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")
_JWKS_CACHE_TTL_SECONDS = 3600
_CLOCK_SKEW_SECONDS = 60

JwksFetcher = Callable[[], Any]


class GoogleAuthError(AuthenticationError):
    """A Google ID token is missing, malformed, or fails verification."""


@dataclass(frozen=True)
class GoogleIdentity:
    subject: str
    email: str
    email_verified: bool
    name: str


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _b64url_to_int(value: str) -> int:
    return int.from_bytes(_b64url_decode(value), "big")


def _rsa_pkcs1_v15_sha256_verify(signing_input: bytes, signature: bytes, n: int, e: int) -> bool:
    """RSASSA-PKCS1-v1.5 verify for SHA-256, comparing the reconstructed
    encoded message in constant time."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    signature_int = int.from_bytes(signature, "big")
    if signature_int >= n:
        return False
    encoded_message = pow(signature_int, e, n).to_bytes(k, "big")
    digest_info = _SHA256_DIGEST_INFO_PREFIX + hashlib.sha256(signing_input).digest()
    padding_length = k - len(digest_info) - 3
    if padding_length < 8:
        return False
    expected = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + digest_info
    return hmac.compare_digest(encoded_message, expected)


class GoogleTokenVerifier:
    """Verifies Google ID tokens against a cached, refreshable JWKS."""

    def __init__(
        self,
        *,
        jwks_fetcher: JwksFetcher | None = None,
        clock: Callable[[], float] = time.time,
        cache_ttl_seconds: int = _JWKS_CACHE_TTL_SECONDS,
    ) -> None:
        self._fetch = jwks_fetcher or (lambda: get_json(GOOGLE_JWKS_URI))
        self._clock = clock
        self._cache_ttl = cache_ttl_seconds
        self._lock = threading.Lock()
        self._keys: dict[str, tuple[int, int]] = {}
        self._fetched_at = 0.0

    def _load_keys(self, *, force: bool) -> dict[str, tuple[int, int]]:
        with self._lock:
            fresh = self._clock() - self._fetched_at < self._cache_ttl
            if self._keys and fresh and not force:
                return self._keys
            try:
                document = self._fetch()
            except HttpError as exc:
                if self._keys and not force:
                    return self._keys  # serve stale keys rather than fail sign-in
                raise GoogleAuthError("Could not reach Google to verify sign-in.") from exc
            keys: dict[str, tuple[int, int]] = {}
            for jwk in (document or {}).get("keys", []):
                if jwk.get("kty") != "RSA" or jwk.get("alg") not in (None, "RS256"):
                    continue
                kid, modulus, exponent = jwk.get("kid"), jwk.get("n"), jwk.get("e")
                if not (kid and modulus and exponent):
                    continue
                keys[kid] = (_b64url_to_int(modulus), _b64url_to_int(exponent))
            if not keys:
                raise GoogleAuthError("Google returned no usable signing keys.")
            self._keys = keys
            self._fetched_at = self._clock()
            return self._keys

    def _key_for(self, kid: str) -> tuple[int, int]:
        keys = self._load_keys(force=False)
        if kid not in keys:
            keys = self._load_keys(force=True)  # key rotation: refresh once
        key = keys.get(kid)
        if key is None:
            raise GoogleAuthError("Sign-in token was signed with an unknown key.")
        return key

    def verify(self, credential: str, *, client_id: str) -> GoogleIdentity:
        if not client_id:
            raise GoogleAuthError("Google sign-in is not configured.")
        if not credential or credential.count(".") != 2:
            raise GoogleAuthError("Malformed Google sign-in token.")

        header_b64, payload_b64, signature_b64 = credential.split(".")
        try:
            header = json.loads(_b64url_decode(header_b64))
        except (ValueError, json.JSONDecodeError) as exc:
            raise GoogleAuthError("Malformed Google sign-in token.") from exc
        if header.get("alg") != "RS256":
            raise GoogleAuthError("Unsupported Google sign-in token algorithm.")
        kid = header.get("kid")
        if not kid:
            raise GoogleAuthError("Google sign-in token is missing its key id.")

        modulus, exponent = self._key_for(kid)
        signing_input = f"{header_b64}.{payload_b64}".encode("ascii")
        try:
            signature = _b64url_decode(signature_b64)
        except ValueError as exc:
            raise GoogleAuthError("Malformed Google sign-in token.") from exc
        if not _rsa_pkcs1_v15_sha256_verify(signing_input, signature, modulus, exponent):
            raise GoogleAuthError("Google sign-in token signature is invalid.")

        try:
            claims = json.loads(_b64url_decode(payload_b64))
        except (ValueError, json.JSONDecodeError) as exc:
            raise GoogleAuthError("Malformed Google sign-in token.") from exc
        return self._validate_claims(claims, client_id=client_id)

    def _validate_claims(self, claims: dict[str, Any], *, client_id: str) -> GoogleIdentity:
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise GoogleAuthError("Google sign-in token has an unexpected issuer.")
        if claims.get("aud") != client_id:
            raise GoogleAuthError("Google sign-in token was issued for another app.")
        now = self._clock()
        exp = claims.get("exp")
        if not isinstance(exp, (int, float)) or now - _CLOCK_SKEW_SECONDS > exp:
            raise GoogleAuthError("Google sign-in token has expired.")
        iat = claims.get("iat")
        if isinstance(iat, (int, float)) and iat - _CLOCK_SKEW_SECONDS > now:
            raise GoogleAuthError("Google sign-in token is not yet valid.")
        subject = claims.get("sub")
        email = claims.get("email")
        if not subject or not email:
            raise GoogleAuthError("Google sign-in token is missing account details.")
        email_verified = claims.get("email_verified") in (True, "true")
        if not email_verified:
            raise GoogleAuthError("Your Google email address is not verified.")
        name = claims.get("name") or claims.get("given_name") or str(email).split("@", 1)[0]
        return GoogleIdentity(
            subject=str(subject),
            email=str(email),
            email_verified=email_verified,
            name=str(name),
        )


_default_verifier = GoogleTokenVerifier()


def verify_google_id_token(credential: str, *, client_id: str) -> GoogleIdentity:
    """Verify a Google ID token using the shared, cached verifier."""
    return _default_verifier.verify(credential, client_id=client_id)

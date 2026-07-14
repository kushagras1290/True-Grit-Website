"""Password hashing for customer accounts.

PBKDF2-HMAC-SHA256 via the standard library. Chosen over bcrypt/argon2 because
the API targets Cloudflare Python Workers, where only pure-Python / stdlib
crypto is dependable — `hashlib.pbkdf2_hmac` is available in both CPython and
the Workers (Pyodide) runtime.

Stored format (PHC-like, self-describing so the work factor can rise over time):

    pbkdf2_sha256$<iterations>$<salt_b64>$<hash_b64>
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from truegrit_api.errors import ValidationAppError

_ALGORITHM = "pbkdf2_sha256"
_SALT_BYTES = 16
_DERIVED_KEY_BYTES = 32


class PasswordError(ValidationAppError):
    """A password value is unusable (empty, malformed stored hash)."""


def _b64encode(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.b64decode(value.encode("ascii"))


def hash_password(password: str, *, iterations: int) -> str:
    """Derive a self-describing PBKDF2 hash with a fresh random salt."""
    if not password:
        raise PasswordError("Password must not be empty.")
    if iterations < 1:
        raise PasswordError("Password hashing work factor must be positive.")
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=_DERIVED_KEY_BYTES
    )
    return f"{_ALGORITHM}${iterations}${_b64encode(salt)}${_b64encode(derived)}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time verification of `password` against a stored hash.

    Returns False for any malformed stored value rather than raising, so a
    corrupt row can never authenticate and never leaks its shape to callers.
    """
    try:
        algorithm, iterations_raw, salt_b64, hash_b64 = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    if iterations < 1 or not salt or not expected:
        return False
    candidate = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iterations, dklen=len(expected)
    )
    return hmac.compare_digest(candidate, expected)

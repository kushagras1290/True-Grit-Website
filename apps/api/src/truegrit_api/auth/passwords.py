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


def password_hash_iterations(encoded: str | None) -> int | None:
    if not encoded:
        return None
    try:
        algorithm, iterations_raw, _salt_b64, _hash_b64 = encoded.split("$")
        if algorithm != _ALGORITHM:
            return None
        return int(iterations_raw)
    except (ValueError, TypeError):
        return None


def verify_password(password: str, encoded: str, *, max_iterations: int | None = None) -> bool:
    """Constant-time verification of `password` against a stored hash.

    Returns False for any malformed stored value rather than raising, so a
    corrupt row can never authenticate and never leaks its shape to callers.
    """
    try:
        algorithm, iterations_raw, salt_b64, hash_b64 = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        if max_iterations is not None and iterations > max_iterations:
            return False
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


async def verify_password_async(
    password: str, encoded: str, *, max_iterations: int | None = None
) -> bool:
    """Verify with native Web Crypto in Workers and stdlib PBKDF2 elsewhere.

    Pyodide's ``hashlib.pbkdf2_hmac`` consumes the Free-plan CPU allowance for
    established 50k-round hashes. Browser/Worker Web Crypto performs the same
    PBKDF2-HMAC-SHA256 operation natively, outside the Python interpreter.
    """
    try:
        algorithm, iterations_raw, salt_b64, hash_b64 = encoded.split("$")
        if algorithm != _ALGORITHM:
            return False
        iterations = int(iterations_raw)
        if max_iterations is not None and iterations > max_iterations:
            return False
        salt = _b64decode(salt_b64)
        expected = _b64decode(hash_b64)
    except (ValueError, TypeError):
        return False
    if iterations < 1 or not salt or not expected:
        return False

    try:
        from js import Uint8Array, crypto
        from pyodide.ffi import to_js
    except ModuleNotFoundError:
        return verify_password(password, encoded, max_iterations=max_iterations)

    password_bytes = Uint8Array.new(to_js(list(password.encode("utf-8"))))
    salt_bytes = Uint8Array.new(to_js(list(salt)))
    key = await crypto.subtle.importKey(
        "raw", password_bytes, to_js({"name": "PBKDF2"}), False, to_js(["deriveBits"])
    )
    derived = await crypto.subtle.deriveBits(
        to_js(
            {
                "name": "PBKDF2",
                "salt": salt_bytes,
                "iterations": iterations,
                "hash": "SHA-256",
            }
        ),
        key,
        len(expected) * 8,
    )
    candidate = bytes(Uint8Array.new(derived).to_py())
    return hmac.compare_digest(candidate, expected)

"""Unit tests for PBKDF2 password hashing."""

from __future__ import annotations

import pytest

from truegrit_api.auth.passwords import (
    PasswordError,
    hash_password,
    password_hash_iterations,
    verify_password,
)

FAST_ITERATIONS = 1000


def test_hash_roundtrip_verifies():
    encoded = hash_password("correct horse battery", iterations=FAST_ITERATIONS)
    assert encoded.startswith("pbkdf2_sha256$1000$")
    assert password_hash_iterations(encoded) == FAST_ITERATIONS
    assert verify_password("correct horse battery", encoded) is True


def test_over_budget_hash_is_not_verified():
    encoded = hash_password("correct horse battery", iterations=FAST_ITERATIONS + 1)
    assert verify_password(
        "correct horse battery", encoded, max_iterations=FAST_ITERATIONS
    ) is False


def test_wrong_password_rejected():
    encoded = hash_password("s3cret-value", iterations=FAST_ITERATIONS)
    assert verify_password("s3cret-valuE", encoded) is False
    assert verify_password("", encoded) is False


def test_hashes_are_salted_and_unique():
    first = hash_password("same-input", iterations=FAST_ITERATIONS)
    second = hash_password("same-input", iterations=FAST_ITERATIONS)
    assert first != second
    assert verify_password("same-input", first)
    assert verify_password("same-input", second)


def test_empty_password_is_rejected():
    with pytest.raises(PasswordError):
        hash_password("", iterations=FAST_ITERATIONS)


@pytest.mark.parametrize(
    "corrupt",
    ["", "not-a-hash", "pbkdf2_sha256$abc$salt$hash", "sha1$1000$aa$bb", "pbkdf2_sha256$1000$$"],
)
def test_malformed_stored_hash_never_verifies(corrupt: str):
    assert verify_password("anything", corrupt) is False

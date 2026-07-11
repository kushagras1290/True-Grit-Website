"""Application-generated, time-sortable identifiers (ULID-style, prefixed)."""

from __future__ import annotations

import secrets
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, length: int) -> str:
    chars = []
    for _ in range(length):
        chars.append(_CROCKFORD[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def new_id(prefix: str) -> str:
    """`prefix_` + 10-char timestamp + 16-char randomness (lowercased ULID flavour)."""
    timestamp_ms = int(time.time() * 1000)
    random_bits = secrets.randbits(80)
    body = _encode_base32(timestamp_ms, 10) + _encode_base32(random_bits, 16)
    return f"{prefix}_{body.lower()}"


def new_request_id() -> str:
    return new_id("req")

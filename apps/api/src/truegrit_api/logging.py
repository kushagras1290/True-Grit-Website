"""Structured JSON logging.

Never log passwords, OTPs, session tokens, CSRF tokens, authorization headers,
payment payloads, or unredacted personal data.
"""

from __future__ import annotations

import json
import sys
import time
from typing import Any

_REDACTED_KEYS = frozenset(
    {"password", "otp", "token", "session", "authorization", "cookie", "secret", "card"}
)


def log_event(level: str, event: str, /, **fields: Any) -> None:
    safe_fields = {
        key: ("[redacted]" if any(marker in key.lower() for marker in _REDACTED_KEYS) else value)
        for key, value in fields.items()
    }
    record = {"level": level, "event": event, "ts": time.time(), **safe_fields}
    sys.stdout.write(json.dumps(record, default=str) + "\n")

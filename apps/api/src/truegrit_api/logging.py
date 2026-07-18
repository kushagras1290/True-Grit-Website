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


def redact_fields(fields: dict[str, Any]) -> dict[str, Any]:
    """Mask any field whose key implies sensitive content. Shared by `log_event`
    and `services.log_persistence.persist_log` so stdout logs and the persisted
    `application_logs` copy can never diverge on what counts as safe to keep."""
    return {
        key: ("[redacted]" if any(marker in key.lower() for marker in _REDACTED_KEYS) else value)
        for key, value in fields.items()
    }


def log_event(level: str, event: str, /, **fields: Any) -> None:
    record = {"level": level, "event": event, "ts": time.time(), **redact_fields(fields)}
    sys.stdout.write(json.dumps(record, default=str) + "\n")

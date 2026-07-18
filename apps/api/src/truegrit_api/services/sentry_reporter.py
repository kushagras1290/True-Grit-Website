"""Minimal, dependency-free Sentry error reporting.

Cloudflare Python Workers run on Pyodide: a single-threaded WebAssembly build of
CPython with no real OS threads, no `signal` delivery, and no background worker
execution. The official `sentry-sdk` package assumes exactly those things are
available — it spawns a background thread to flush its transport queue and
installs signal handlers for graceful shutdown — so it cannot run in this
runtime. This is a Python Workers (Pyodide) limitation specifically: Cloudflare
and Sentry do have an official integration for *JavaScript* Workers
(`@sentry/cloudflare`), but nothing analogous exists for Python Workers.

Rather than force in a package that will not run, this module POSTs directly to
Sentry's documented, SDK-free ingestion protocol: a single "envelope" containing
one error event, sent to `{host}{path}/api/{project_id}/envelope/` with an
`X-Sentry-Auth` header carrying the DSN's public key. See:
  https://develop.sentry.dev/sdk/foundations/transport/envelopes/
  https://develop.sentry.dev/sdk/foundations/transport/authentication/
  https://develop.sentry.dev/sdk/data-model/event-payloads/
The older, simpler `/api/{project_id}/store/` endpoint was deliberately not
used — Sentry's own developer docs mark it deprecated in favor of the envelope
endpoint for anything but a legacy transport.

A no-op when `settings.sentry_dsn` is empty (the default): no DSN parsing and no
network call, identical behavior to today, exactly like this codebase's
`fast2sms_api_key`/`resend_api_key` "empty means not configured" convention.
Reporting failures are swallowed and logged, never raised — this runs from
inside exception handlers, so a broken or misconfigured Sentry integration must
never itself turn a request into a second, worse failure.

Never logs `settings.sentry_dsn` itself: a DSN's public key is safe to expose,
but a legacy DSN may still carry a secret key component, and the type/module of
a reporting failure is all `error_handler.py` ever needs to diagnose it.
"""

from __future__ import annotations

import json
import traceback
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from truegrit_api.config import Settings, get_settings
from truegrit_api.logging import log_event
from truegrit_api.platform.http import post_raw_async

_ENVELOPE_CONTENT_TYPE = "application/x-sentry-envelope"
_SENTRY_PROTOCOL_VERSION = 7
_SDK_NAME = "truegrit-api-minimal-http"
_SDK_VERSION = "1.0.0"
# Caps how much of the exception message and stack we ship. An exception
# message can embed arbitrary (even attacker-influenced) data, and a deeply
# recursive traceback can have thousands of frames; neither should be able to
# build an unbounded outbound payload.
_MAX_MESSAGE_CHARS = 2000
_MAX_STACK_FRAMES = 50


class SentryDsnError(Exception):
    """`sentry_dsn` is set but is not a well-formed Sentry DSN."""


@dataclass(frozen=True)
class _ParsedDsn:
    """The pieces of a Sentry DSN needed to POST an envelope.

    DSN shape: `{scheme}://{public_key}[:{secret_key}]@{host}[:{port}]{path}/{project_id}`.
    `path` is an optional prefix used by self-hosted/proxied Sentry instances
    mounted under a sub-path; it is empty for the sentry.io SaaS.
    """

    envelope_url: str
    public_key: str
    secret_key: str | None


def _parse_dsn(dsn: str) -> _ParsedDsn:
    parts = urlsplit(dsn)
    if not parts.scheme or not parts.hostname or not parts.username:
        raise SentryDsnError("SENTRY_DSN is not a well-formed Sentry DSN.")
    prefix, _, project_id = parts.path.rpartition("/")
    if not project_id:
        raise SentryDsnError("SENTRY_DSN is missing its project id.")
    netloc = parts.hostname if parts.port is None else f"{parts.hostname}:{parts.port}"
    envelope_url = f"{parts.scheme}://{netloc}{prefix}/api/{project_id}/envelope/"
    return _ParsedDsn(
        envelope_url=envelope_url, public_key=parts.username, secret_key=parts.password
    )


def _auth_header(parsed: _ParsedDsn) -> str:
    fields = [
        f"sentry_version={_SENTRY_PROTOCOL_VERSION}",
        f"sentry_client={_SDK_NAME}/{_SDK_VERSION}",
        f"sentry_key={parsed.public_key}",
    ]
    if parsed.secret_key:
        # Legacy DSN shape only — Sentry stopped issuing secret keys in 2019,
        # but an old self-hosted DSN could still carry one.
        fields.append(f"sentry_secret={parsed.secret_key}")
    return "Sentry " + ", ".join(fields)


def _stack_frames(exc: BaseException) -> list[dict[str, Any]]:
    frames = traceback.extract_tb(exc.__traceback__)[-_MAX_STACK_FRAMES:]
    return [
        {
            "filename": frame.filename,
            "function": frame.name or "<unknown>",
            "lineno": frame.lineno,
            "in_app": "truegrit_api" in frame.filename,
        }
        for frame in frames
    ]


def _build_envelope(
    *, event_id: str, dsn: str, settings: Settings, exc: BaseException, extra: dict[str, Any]
) -> str:
    sent_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    envelope_header = {"event_id": event_id, "sent_at": sent_at, "dsn": dsn}
    event: dict[str, Any] = {
        "event_id": event_id,
        "timestamp": sent_at,
        "platform": "python",
        "level": "error",
        "environment": settings.app_env,
        "logger": "truegrit_api",
        "exception": {
            "values": [
                {
                    "type": type(exc).__name__,
                    "value": str(exc)[:_MAX_MESSAGE_CHARS],
                    "module": type(exc).__module__,
                    "stacktrace": {"frames": _stack_frames(exc)},
                }
            ]
        },
    }
    if extra:
        event["extra"] = {key: str(value) for key, value in extra.items()}
        request_id = extra.get("request_id")
        if request_id:
            event["tags"] = {"request_id": str(request_id)}
    item_body = json.dumps(event, default=str)
    item_header = {
        "type": "event",
        "length": len(item_body.encode("utf-8")),
        "content_type": "application/json",
    }
    return "\n".join([json.dumps(envelope_header), json.dumps(item_header), item_body]) + "\n"


async def report_exception_async(
    exc: BaseException, *, settings: Settings | None = None, **extra: Any
) -> None:
    """Best-effort: report `exc` to Sentry if `SENTRY_DSN` is configured.

    Never raises. Every failure mode — no DSN configured, a malformed DSN, a
    network error, a non-2xx response from Sentry — is caught here and logged
    as `sentry_report_failed` (error type only, per this module's docstring)
    rather than propagated.
    """
    settings = settings or get_settings()
    if not settings.sentry_dsn:
        return
    try:
        parsed = _parse_dsn(settings.sentry_dsn)
        envelope = _build_envelope(
            event_id=uuid.uuid4().hex,
            dsn=settings.sentry_dsn,
            settings=settings,
            exc=exc,
            extra=extra,
        )
        await post_raw_async(
            parsed.envelope_url,
            body=envelope,
            content_type=_ENVELOPE_CONTENT_TYPE,
            headers={"X-Sentry-Auth": _auth_header(parsed)},
        )
    except Exception as report_exc:
        log_event("error", "sentry_report_failed", error_type=type(report_exc).__name__)

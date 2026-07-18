"""Unit tests for the minimal, dependency-free Sentry error reporter.

The rule worth guarding here: an unconfigured or misbehaving Sentry integration
must never make a network call (when unconfigured) and must never raise (when
misbehaving) — a reporting failure must never become a second, worse failure on
top of the exception it was trying to report.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from truegrit_api.config import Settings
from truegrit_api.services.sentry_reporter import (
    SentryDsnError,
    _auth_header,
    _parse_dsn,
    report_exception_async,
)


def settings_for(dsn: str = "", app_env: str = "production") -> Settings:
    return Settings(app_env=app_env, sentry_dsn=dsn)


def test_report_is_a_no_op_when_dsn_is_unset(monkeypatch):
    """No DSN configured -> no network call at all, ever."""
    calls: list[object] = []

    async def fake_post(*args, **kwargs):
        calls.append((args, kwargs))
        return {}

    monkeypatch.setattr("truegrit_api.services.sentry_reporter.post_raw_async", fake_post)
    asyncio.run(report_exception_async(ValueError("boom"), settings=settings_for("")))
    assert calls == []


def test_parse_dsn_extracts_envelope_url_and_keys():
    parsed = _parse_dsn("https://public_key@o123456.ingest.sentry.io/987654")
    assert parsed.envelope_url == "https://o123456.ingest.sentry.io/api/987654/envelope/"
    assert parsed.public_key == "public_key"
    assert parsed.secret_key is None


def test_parse_dsn_handles_self_hosted_path_prefix_and_port():
    parsed = _parse_dsn("http://key:secret@sentry.internal:9000/relay/42")
    assert parsed.envelope_url == "http://sentry.internal:9000/relay/api/42/envelope/"
    assert parsed.secret_key == "secret"


@pytest.mark.parametrize(
    "bad_dsn", ["", "not-a-url", "https://sentry.io/987654", "https://key@sentry.io/"]
)
def test_parse_dsn_rejects_malformed_input(bad_dsn):
    with pytest.raises(SentryDsnError):
        _parse_dsn(bad_dsn)


def test_auth_header_omits_secret_when_absent():
    parsed = _parse_dsn("https://public_key@o1.ingest.sentry.io/2")
    header = _auth_header(parsed)
    assert header.startswith("Sentry sentry_version=7")
    assert "sentry_key=public_key" in header
    assert "sentry_secret" not in header


def test_auth_header_includes_secret_when_present():
    parsed = _parse_dsn("https://key:secret@sentry.io/2")
    assert "sentry_secret=secret" in _auth_header(parsed)


def test_report_posts_a_well_formed_envelope(monkeypatch):
    sent: dict = {}

    async def fake_post(url, *, body, content_type, headers=None):
        sent["url"] = url
        sent["body"] = body
        sent["content_type"] = content_type
        sent["headers"] = headers
        return {"id": "abc"}

    monkeypatch.setattr("truegrit_api.services.sentry_reporter.post_raw_async", fake_post)

    try:
        raise ValueError("something broke")
    except ValueError as exc:
        asyncio.run(
            report_exception_async(
                exc,
                settings=settings_for("https://public_key@o1.ingest.sentry.io/55"),
                request_id="req_123",
            )
        )

    assert sent["url"] == "https://o1.ingest.sentry.io/api/55/envelope/"
    assert sent["content_type"] == "application/x-sentry-envelope"
    assert sent["headers"]["X-Sentry-Auth"].startswith("Sentry sentry_version=7")

    lines = sent["body"].strip("\n").split("\n")
    assert len(lines) == 3
    envelope_header, item_header, event = (json.loads(line) for line in lines)
    assert envelope_header["event_id"] == event["event_id"]
    assert len(envelope_header["event_id"]) == 32
    assert item_header["type"] == "event"
    assert item_header["length"] == len(lines[2].encode("utf-8"))
    assert event["exception"]["values"][0]["type"] == "ValueError"
    assert event["exception"]["values"][0]["value"] == "something broke"
    assert event["environment"] == "production"
    assert event["tags"]["request_id"] == "req_123"


def test_report_never_raises_when_the_transport_fails(monkeypatch):
    """A broken Sentry integration (network error, bad DSN, 5xx from Sentry)
    must never itself crash the request that triggered the report."""

    async def failing_post(*args, **kwargs):
        raise RuntimeError("network is down")

    monkeypatch.setattr("truegrit_api.services.sentry_reporter.post_raw_async", failing_post)
    # Must not raise.
    asyncio.run(
        report_exception_async(
            RuntimeError("original error"),
            settings=settings_for("https://public_key@o1.ingest.sentry.io/55"),
        )
    )


def test_report_never_raises_on_a_malformed_dsn(monkeypatch):
    calls: list[object] = []

    async def fake_post(*args, **kwargs):
        calls.append(args)
        return {}

    monkeypatch.setattr("truegrit_api.services.sentry_reporter.post_raw_async", fake_post)
    asyncio.run(report_exception_async(ValueError("boom"), settings=settings_for("not-a-dsn")))
    assert calls == []


def test_report_never_logs_the_dsn_secret(monkeypatch, capsys):
    async def failing_post(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("truegrit_api.services.sentry_reporter.post_raw_async", failing_post)
    asyncio.run(
        report_exception_async(
            ValueError("x"),
            settings=settings_for("https://key:top-secret@sentry.io/1"),
        )
    )
    assert "top-secret" not in capsys.readouterr().out

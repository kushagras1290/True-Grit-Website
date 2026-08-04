"""Raw cookie-header parsing for code paths that run before (or entirely
outside) FastAPI's own cookie handling — the Workers entry point's
direct-D1 bypasses (`worker.py`) and the chat Durable Object
(`realtime/chat_room.py`), neither of which has access to
`starlette.Request.cookies`.
"""

from __future__ import annotations

from typing import Any


def cookie_value(request: Any, name: str) -> str | None:
    cookie_header = request.headers.get("cookie") or ""
    for item in str(cookie_header).split(";"):
        key, separator, value = item.strip().partition("=")
        if separator and key == name:
            return value
    return None

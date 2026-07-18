"""Central error handling: AppError -> stable JSON envelope; everything else -> opaque 500."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from truegrit_api.errors import AppError
from truegrit_api.logging import log_event
from truegrit_api.platform.database import Database
from truegrit_api.services.log_persistence import persist_log


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _envelope(
    request: Request, code: str, message: str, details: object = None
) -> dict[str, object]:
    body: dict[str, object] = {"code": code, "message": message, "requestId": _request_id(request)}
    if details is not None:
        body["details"] = details
    return {"error": body}


async def _persist_log_best_effort(request: Request, level: str, event: str, /, **fields: Any) -> None:
    """Write the 5xx/unhandled event to `application_logs` for the owner's
    Server Logs page. Best-effort: we are already inside an exception handler,
    so a persistence failure here (e.g. `db` unset in a unit test app, or the
    write itself failing) must never replace the response we are about to
    send with a second, worse error."""
    db: Database | None = getattr(request.app.state, "db", None)
    if db is None:
        return
    try:
        await persist_log(db, level, event, **fields)
    except Exception:
        log_event("error", "application_log_persist_failed", request_id=_request_id(request))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.http_status >= 500:
            request_id = _request_id(request)
            log_event("error", "app_error", request_id=request_id, code=exc.code)
            await _persist_log_best_effort(request, "error", "app_error", request_id=request_id, code=exc.code)
        return JSONResponse(
            status_code=exc.http_status,
            content=_envelope(request, exc.code, exc.message, exc.details),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        issues = [
            {"loc": [str(part) for part in error["loc"]], "msg": error["msg"]}
            for error in exc.errors()[:10]
        ]
        return JSONResponse(
            status_code=422,
            content=_envelope(request, "validation_error", "Request failed validation.", issues),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = _request_id(request)
        log_event(
            "error",
            "unhandled_exception",
            request_id=request_id,
            error_type=type(exc).__name__,
        )
        await _persist_log_best_effort(
            request, "error", "unhandled_exception", request_id=request_id, error_type=type(exc).__name__
        )
        return JSONResponse(
            status_code=500,
            content=_envelope(request, "internal_error", "Something went wrong."),
        )

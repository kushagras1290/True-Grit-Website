"""Central error handling: AppError -> stable JSON envelope; everything else -> opaque 500."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from truegrit_api.errors import AppError
from truegrit_api.logging import log_event


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def _envelope(
    request: Request, code: str, message: str, details: object = None
) -> dict[str, object]:
    body: dict[str, object] = {"code": code, "message": message, "requestId": _request_id(request)}
    if details is not None:
        body["details"] = details
    return {"error": body}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        if exc.http_status >= 500:
            log_event("error", "app_error", request_id=_request_id(request), code=exc.code)
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
        log_event(
            "error",
            "unhandled_exception",
            request_id=_request_id(request),
            error_type=type(exc).__name__,
        )
        return JSONResponse(
            status_code=500,
            content=_envelope(request, "internal_error", "Something went wrong."),
        )

"""Application error hierarchy.

Every error surfaced to a client uses the stable envelope:
{"error": {"code", "message", "details?", "requestId"}}. Stack traces, SQL, and
provider credentials never leave the process.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    code = "app_error"
    http_status = 500

    def __init__(
        self, message: str = "Something went wrong.", details: dict[str, Any] | None = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details


class ValidationAppError(AppError):
    code = "validation_error"
    http_status = 422


class AuthenticationError(AppError):
    code = "authentication_required"
    http_status = 401

    def __init__(self, message: str = "Authentication required."):
        super().__init__(message)


class PermissionDeniedError(AppError):
    code = "permission_denied"
    http_status = 403

    def __init__(self, message: str = "You do not have permission to do this."):
        super().__init__(message)


class CsrfError(AppError):
    """A state-changing request arrived without a valid X-CSRF-Token.

    Its own code (distinct from permission_denied) so a client can tell "you
    need a fresh CSRF token" apart from "you are not allowed to do this" and
    react by refetching one instead of showing a dead-end permission error.
    """

    code = "csrf_invalid"
    http_status = 403

    def __init__(self, message: str = "Missing or invalid CSRF token."):
        super().__init__(message)


class NotFoundError(AppError):
    code = "not_found"
    http_status = 404

    def __init__(self, message: str = "Not found."):
        super().__init__(message)


class ConflictError(AppError):
    code = "conflict"
    http_status = 409


class RateLimitError(AppError):
    code = "rate_limited"
    http_status = 429

    def __init__(
        self,
        message: str = "Too many requests. Try again shortly.",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message, details)


class PhoneRequiredError(AppError):
    """The action needs a verified mobile the account does not have yet.

    Its own code so the storefront can open the verification flow instead of
    printing a message the customer has no way to act on — the difference between
    "here is a Verify button" and a dead end at checkout.
    """

    code = "phone_verification_required"
    http_status = 422

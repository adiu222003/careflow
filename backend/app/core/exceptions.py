"""
Centralized exception types and FastAPI exception handlers.
All error responses follow the shape: {"success": false, "error": {"code": ..., "message": ...}}
Internal details (stack traces, SQL errors, secrets) are never exposed.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Custom exception base ────────────────────────────────────────────────────

class CareFlowError(Exception):
    """Base exception for all application-level errors."""
    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = "INTERNAL_ERROR"
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)
        if message:
            self.message = message


class NotFoundError(CareFlowError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "NOT_FOUND"
    message = "The requested resource was not found."


class ConflictError(CareFlowError):
    status_code = status.HTTP_409_CONFLICT
    code = "CONFLICT"
    message = "A conflict occurred."


class SlotUnavailableError(CareFlowError):
    status_code = status.HTTP_409_CONFLICT
    code = "SLOT_NO_LONGER_AVAILABLE"
    message = "The selected slot is no longer available."


class HoldExpiredError(CareFlowError):
    status_code = status.HTTP_410_GONE
    code = "HOLD_EXPIRED"
    message = "The slot reservation has expired. Please start a new booking."


class ForbiddenError(CareFlowError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "FORBIDDEN"
    message = "You do not have permission to perform this action."


class ValidationError(CareFlowError):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    code = "VALIDATION_ERROR"
    message = "Request validation failed."


class ExternalServiceError(CareFlowError):
    """Raised when an external service (Gemini, Resend, Google) fails."""
    status_code = status.HTTP_502_BAD_GATEWAY
    code = "EXTERNAL_SERVICE_ERROR"
    message = "An external service is temporarily unavailable."


# ── Error response helper ────────────────────────────────────────────────────

def error_response(code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message}},
    )


def register_exception_handlers(app: FastAPI) -> None:
    from starlette.exceptions import HTTPException as StarletteHTTPException

    @app.exception_handler(CareFlowError)
    async def careflow_error_handler(request: Request, exc: CareFlowError) -> JSONResponse:
        return error_response(exc.code, exc.message, exc.status_code)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Check if detail is already our custom dict shape
        if isinstance(exc.detail, dict) and "code" in exc.detail and "message" in exc.detail:
            code = exc.detail["code"]
            message = exc.detail["message"]
        else:
            code = "HTTP_ERROR"
            message = str(exc.detail)
        return error_response(code, message, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Never expose internal field paths to the client
        return error_response(
            "VALIDATION_ERROR",
            "One or more request fields are invalid.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
        # Log the real error server-side; return generic message to client
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return error_response(
            "INTERNAL_ERROR",
            "An unexpected error occurred. Please try again later.",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger
from app.middleware.request_id import REQUEST_ID_HEADER

logger = get_logger(__name__)


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _log_extra(
    request: Request,
    *,
    status_code: int,
    error_code: str,
) -> dict[str, object]:
    return {
        "request_id": _request_id(request),
        "path": request.url.path,
        "method": request.method,
        "status_code": status_code,
        "error_code": error_code,
    }


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str | None,
) -> JSONResponse:
    headers = {REQUEST_ID_HEADER: request_id} if request_id else None
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "status": "error",
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


async def validation_error_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    logger.error(
        "Request validation failed.",
        extra={
            **_log_extra(request, status_code=422, error_code="invalid_request"),
            "validation_errors": exc.errors(),
        },
    )
    return _error_response(
        status_code=422,
        code="invalid_request",
        message="Request validation failed.",
        request_id=_request_id(request),
    )


async def http_error_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code_by_status = {
        404: "not_found",
        405: "method_not_allowed",
    }
    error_code = code_by_status.get(exc.status_code, "http_error")
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."

    logger.error(
        "HTTP error.",
        extra=_log_extra(
            request,
            status_code=exc.status_code,
            error_code=error_code,
        ),
    )
    return _error_response(
        status_code=exc.status_code,
        code=error_code,
        message=detail,
        request_id=_request_id(request),
    )


async def unhandled_error_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    logger.exception(
        "Unhandled server error.",
        extra=_log_extra(
            request,
            status_code=500,
            error_code="internal_server_error",
        ),
        exc_info=exc,
    )
    return _error_response(
        status_code=500,
        code="internal_server_error",
        message="Internal server error.",
        request_id=_request_id(request),
    )

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes_analyze import router as analyze_router
from app.api.routes_generation import router as generation_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings


async def validation_error_handler(
    _request: Request,
    _exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "error": {
                "code": "invalid_request",
                "message": "Request validation failed.",
            },
        },
    )


async def http_error_handler(
    _request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    code_by_status = {
        404: "not_found",
        405: "method_not_allowed",
    }
    detail = exc.detail if isinstance(exc.detail, str) else "HTTP error."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "error": {
                "code": code_by_status.get(exc.status_code, "http_error"),
                "message": detail,
            },
        },
    )


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    cors_origins = settings.allowed_cors_origins()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.include_router(health_router)
    app.include_router(analyze_router, prefix="/api/v2")
    app.include_router(generation_router, prefix="/api/v2")
    return app


app = create_app()

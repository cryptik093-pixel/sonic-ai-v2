from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes_analyze import router as analyze_router
from app.api.routes_generation import router as generation_router
from app.api.routes_health import router as health_router
from app.api.routes_master import router as master_router
from app.api.routes_flagship import router as flagship_router
from app.api.routes_agents import router as agents_router
from app.core.config import get_settings
from app.middleware.error_handler import (
    http_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)
from app.middleware.request_id import RequestIDMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    cors_origins = settings.allowed_cors_origins()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials="*" not in cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(StarletteHTTPException, http_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)
    app.include_router(health_router)
    app.include_router(analyze_router, prefix="/api/v2")
    app.include_router(generation_router, prefix="/api/v2")
    app.include_router(master_router, prefix="/api/v2")
    app.include_router(flagship_router, prefix="/api/v2")
    app.include_router(agents_router, prefix="/api/v2")
    return app


app = create_app()

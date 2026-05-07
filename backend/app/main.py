from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_analyze import router as analyze_router
from app.api.routes_generation import router as generation_router
from app.api.routes_health import router as health_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    # CORS: allow the deployed frontend and local dev hosts
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://omega-house.online",
            "https://www.omega-house.online",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health_router)
    app.include_router(analyze_router, prefix="/api/v2")
    app.include_router(generation_router, prefix="/api/v2")
    return app


app = create_app()

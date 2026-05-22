from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MAX_UPLOAD_BYTES = 200 * 1024 * 1024


class Settings(BaseSettings):
    app_name: str = "Sonic AI V2 API"
    service_name: str = "sonic-ai-v2-backend"
    version: str = "0.1.0"
    environment: str = "development"
    max_upload_mb: int = 200
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES
    upload_read_chunk_bytes: int = 1024 * 1024
    cors_origins: str = (
        "https://omega-house.online,"
        "https://www.omega-house.online,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173"
    )

    model_config = SettingsConfigDict(env_prefix="SONIC_AI_")

    @property
    def upload_limit_bytes(self) -> int:
        if self.max_upload_bytes != DEFAULT_MAX_UPLOAD_BYTES:
            return self.max_upload_bytes
        return self.max_upload_mb * 1024 * 1024

    def allowed_cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        return origins or ["http://localhost:5173", "http://127.0.0.1:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()

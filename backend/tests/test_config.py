from app.core.config import Settings, get_settings


def test_default_upload_limit_is_200_mb() -> None:
    settings = Settings()

    assert settings.max_upload_bytes == 200 * 1024 * 1024
    assert settings.upload_read_chunk_bytes == 1024 * 1024


def test_cors_origins_are_parsed_from_comma_separated_env(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "SONIC_AI_CORS_ORIGINS",
        "https://app.example.com, https://www.example.com ,, http://localhost:5173",
    )
    get_settings.cache_clear()

    settings = get_settings()
    get_settings.cache_clear()

    assert settings.allowed_cors_origins() == [
        "https://app.example.com",
        "https://www.example.com",
        "http://localhost:5173",
    ]

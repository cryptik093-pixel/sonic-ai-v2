from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse

from app.audio.reference_profiles import REFERENCE_PROFILES
from app.core.config import get_settings
from app.models.analysis_models import AnalyzeSuccessResponse

router = APIRouter(tags=["analysis"])

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".wave", ".flac", ".aiff", ".aif", ".mp3", ".ogg"}
VALID_TARGET_PROFILE_IDS = tuple(REFERENCE_PROFILES.keys())
TARGET_PROFILE_DESCRIPTION = (
    "Reference profile id. Valid values: "
    + ", ".join(VALID_TARGET_PROFILE_IDS)
    + ". Defaults to modern_hiphop_master."
)


@router.post("/analyze", response_model=AnalyzeSuccessResponse)
async def analyze_audio(
    file: Annotated[UploadFile, File(...)],
    target_profile: Annotated[
        str | None,
        Form(
            alias="target_profile",
            description=TARGET_PROFILE_DESCRIPTION,
            examples=["modern_hiphop_master"],
            json_schema_extra={"enum": list(VALID_TARGET_PROFILE_IDS)},
        ),
    ] = None,
    target_profile_query: Annotated[
        str | None,
        Query(
            alias="target_profile",
            description=TARGET_PROFILE_DESCRIPTION,
            examples=["modern_hiphop_master"],
            json_schema_extra={"enum": list(VALID_TARGET_PROFILE_IDS)},
        ),
    ] = None,
) -> AnalyzeSuccessResponse | JSONResponse:
    selected_target_profile = target_profile or target_profile_query or "modern_hiphop_master"
    filename = file.filename or ""
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_AUDIO_EXTENSIONS:
        return _error_response(
            status_code=400,
            code="unsupported_audio_format",
            message=(
                f"Unsupported audio file extension '{suffix}'. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_AUDIO_EXTENSIONS))}."
            ),
        )
    if selected_target_profile not in VALID_TARGET_PROFILE_IDS:
        return _unknown_target_profile_response(selected_target_profile)

    temp_path: Path | None = None
    try:
        settings = get_settings()
        upload_bytes = await _read_upload_with_limit(
            file,
            max_upload_bytes=settings.upload_limit_bytes,
            chunk_size=settings.upload_read_chunk_bytes,
        )
        if not upload_bytes:
            return _error_response(
                status_code=400,
                code="empty_file",
                message="Uploaded audio file is empty.",
            )

        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(upload_bytes)
            temp_path = Path(temp_file.name)

        from app.services.analyzer_service import AnalyzerService, analysis_result_to_dict

        service = AnalyzerService()
        result = service.analyze_file_path(temp_path, profile_id=selected_target_profile)
        analysis = analysis_result_to_dict(result)
        analysis["filename"] = filename
        return AnalyzeSuccessResponse(status="completed", analysis=analysis)
    except FileTooLargeError:
        settings = get_settings()
        return _error_response(
            status_code=413,
            code="file_too_large",
            message=(
                "Uploaded audio file exceeds the "
                f"{_format_byte_limit(settings.upload_limit_bytes)} limit."
            ),
        )
    except ValueError as exc:
        code = (
            "unknown_target_profile"
            if "Unknown reference profile" in str(exc)
            else "invalid_request"
        )
        return _error_response(status_code=400, code=code, message=str(exc))
    except Exception:
        error_type, error_message = _analysis_error_details()
        if error_type and error_message:
            return _error_response(
                status_code=400,
                code=error_type,
                message=error_message,
            )
        return _error_response(
            status_code=500,
            code="analysis_failed",
            message="Unexpected analysis failure.",
        )
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        await file.close()


async def _read_upload_with_limit(
    file: UploadFile,
    *,
    max_upload_bytes: int,
    chunk_size: int,
) -> bytes:
    chunks: list[bytes] = []
    total_size = 0
    while chunk := await file.read(chunk_size):
        total_size += len(chunk)
        if total_size > max_upload_bytes:
            raise FileTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


class FileTooLargeError(Exception):
    """Raised when an uploaded file exceeds the configured analysis limit."""


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "error",
            "error": {
                "code": code,
                "message": message,
            },
        },
    )


def _unknown_target_profile_response(profile_id: str) -> JSONResponse:
    return _error_response(
        status_code=400,
        code="unknown_target_profile",
        message=f"Unknown reference profile: '{profile_id}'.",
    )


def _format_byte_limit(max_upload_bytes: int) -> str:
    if max_upload_bytes >= 1024 * 1024 and max_upload_bytes % (1024 * 1024) == 0:
        return f"{max_upload_bytes // (1024 * 1024)} MB"
    return f"{max_upload_bytes} byte"


def _analysis_error_details() -> tuple[str | None, str | None]:
    try:
        from app.audio.loader import AudioLoadError
        from app.services.analyzer_service import AnalysisServiceError
    except Exception:
        return None, None

    import sys

    exc = sys.exc_info()[1]
    if isinstance(exc, AudioLoadError):
        return "audio_load_failed", f"Uploaded audio could not be loaded: {exc}"
    if isinstance(exc, AnalysisServiceError):
        return "analysis_service_error", str(exc)
    return None, None

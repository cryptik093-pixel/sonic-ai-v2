from __future__ import annotations

import base64
from typing import Annotated

from fastapi import APIRouter, File, Form, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.logging import get_logger
from app.services.mastering_service import MasteringService, MasteringServiceError
from app.schemas.mastering import MasterAudioJsonResponse
from app.utils.streaming import stream_temp_file

router = APIRouter(tags=["mastering"])

logger = get_logger(__name__)


class FileTooLargeError(Exception):
    pass


async def _read_upload_with_limit(
    file: UploadFile,
    *,
    max_upload_bytes: int,
    chunk_size: int,
) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total += len(chunk)
        if total > max_upload_bytes:
            raise FileTooLargeError
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/master-audio", response_model=MasterAudioJsonResponse)
async def master_audio(
    file: Annotated[UploadFile, File(...)],
    target_lufs: Annotated[float | None, Form(default=-14.0)] | None = None,
    format: Annotated[
        str | None,
        Query(
            alias="format",
            description="Response format: 'wav' (default) or 'json'.",
        ),
    ] = None,
):
    settings = get_settings()
    try:
        upload_bytes = await _read_upload_with_limit(
            file,
            max_upload_bytes=settings.upload_limit_bytes,
            chunk_size=settings.upload_read_chunk_bytes,
        )
        if not upload_bytes:
            return JSONResponse(
                status_code=400,
                content={
                    "status": "error",
                    "error": {
                        "code": "empty_file",
                        "message": "Uploaded file is empty.",
                    },
                },
            )

        service = MasteringService()
        # Offload CPU-bound mastering to a threadpool to avoid blocking the event loop
        result = await run_in_threadpool(
            service.master,
            upload_bytes,
            target_lufs=target_lufs,
        )

        wants_json = False
        if format is not None:
            wants_json = format.lower() == "json"
        else:
            # Default to binary WAV
            wants_json = False

        if wants_json:
            wav_b64 = base64.b64encode(result.wav_bytes).decode("ascii")
            return JSONResponse(
                content={
                    "status": "completed",
                    "byte_length": len(result.wav_bytes),
                    "media_type": "audio/wav",
                    "encoding": "base64",
                    "data_base64": wav_b64,
                }
            )

        filename = f"sonic_ai_mastered_{file.filename or 'audio'}.wav"
        return stream_temp_file(result.wav_bytes, filename)

    except FileTooLargeError:
        return JSONResponse(
            status_code=413,
            content={
                "status": "error",
                "error": {
                    "code": "file_too_large",
                    "message": "Uploaded audio file exceeds the configured limit.",
                },
            },
        )
    except MasteringServiceError as exc:
        logger.exception("Mastering service failed: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": {"code": "mastering_failed", "message": str(exc)},
            },
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Unexpected mastering error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": {
                    "code": "mastering_failed",
                    "message": "Unexpected mastering failure.",
                },
            },
        )
    finally:
        try:
            await file.close()
        except Exception:
            pass

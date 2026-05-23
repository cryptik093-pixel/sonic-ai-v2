import base64
from dataclasses import dataclass
from io import BytesIO
from typing import Annotated, Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.audio.prompt_to_midi import (
    generate_prompt_midi,
    interpret_prompt,
    parse_prompt,
)
from app.core.logging import get_logger
from app.schemas.midi_generation import MidiData, PromptMeta, PromptMIDIResponse

router = APIRouter(tags=["generation"])

logger = get_logger(__name__)


def _empty_prompt_response() -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "status": "error",
            "error": {
                "code": "empty_prompt",
                "message": "Prompt must not be empty.",
            },
        },
    )


def _generation_failure_response() -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={
            "status": "error",
            "error": {
                "code": "generation_failed",
                "message": "Unexpected prompt MIDI generation failure.",
            },
        },
    )


def _render_prompt_midi(prompt: str, seed: int | None):
    prompt_spec = parse_prompt(prompt)
    prompt_intent = interpret_prompt(prompt_spec)
    result = generate_prompt_midi(prompt, seed=seed)
    return prompt_spec, prompt_intent, result.midi_bytes


def _midi_download_headers(
    prompt_spec,
    prompt_intent,
    seed: int | None,
    midi_bytes: bytes,
) -> dict[str, str]:
    filename_seed = "deterministic" if seed is None else str(seed)
    safe_key = (prompt_spec.key or "key").replace('"', "_").replace("\\", "_").replace("/", "_")
    suggested_filename = f"sonic_ai_{safe_key}_{filename_seed}.mid"
    return {
        "X-Prompt": prompt_spec.raw_prompt,
        "X-Seed": "" if seed is None else str(seed),
        "X-Key": prompt_spec.key,
        "X-Mode": prompt_intent.mode,
        "Content-Disposition": f'attachment; filename="{suggested_filename}"',
        "Content-Length": str(len(midi_bytes)),
    }


def _json_prompt_midi_payload(
    *,
    prompt_spec,
    prompt_intent,
    seed: int | None,
    midi_bytes: bytes,
) -> dict:
    midi_b64 = base64.b64encode(midi_bytes).decode("ascii")
    prompt_meta = PromptMeta(
        raw=prompt_spec.raw_prompt,
        seed=seed,
        tempo_bpm=prompt_intent.tempo_bpm,
        key=prompt_intent.key,
        mode=prompt_intent.mode,
        pattern_type=prompt_intent.pattern_type,
        density=prompt_intent.density,
        complexity=prompt_intent.complexity,
        mood_modifiers=list(prompt_intent.mood_modifiers),
        primary_mood=prompt_intent.primary_mood,
        rhythm_style=prompt_intent.rhythm_style,
        rhythm_grid=prompt_intent.rhythm_grid,
        contour_rule=prompt_intent.contour_rule,
        chord_degrees=list(prompt_intent.chord_degrees),
    )
    midi_data = MidiData(
        media_type="audio/midi",
        encoding="base64",
        byte_length=len(midi_bytes),
        data_base64=midi_b64,
    )
    return PromptMIDIResponse(
        status="completed",
        prompt=prompt_meta,
        midi=midi_data,
    ).model_dump()


class PromptMIDIRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "prompt": "dark trap melody at 140 bpm in D minor",
                    "seed": 12,
                },
                {
                    "prompt": "emotional chord progression at 92 bpm in F# minor",
                    "seed": 3,
                },
            ]
        }
    )

    prompt: str = Field(
        description="Music prompt to interpret with the deterministic rule-based MIDI engine.",
        examples=["dark trap melody at 140 bpm in D minor"],
    )
    seed: int | None = Field(
        default=None,
        description=(
            "Optional deterministic seed. Same prompt plus same seed returns "
            "identical MIDI bytes."
        ),
        examples=[12],
    )


@dataclass(frozen=True)
class ParsedPromptMIDIRequest:
    request: PromptMIDIRequest
    response_format: str | None
    source: Literal["json", "form"]


_FORM_CONTENT_TYPES = {
    "application/x-www-form-urlencoded",
    "multipart/form-data",
}

_PROMPT_MIDI_REQUEST_BODY = {
    "requestBody": {
        "required": True,
        "content": {
            "application/json": {
                "schema": PromptMIDIRequest.model_json_schema(),
            },
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "required": ["prompt"],
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": (
                                "Music prompt to interpret with the deterministic "
                                "rule-based MIDI engine."
                            ),
                            "examples": ["dark trap melody at 140 bpm in D minor"],
                        },
                        "seed": {
                            "type": "integer",
                            "nullable": True,
                            "description": (
                                "Optional deterministic seed. Same prompt plus same "
                                "seed returns identical MIDI bytes."
                            ),
                            "examples": [12],
                        },
                        "format": {
                            "type": "string",
                            "enum": ["midi", "json"],
                            "description": "Response format: 'midi' or 'json'.",
                        },
                    },
                },
            },
        },
    }
}


def _invalid_request_response() -> JSONResponse:
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


def _text_or_none(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value)


async def _read_prompt_midi_request(
    http_request: Request,
) -> ParsedPromptMIDIRequest | JSONResponse:
    content_type = http_request.headers.get("content-type", "").partition(";")[0].lower()
    source: Literal["json", "form"] = "form" if content_type in _FORM_CONTENT_TYPES else "json"

    try:
        if source == "form":
            form = await http_request.form()
            raw_payload = {key: value for key, value in form.items()}
        else:
            raw_payload = await http_request.json()
    except ValueError:
        return _invalid_request_response()

    if not isinstance(raw_payload, dict):
        return _invalid_request_response()

    payload = dict(raw_payload)
    response_format = _text_or_none(payload.pop("format", None))

    try:
        request_payload = PromptMIDIRequest.model_validate(payload)
    except ValidationError:
        return _invalid_request_response()

    return ParsedPromptMIDIRequest(
        request=request_payload,
        response_format=response_format,
        source=source,
    )


@router.post(
    "/prompt-midi",
    response_model=PromptMIDIResponse,
    openapi_extra=_PROMPT_MIDI_REQUEST_BODY,
)
async def prompt_midi(
    http_request: Request,
    format: Annotated[
        str | None,
        Query(alias="format", description="Response format: 'midi' (default) or 'json'."),
    ] = None,
) -> StreamingResponse | JSONResponse:
    parsed_request = await _read_prompt_midi_request(http_request)
    if isinstance(parsed_request, JSONResponse):
        return parsed_request

    request = parsed_request.request
    prompt = request.prompt.strip()
    if not prompt:
        return _empty_prompt_response()

    try:
        prompt_spec, prompt_intent, midi_bytes = _render_prompt_midi(prompt, request.seed)
    except Exception as exc:  # pragma: no cover - defensive error mapping
        logger.exception("Prompt MIDI generation failed: %s", exc)
        return _generation_failure_response()

    # Determine whether the client explicitly requested JSON output. The
    # query parameter `format=json` takes precedence over the Accept header.
    response_format = format if format is not None else parsed_request.response_format
    wants_json = False
    if response_format is not None:
        wants_json = response_format.lower() == "json"
    else:
        wants_json = "application/json" in http_request.headers.get("accept", "")

    if wants_json:
        canonical_payload = _json_prompt_midi_payload(
            prompt_spec=prompt_spec,
            prompt_intent=prompt_intent,
            seed=request.seed,
            midi_bytes=midi_bytes,
        )
        if parsed_request.source == "form":
            return JSONResponse(
                content={
                    "status": "ok",
                    "midi_base64": canonical_payload["midi"]["data_base64"],
                    "prompt": canonical_payload["prompt"],
                    "midi": canonical_payload["midi"],
                }
            )
        return JSONResponse(content=canonical_payload)

    headers = _midi_download_headers(prompt_spec, prompt_intent, request.seed, midi_bytes)

    return StreamingResponse(
        BytesIO(midi_bytes), media_type="audio/midi", headers=headers
    )


@router.post(
    "/prompt-midi/download",
    response_model=None,
    openapi_extra=_PROMPT_MIDI_REQUEST_BODY,
)
async def download_prompt_midi(
    http_request: Request,
) -> StreamingResponse | JSONResponse:
    """
    Explicit form endpoint for clients that always want a downloadable MIDI file.
    """

    parsed_request = await _read_prompt_midi_request(http_request)
    if isinstance(parsed_request, JSONResponse):
        return parsed_request

    request = parsed_request.request
    prompt = request.prompt.strip()
    if not prompt:
        return _empty_prompt_response()

    try:
        prompt_spec, prompt_intent, midi_bytes = _render_prompt_midi(prompt, request.seed)
    except Exception as exc:  # pragma: no cover - defensive error mapping
        logger.exception("Prompt MIDI download failed: %s", exc)
        return _generation_failure_response()

    headers = _midi_download_headers(prompt_spec, prompt_intent, request.seed, midi_bytes)
    return StreamingResponse(
        BytesIO(midi_bytes), media_type="audio/midi", headers=headers
    )

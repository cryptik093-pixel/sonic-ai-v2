import base64
from io import BytesIO

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from app.audio.prompt_to_midi import (
    generate_prompt_midi,
    interpret_prompt,
    parse_prompt,
)

router = APIRouter(tags=["generation"])


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


@router.post("/prompt-midi", response_model=None)
async def prompt_midi(
    request: PromptMIDIRequest,
    http_request: Request,
) -> StreamingResponse | JSONResponse:
    prompt = request.prompt.strip()
    if not prompt:
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

    try:
        prompt_spec = parse_prompt(prompt)
        prompt_intent = interpret_prompt(prompt_spec)
        result = generate_prompt_midi(prompt, seed=request.seed)
    except Exception:
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

    midi_bytes = result.midi_bytes

    if "application/json" in http_request.headers.get("accept", ""):
        return JSONResponse(
            content={
                "status": "completed",
                "prompt": {
                    "raw": prompt_spec.raw_prompt,
                    "seed": request.seed,
                    "tempo_bpm": prompt_intent.tempo_bpm,
                    "key": prompt_intent.key,
                    "mode": prompt_intent.mode,
                    "pattern_type": prompt_intent.pattern_type,
                    "density": prompt_intent.density,
                    "complexity": prompt_intent.complexity,
                    "mood_modifiers": list(prompt_intent.mood_modifiers),
                    "primary_mood": prompt_intent.primary_mood,
                    "rhythm_style": prompt_intent.rhythm_style,
                    "rhythm_grid": prompt_intent.rhythm_grid,
                    "contour_rule": prompt_intent.contour_rule,
                    "chord_degrees": list(prompt_intent.chord_degrees),
                },
                "midi": {
                    "media_type": "audio/midi",
                    "encoding": "base64",
                    "byte_length": len(midi_bytes),
                    "data_base64": base64.b64encode(midi_bytes).decode("ascii"),
                },
            },
        )

    return StreamingResponse(
        BytesIO(midi_bytes),
        media_type="audio/midi",
        headers={
            "X-Prompt": prompt_spec.raw_prompt,
            "X-Seed": "" if request.seed is None else str(request.seed),
            "X-Key": prompt_spec.key,
            "X-Mode": prompt_intent.mode,
        },
    )

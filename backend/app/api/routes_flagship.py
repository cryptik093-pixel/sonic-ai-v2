from __future__ import annotations

import json
import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.logging import get_logger
from app.api.audio.prompt_to_midi import parse_prompt, interpret_prompt, generate_prompt_midi


logger = get_logger(__name__)

router = APIRouter(tags=["flagship"])


class FlagshipGenerateRequest(BaseModel):
    prompts: List[str] = Field(
        default_factory=lambda: [
            "dark trap melody at 140 bpm in D minor",
            "emotional chord progression at 92 bpm in F# minor",
        ]
    )
    seeds: Optional[List[Optional[int]]] = Field(
        default=None,
        description=(
            "Optional list of deterministic seeds. If shorter than prompts, missing "
            "values are treated as None (deterministic engine rules)."
        ),
    )
    ticks_per_beat: int = Field(default=480, description="MIDI ticks per beat for export.")
    output_dir: Optional[str] = Field(
        default=None, description="Optional output directory (overrides default outputs path)."
    )


@router.post("/flagship/generate")
async def flagship_generate(request: FlagshipGenerateRequest):
    """Generate a controlled flagship demo bundle of MIDI files and a manifest.

    This endpoint runs the deterministic prompt->MIDI engine for each prompt,
    saves the resulting MIDI files and a manifest.json under `outputs/flagship_demo/<timestamp>/` by
    default, and returns a JSON summary with file locations and parsed prompt metadata.
    """

    prompts = request.prompts or []
    if not prompts:
        raise HTTPException(status_code=400, detail="At least one prompt is required.")

    seeds = request.seeds or []
    # normalize seeds length to prompts length
    if len(seeds) < len(prompts):
        seeds = seeds + [None] * (len(prompts) - len(seeds))

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base = Path(request.output_dir) if request.output_dir else Path("outputs/flagship_demo")
    out_dir = base / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    created: list[dict] = []

    for idx, prompt in enumerate(prompts):
        seed = seeds[idx]
        try:
            parsed = parse_prompt(prompt)
            plan = interpret_prompt(parsed)
            result = generate_prompt_midi(prompt, seed=seed)
        except Exception as exc:
            logger.exception("Flagship generation failed for prompt: %s", prompt)
            raise HTTPException(status_code=500, detail=f"Generation failed: {exc}")

        # safe filename
        safe = (
            parsed.raw_prompt.replace("/", "_").replace('"', "_").replace(" ", "_")
        )
        safe = safe[:120]
        filename = f"sonic_ai_flagship_{idx}_{safe}_{'det' if seed is None else seed}.mid"
        path = out_dir / filename
        path.write_bytes(result.midi_bytes)

        created.append(
            {
                "filename": filename,
                "path": str(path),
                "bytes_length": len(result.midi_bytes),
                "prompt": parsed.raw_prompt,
                "seed": seed,
                "tempo_bpm": parsed.tempo_bpm,
                "key": parsed.key,
                "mode": parsed.mode,
                "pattern_type": parsed.pattern_type,
                "tracks": [t.name for t in result.tracks],
            }
        )

    manifest = {"created_at": ts, "items": created}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    return {"status": "completed", "output_dir": str(out_dir), "manifest": manifest}

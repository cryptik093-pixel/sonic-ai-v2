from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict
import soundfile as sf
import numpy as np
import io
import base64
import random
import re

# Try to import optional dependencies; keep fallbacks
try:
    import pyloudnorm as pyln
except Exception:
    pyln = None

try:
    import mido
except Exception:
    mido = None

try:
    from mcp import FastMCP
except Exception:
    FastMCP = None

# --- FastMCP (optional) ---
if FastMCP is not None:
    mcp = FastMCP(title="Sonic AI V2 MCP", description="Sonic AI V2 MCP server")

    class HealthResponse(BaseModel):
        status: str
        service: str
        version: str

    @mcp.tool()
    async def health() -> HealthResponse:
        """Service health for MCP clients"""
        return HealthResponse(status="ok", service="sonic-ai-v2-backend", version="0.1.0")

# --- FastAPI app ---
app = FastAPI(title="Sonic AI V2 API", version="0.1.0")

# Mount MCP app if available at /mcp
if FastMCP is not None:
    app.mount("/mcp", mcp.streamable_http_app())

# Simple typed responses
class HealthModel(BaseModel):
    status: str = Field("ok")
    service: str = Field("sonic-ai-v2-backend")
    version: str = Field("0.1.0")

@app.get("/health", response_model=HealthModel)
async def health_route():
    """Simple health endpoint matching API contract"""
    return HealthModel()

# Metrics models
class Metrics(BaseModel):
    duration_seconds: float
    sample_rate: int
    channels: int
    peak: float
    integrated_lufs: Optional[float] = None

@app.post("/api/v2/analyze")
async def analyze_route(file: UploadFile = File(...), target_profile: str = "modern_hiphop_master"):
    """Deterministic, minimal audio analysis — deterministic metrics only.

    This is intentionally conservative: it returns deterministic scalar metrics
    computed from the audio file. Business logic (reference comparison, report
    generation) should be implemented in separate modules and tested.
    """
    contents = await file.read()
    if not contents:
        return JSONResponse(status_code=400, content={"status": "error", "error": {"code": "empty_file", "message": "Uploaded audio file is empty."}})

    try:
        data, sr = sf.read(io.BytesIO(contents), dtype='float32')
    except Exception as e:
        return JSONResponse(status_code=400, content={"status": "error", "error": {"code": "audio_load_failed", "message": f"Uploaded audio could not be loaded: {str(e)}"}})

    samples = np.asarray(data)
    if samples.ndim == 1:
        channels = 1
        mono = samples
        length = samples.shape[0]
    else:
        channels = samples.shape[1]
        mono = np.mean(samples, axis=1)
        length = samples.shape[0]

    duration = float(length) / int(sr)
    peak = float(np.max(np.abs(samples))) if samples.size else 0.0

    # Best-effort integrated LUFS using pyloudnorm if available
    integrated = None
    if pyln is not None:
        try:
            meter = pyln.Meter(sr)
            integrated = float(meter.integrated_loudness(mono))
        except Exception:
            integrated = None

    metrics = Metrics(duration_seconds=duration, sample_rate=int(sr), channels=int(channels), peak=peak, integrated_lufs=integrated)

    analysis = {
        "engine_version": "sonic-ai-v2-analysis-core-0.1.0",
        "filename": file.filename,
        "profile_id": target_profile,
        "metrics": metrics.dict(),
        "reference_comparison": {
            "profile_id": target_profile,
            "display_name": target_profile,
            "deltas": [],
            "overall_severity": "none",
            "strongest_issues": []
        },
        "engineering_report": {
            "summary": {
                "overall_grade": "unknown",
                "short_verdict": "Deterministic metrics produced.",
                "main_issue": None,
                "confidence": "medium"
            }
        }
    }

    return JSONResponse(content={"status": "completed", "analysis": analysis})

@app.post("/api/v2/prompt-midi")
async def prompt_midi(prompt: str = "", seed: Optional[int] = None):
    """Deterministic MIDI generator (rule-based). Returns base64 JSON by default."""
    if not prompt or not prompt.strip():
        return JSONResponse(status_code=400, content={"status": "error", "error": {"code": "empty_prompt", "message": "Prompt must not be empty."}})

    # Extract tempo if present (e.g., '140 bpm')
    m = re.search(r"(\d{2,3})\s*bpm", prompt, flags=re.IGNORECASE)
    bpm = int(m.group(1)) if m else 120

    rng = random.Random(seed if seed is not None else 0)

    if mido is None:
        # Fallback deterministic textual representation if mido not installed
        notes = [str(rng.randint(48, 72)) for _ in range(8)]
        midi_b64 = base64.b64encode(f"MIDI-FALLBACK:{','.join(notes)}".encode()).decode('ascii')
        byte_length = len(midi_b64)
    else:
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.MetaMessage('set_tempo', tempo=mido.bpm2tempo(bpm)))
        for i in range(8):
            note = rng.randint(48, 72)
            track.append(mido.Message('note_on', note=note, velocity=64, time=120))
            track.append(mido.Message('note_off', note=note, velocity=64, time=120))
        bio = io.BytesIO()
        mid.save(file=bio)
        b = bio.getvalue()
        midi_b64 = base64.b64encode(b).decode('ascii')
        byte_length = len(b)

    return JSONResponse(content={
        "status": "completed",
        "prompt": {
            "raw": prompt,
            "seed": seed,
        },
        "midi": {
            "media_type": "audio/midi",
            "encoding": "base64",
            "byte_length": byte_length,
            "data_base64": midi_b64
        }
    })

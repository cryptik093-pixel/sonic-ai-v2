from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class MidiData(BaseModel):
    media_type: str = Field(..., example="audio/midi")
    encoding: Literal["base64"] = Field(..., example="base64")
    byte_length: int = Field(..., example=12345)
    data_base64: str = Field(..., description="Base64-encoded MIDI bytes")


class PromptMeta(BaseModel):
    raw: str
    seed: Optional[int] = None
    tempo_bpm: int
    key: str
    mode: str
    pattern_type: str
    density: str
    complexity: str
    mood_modifiers: List[str]
    primary_mood: Optional[str]
    rhythm_style: str
    rhythm_grid: str
    contour_rule: str
    chord_degrees: List[int]


class PromptMIDIResponse(BaseModel):
    status: Literal["completed"] = Field(..., example="completed")
    prompt: PromptMeta
    midi: MidiData

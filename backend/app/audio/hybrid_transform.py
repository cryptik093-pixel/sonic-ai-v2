from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.audio.audio_to_midi import ExtractedAudioMIDI
from app.audio.midi_generation import Track
from app.audio.prompt_to_midi import (
    DEFAULT_KEY,
    DEFAULT_MODE,
    PromptIntent,
    PromptSpec,
    build_midi_plan,
    parse_prompt,
)

EngineMode = Literal["major", "minor"]
HybridTransformation = Literal[
    "preserve_extracted_audio_midi",
    "align_harmony_to_prompt",
    "adapt_tempo_to_prompt",
    "use_extracted_rhythm",
    "use_extracted_melody",
    "use_extracted_chord_hints",
]


@dataclass(frozen=True)
class HybridPlan:
    """Deterministic routing plan for future hybrid audio-plus-prompt transforms."""

    target_key: str
    target_mode: EngineMode
    target_tempo_bpm: int
    rhythm_grid: str
    requested_pattern_type: str
    transformations: tuple[HybridTransformation, ...]
    uses_prompt_key: bool
    uses_prompt_mode: bool
    uses_prompt_tempo: bool
    uses_extracted_key: bool
    uses_extracted_mode: bool
    uses_extracted_tempo: bool
    has_extracted_melody: bool
    has_extracted_drums: bool
    has_extracted_chord_hints: bool


@dataclass(frozen=True)
class HybridResult:
    """Phase 12 Step 1 result. This intentionally contains no generated MIDI."""

    prompt: PromptSpec
    intent: PromptIntent
    plan: HybridPlan
    tracks: tuple[Track, ...]
    midi_bytes: bytes


@dataclass(frozen=True)
class _PromptExplicitFields:
    tempo_bpm: int | None
    key: str | None
    mode: EngineMode | None


def plan_hybrid_transform(extracted: ExtractedAudioMIDI, prompt: str) -> HybridResult:
    """Build a typed hybrid transform plan without DSP or MIDI generation."""

    _validate_extracted(extracted)
    prompt_spec = parse_prompt(prompt)
    explicit = _prompt_explicit_fields(prompt_spec.raw_prompt)
    intent = build_midi_plan(prompt_spec)
    plan = build_hybrid_plan(extracted, prompt_spec, explicit)
    return HybridResult(
        prompt=prompt_spec,
        intent=intent,
        plan=plan,
        tracks=(),
        midi_bytes=b"",
    )


def build_hybrid_plan(
    extracted: ExtractedAudioMIDI,
    prompt: PromptSpec,
    explicit: _PromptExplicitFields | None = None,
) -> HybridPlan:
    """Select future transformation routes from existing typed structures only."""

    _validate_extracted(extracted)
    prompt_explicit = explicit or _prompt_explicit_fields(prompt.raw_prompt)

    target_key = prompt_explicit.key or _clean_key(extracted.key) or prompt.key or DEFAULT_KEY
    target_mode = (
        prompt_explicit.mode
        or _supported_mode(extracted.mode)
        or _supported_mode(prompt.mode)
        or _supported_mode(DEFAULT_MODE)
        or "minor"
    )
    target_tempo = _target_tempo_bpm(extracted, prompt, prompt_explicit)

    has_melody = extracted.melody_track is not None
    has_drums = extracted.drum_track is not None
    has_chord_hints = bool(extracted.chord_hints)

    transformations: list[HybridTransformation] = ["preserve_extracted_audio_midi"]
    if prompt_explicit.key is not None or prompt_explicit.mode is not None:
        transformations.append("align_harmony_to_prompt")
    if prompt_explicit.tempo_bpm is not None:
        transformations.append("adapt_tempo_to_prompt")
    if has_drums:
        transformations.append("use_extracted_rhythm")
    if has_melody:
        transformations.append("use_extracted_melody")
    if has_chord_hints:
        transformations.append("use_extracted_chord_hints")

    return HybridPlan(
        target_key=target_key,
        target_mode=target_mode,
        target_tempo_bpm=target_tempo,
        rhythm_grid=extracted.rhythm_grid or "straight_eighth_grid",
        requested_pattern_type=prompt.pattern_type,
        transformations=tuple(transformations),
        uses_prompt_key=prompt_explicit.key is not None,
        uses_prompt_mode=prompt_explicit.mode is not None,
        uses_prompt_tempo=prompt_explicit.tempo_bpm is not None,
        uses_extracted_key=prompt_explicit.key is None and _clean_key(extracted.key) is not None,
        uses_extracted_mode=(
            prompt_explicit.mode is None and _supported_mode(extracted.mode) is not None
        ),
        uses_extracted_tempo=(
            prompt_explicit.tempo_bpm is None and _valid_extracted_tempo(extracted) is not None
        ),
        has_extracted_melody=has_melody,
        has_extracted_drums=has_drums,
        has_extracted_chord_hints=has_chord_hints,
    )


def _target_tempo_bpm(
    extracted: ExtractedAudioMIDI,
    prompt: PromptSpec,
    explicit: _PromptExplicitFields,
) -> int:
    if explicit.tempo_bpm is not None:
        return explicit.tempo_bpm
    extracted_tempo = _valid_extracted_tempo(extracted)
    if extracted_tempo is not None:
        return extracted_tempo
    return max(1, int(prompt.tempo_bpm))


def _valid_extracted_tempo(extracted: ExtractedAudioMIDI) -> int | None:
    if extracted.tempo_bpm <= 0:
        return None
    return max(1, int(round(extracted.tempo_bpm)))


def _prompt_explicit_fields(prompt: str) -> _PromptExplicitFields:
    normalized = (prompt or "").lower()
    return _PromptExplicitFields(
        tempo_bpm=_explicit_tempo(normalized),
        key=_explicit_key(normalized),
        mode=_explicit_mode(normalized),
    )


def _explicit_tempo(prompt: str) -> int | None:
    match = re.search(
        r"\b([4-9][0-9]|1[0-9]{2}|2[0-4][0-9]|250)\s*(?:bpm|beats per minute)\b",
        prompt,
    )
    return int(match.group(1)) if match else None


def _explicit_key(prompt: str) -> str | None:
    match = re.search(
        r"(?<![a-z0-9])(?:in|key of)\s+([a-g](?:#|b)?)(?![a-z0-9#])",
        prompt,
    )
    if match is None:
        return None
    return _clean_key(match.group(1))


def _explicit_mode(prompt: str) -> EngineMode | None:
    if re.search(r"\bmajor\b", prompt):
        return "major"
    if re.search(r"\bminor\b", prompt):
        return "minor"
    return None


def _clean_key(key: str | None) -> str | None:
    if key is None:
        return None
    normalized = key.strip()
    if not normalized:
        return None
    return normalized[0].upper() + normalized[1:]


def _supported_mode(mode: str | None) -> EngineMode | None:
    if mode == "major":
        return "major"
    if mode == "minor":
        return "minor"
    return None


def _validate_extracted(extracted: ExtractedAudioMIDI) -> None:
    if not isinstance(extracted, ExtractedAudioMIDI):
        raise TypeError("extracted must be an ExtractedAudioMIDI handoff from Phase 10.")

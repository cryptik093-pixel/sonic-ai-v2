from app.audio.audio_to_midi import ExtractedAudioMIDI
from app.audio.hybrid_transform import (
    HybridPlan,
    HybridResult,
    build_hybrid_plan,
    plan_hybrid_transform,
)
from app.audio.midi_generation import Note, Pattern, Track
from app.audio.prompt_to_midi import PromptIntent, PromptSpec, parse_prompt


def test_hybrid_result_is_typed_and_does_not_generate_midi() -> None:
    result = plan_hybrid_transform(
        _extracted_audio_midi(key="C", mode="major", tempo_bpm=96.4),
        "make it dark in D minor at 140 bpm",
    )

    assert isinstance(result, HybridResult)
    assert isinstance(result.prompt, PromptSpec)
    assert isinstance(result.intent, PromptIntent)
    assert isinstance(result.plan, HybridPlan)
    assert result.tracks == ()
    assert result.midi_bytes == b""


def test_prompt_key_mode_and_explicit_tempo_override_extracted_values() -> None:
    result = plan_hybrid_transform(
        _extracted_audio_midi(key="C", mode="minor", tempo_bpm=88.2),
        "make a dreamy version in F# major at 130 bpm",
    )

    assert result.plan.target_key == "F#"
    assert result.plan.target_mode == "major"
    assert result.plan.target_tempo_bpm == 130
    assert result.plan.uses_prompt_key is True
    assert result.plan.uses_prompt_mode is True
    assert result.plan.uses_prompt_tempo is True
    assert result.plan.uses_extracted_key is False
    assert result.plan.uses_extracted_mode is False
    assert result.plan.uses_extracted_tempo is False


def test_missing_prompt_fields_fall_back_to_extracted_values() -> None:
    result = plan_hybrid_transform(
        _extracted_audio_midi(key="Eb", mode="minor", tempo_bpm=101.6),
        "make it sparse",
    )

    assert result.plan.target_key == "Eb"
    assert result.plan.target_mode == "minor"
    assert result.plan.target_tempo_bpm == 102
    assert result.plan.uses_prompt_key is False
    assert result.plan.uses_prompt_mode is False
    assert result.plan.uses_prompt_tempo is False
    assert result.plan.uses_extracted_key is True
    assert result.plan.uses_extracted_mode is True
    assert result.plan.uses_extracted_tempo is True


def test_missing_prompt_and_extracted_fields_use_stable_prompt_defaults() -> None:
    result = plan_hybrid_transform(
        _extracted_audio_midi(
            key=None,
            mode=None,
            tempo_bpm=0.0,
            include_melody=False,
            include_drums=False,
            chord_hints=None,
        ),
        "",
    )

    assert result.plan.target_key == "C"
    assert result.plan.target_mode == "minor"
    assert result.plan.target_tempo_bpm == 120
    assert result.plan.transformations == ("preserve_extracted_audio_midi",)
    assert result.plan.has_extracted_melody is False
    assert result.plan.has_extracted_drums is False
    assert result.plan.has_extracted_chord_hints is False


def test_deterministic_hybrid_plan_selection_from_prompt_and_audio_content() -> None:
    extracted = _extracted_audio_midi(
        key="C",
        mode="major",
        tempo_bpm=90.0,
        chord_hints=(0, 5),
    )
    prompt = parse_prompt("add energy in A minor at 150 bpm")

    first = build_hybrid_plan(extracted, prompt)
    second = build_hybrid_plan(extracted, prompt)

    assert first == second
    assert first.transformations == (
        "preserve_extracted_audio_midi",
        "align_harmony_to_prompt",
        "adapt_tempo_to_prompt",
        "use_extracted_rhythm",
        "use_extracted_melody",
        "use_extracted_chord_hints",
    )
    assert first.requested_pattern_type == "melody"


def test_track_content_only_routes_context_and_never_returns_tracks() -> None:
    result = plan_hybrid_transform(
        _extracted_audio_midi(key=None, mode=None, include_melody=False),
        "in G minor",
    )

    assert result.plan.has_extracted_melody is False
    assert result.plan.has_extracted_drums is True
    assert result.plan.transformations == (
        "preserve_extracted_audio_midi",
        "align_harmony_to_prompt",
        "use_extracted_rhythm",
    )
    assert result.tracks == ()
    assert result.midi_bytes == b""


def _extracted_audio_midi(
    *,
    tempo_bpm: float = 100.0,
    key: str | None = "C",
    mode: str | None = "minor",
    include_melody: bool = True,
    include_drums: bool = True,
    chord_hints: tuple[int, ...] | None = (),
) -> ExtractedAudioMIDI:
    return ExtractedAudioMIDI(
        tempo_bpm=tempo_bpm,
        beat_grid=(0.0, 0.6, 1.2, 1.8),
        melody_track=_melody_track() if include_melody else None,
        drum_track=_drum_track() if include_drums else None,
        chord_hints=chord_hints,
        key=key,
        mode=mode,
    )


def _melody_track() -> Track:
    pattern = Pattern(
        notes=(Note(60, 90, 0.0, 0.5), Note(62, 90, 0.5, 0.5)),
        tempo_bpm=100,
        length_beats=2.0,
    )
    return Track(name="Extracted Melody", role="melody", patterns=(pattern,))


def _drum_track() -> Track:
    pattern = Pattern(
        notes=(Note(36, 96, 0.0, 0.25, 9), Note(38, 90, 1.0, 0.25, 9)),
        tempo_bpm=100,
        length_beats=2.0,
    )
    return Track(name="Extracted Drums", role="drums", patterns=(pattern,))

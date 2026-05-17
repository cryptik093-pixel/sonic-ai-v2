from app.audio.midi_generation import (
    BasslineConfig,
    ChordProgressionConfig,
    DrumPatternConfig,
    MelodyConfig,
)
from app.audio.prompt_to_midi import build_midi_plan, generate_prompt_midi, parse_prompt


def test_parse_dark_trap_melody_extracts_tempo_key_mode_and_style() -> None:
    parsed = parse_prompt("Make a dark trap melody at 140 BPM in D minor")

    assert parsed.tempo_bpm == 140
    assert parsed.key == "D"
    assert parsed.root_pitch_class == 2
    assert parsed.mode == "minor"
    assert parsed.engine_scale == "minor"
    assert parsed.pattern_type == "melody"
    assert parsed.rhythm_style == "trap"
    assert parsed.mood_modifiers == ("dark",)


def test_parse_uk_drill_drums_uses_drill_rhythm_defaults() -> None:
    parsed = parse_prompt("Generate a UK drill drum pattern")
    plan = build_midi_plan(parsed)

    assert parsed.pattern_type == "drums"
    assert parsed.rhythm_style == "drill"
    assert parsed.tempo_bpm == 142
    assert isinstance(plan.engine_config, DrumPatternConfig)
    assert plan.rhythm_grid == "triplet_hat_grid"


def test_parse_emotional_chords_maps_to_emotional_harmony() -> None:
    parsed = parse_prompt("Give me emotional chords")
    plan = build_midi_plan(parsed)

    assert parsed.pattern_type == "chords"
    assert parsed.primary_mood == "emotional"
    assert isinstance(plan.engine_config, ChordProgressionConfig)
    assert plan.chord_degrees == (1, 6, 4, 5)
    assert plan.contour_rule == "wide_leap_slow_contour"


def test_empty_prompt_uses_deterministic_default_melody() -> None:
    parsed = parse_prompt("")
    plan = build_midi_plan(parsed)

    assert parsed.tempo_bpm == 120
    assert parsed.key == "C"
    assert parsed.mode == "minor"
    assert parsed.pattern_type == "melody"
    assert parsed.density == "medium"
    assert parsed.complexity == "moderate"
    assert isinstance(plan.engine_config, MelodyConfig)
    assert plan.engine_config.notes_per_bar == 8


def test_mood_mapping_dark_lowers_melody_root_and_forces_minor_scale() -> None:
    parsed = parse_prompt("happy dark melody in C major")
    plan = build_midi_plan(parsed)

    assert parsed.mood_modifiers == ("dark", "happy")
    assert parsed.primary_mood == "dark"
    assert parsed.mode == "minor"
    assert isinstance(plan.engine_config, MelodyConfig)
    assert plan.engine_config.root_pitch == 48
    assert plan.contour_rule == "low_narrow_minor_contour"


def test_genre_mapping_trap_and_drill_set_distinct_rhythm_grids() -> None:
    trap = build_midi_plan(parse_prompt("trap melody"))
    drill = build_midi_plan(parse_prompt("drill melody"))

    assert trap.rhythm_grid == "eighth_hat_grid"
    assert drill.rhythm_grid == "triplet_hat_grid"
    assert isinstance(drill.engine_config, MelodyConfig)
    assert drill.engine_config.notes_per_bar == 12


def test_density_mapping_changes_melody_note_count() -> None:
    sparse = build_midi_plan(parse_prompt("sparse melody"))
    dense = build_midi_plan(parse_prompt("dense melody"))

    assert isinstance(sparse.engine_config, MelodyConfig)
    assert isinstance(dense.engine_config, MelodyConfig)
    assert sparse.engine_config.notes_per_bar == 4
    assert dense.engine_config.notes_per_bar == 12


def test_bouncy_bassline_maps_to_bass_config_and_offbeat_grid() -> None:
    parsed = parse_prompt("Make a bouncy bassline in G minor")
    plan = build_midi_plan(parsed)

    assert parsed.pattern_type == "bassline"
    assert parsed.key == "G"
    assert parsed.primary_mood == "bouncy"
    assert isinstance(plan.engine_config, BasslineConfig)
    assert plan.engine_config.root_pitch == 43
    assert plan.rhythm_grid == "offbeat_eighth_grid"


def test_dreamy_pad_progression_defaults_to_90_bpm_chords() -> None:
    parsed = parse_prompt("Create a dreamy pad progression at 90 BPM")
    plan = build_midi_plan(parsed)

    assert parsed.tempo_bpm == 90
    assert parsed.pattern_type == "chords"
    assert parsed.primary_mood == "dreamy"
    assert isinstance(plan.engine_config, ChordProgressionConfig)
    assert plan.engine_config.root_pitch == 60
    assert plan.chord_degrees == (1, 4, 2, 5)


def test_same_prompt_and_seed_render_identical_midi_bytes() -> None:
    first = generate_prompt_midi("dark trap melody at 140 bpm in D minor", seed=12)
    second = generate_prompt_midi("dark trap melody at 140 bpm in D minor", seed=12)

    assert first.midi_bytes == second.midi_bytes
    assert first.tracks == second.tracks


def test_different_prompts_produce_structurally_different_patterns() -> None:
    melody = generate_prompt_midi("dark trap melody at 140 bpm", seed=7)
    drums = generate_prompt_midi("uk drill drums", seed=7)

    assert melody.tracks[0].role == "melody"
    assert drums.tracks[0].role == "drums"
    assert melody.tracks[0].patterns[0].ordered_notes != drums.tracks[0].patterns[0].ordered_notes


def test_prompt_midi_render_returns_valid_midi_structure() -> None:
    result = generate_prompt_midi("emotional chords in F# minor", seed=3)

    assert result.midi_bytes.startswith(b"MThd")
    assert result.midi_bytes.count(b"MTrk") == 2
    assert result.midi_bytes.endswith(b"\x00\xff\x2f\x00")


def test_unsupported_keywords_are_ignored_safely() -> None:
    parsed = parse_prompt("make a crystalline volcano melody with impossible sauce")
    plan = build_midi_plan(parsed)

    assert parsed.pattern_type == "melody"
    assert parsed.tempo_bpm == 120
    assert parsed.rhythm_style == "none"
    assert isinstance(plan.engine_config, MelodyConfig)

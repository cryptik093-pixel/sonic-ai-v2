from app.audio.midi_generation import (
    DrumPatternConfig,
    MelodyConfig,
    MIDIEngine,
    Note,
    Pattern,
    Track,
    render_to_midi,
    tracks_to_midi_bytes,
)


def test_melody_generation_is_deterministic_with_seed() -> None:
    engine = MIDIEngine()
    config = MelodyConfig(tempo_bpm=92, bars=2, root_pitch=62, scale="minor")

    first = engine.generate_melody(config, seed=1234)
    second = engine.generate_melody(config, seed=1234)

    assert first == second
    assert first.role == "melody"
    assert len(first.patterns[0].ordered_notes) == config.bars * config.notes_per_bar


def test_different_seed_can_change_seeded_melody() -> None:
    engine = MIDIEngine()
    config = MelodyConfig(tempo_bpm=92, bars=2, root_pitch=62, scale="minor")

    first_notes = engine.generate_melody(config, seed=1).patterns[0].ordered_notes
    second_notes = engine.generate_melody(config, seed=2).patterns[0].ordered_notes

    assert first_notes != second_notes


def test_melody_notes_follow_expected_grid_and_bar_length() -> None:
    engine = MIDIEngine()

    track = engine.generate_melody(
        MelodyConfig(tempo_bpm=120, bars=1, notes_per_bar=8, root_pitch=60),
    )
    pattern = track.patterns[0]

    assert pattern.length_beats == 4.0
    assert [note.start_time for note in pattern.ordered_notes] == [
        0.0,
        0.5,
        1.0,
        1.5,
        2.0,
        2.5,
        3.0,
        3.5,
    ]
    assert all(0 <= note.pitch <= 127 for note in pattern.ordered_notes)
    assert all(
        note.start_time + note.duration <= pattern.length_beats for note in pattern.ordered_notes
    )


def test_drum_pattern_uses_basic_four_four_grid() -> None:
    engine = MIDIEngine()

    track = engine.generate_drum_pattern(DrumPatternConfig(tempo_bpm=100, bars=1))
    notes_by_pitch = _starts_by_pitch(track.patterns[0].ordered_notes)

    assert track.role == "drums"
    assert notes_by_pitch[36] == [0.0, 2.0]
    assert notes_by_pitch[38] == [1.0, 3.0]
    assert notes_by_pitch[42] == [0.0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
    assert all(note.channel == 9 for note in track.patterns[0].ordered_notes)


def test_seeded_drum_pattern_is_deterministic() -> None:
    engine = MIDIEngine()
    config = DrumPatternConfig(tempo_bpm=100, bars=2, velocity=90)

    first = engine.generate_drum_pattern(config, seed=99)
    second = engine.generate_drum_pattern(config, seed=99)

    assert first.patterns[0].ordered_notes == second.patterns[0].ordered_notes


def test_bassline_and_chords_are_available_internal_generators() -> None:
    engine = MIDIEngine()

    bass = engine.generate_bassline({"tempo_bpm": 110, "bars": 2, "root_pitch": 36})
    chords = engine.generate_chord_progression({"tempo_bpm": 110, "bars": 4, "root_pitch": 48})

    assert bass.role == "bass"
    assert chords.role == "chords"
    assert bass.patterns[0].length_beats == 8.0
    assert chords.patterns[0].length_beats == 16.0
    assert len(chords.patterns[0].ordered_notes) == 12


def test_bassline_and_chords_respect_bar_length_and_grid() -> None:
    engine = MIDIEngine()

    bass = engine.generate_bassline({"tempo_bpm": 110, "bars": 2, "root_pitch": 36}, seed=7)
    chords = engine.generate_chord_progression({"tempo_bpm": 110, "bars": 2, "root_pitch": 48})

    assert bass.patterns[0].tempo == 110
    assert [note.start_time for note in bass.patterns[0].ordered_notes] == [
        0.0,
        2.0,
        3.0,
        4.0,
        6.0,
        7.0,
    ]
    assert all(note.start_time % 1.0 == 0 for note in chords.patterns[0].ordered_notes)
    assert all(note.start_time + note.duration <= 8.0 for note in chords.patterns[0].ordered_notes)


def test_pattern_stores_notes_in_deterministic_order() -> None:
    pattern = Pattern(
        notes=(
            Note(pitch=67, velocity=90, start_time=1.0, duration=1.0),
            Note(pitch=60, velocity=90, start_time=0.0, duration=1.0),
            Note(pitch=64, velocity=90, start_time=1.0, duration=1.0),
        ),
        tempo_bpm=120,
        length_beats=2.0,
    )

    assert [note.pitch for note in pattern.notes] == [60, 64, 67]
    assert pattern.ordered_notes == pattern.notes


def test_note_accepts_midi_zero_velocity() -> None:
    note = Note(pitch=60, velocity=0, start_time=0.0, duration=1.0)

    assert note.velocity == 0


def test_tracks_to_midi_bytes_returns_structurally_valid_midi() -> None:
    pattern = Pattern(
        notes=(
            Note(pitch=60, velocity=90, start_time=0.0, duration=1.0),
            Note(pitch=64, velocity=90, start_time=1.0, duration=1.0),
        ),
        tempo_bpm=120,
        length_beats=2.0,
    )
    track = Track(name="Unit Test", role="melody", patterns=(pattern,))

    midi_bytes = tracks_to_midi_bytes(track)

    assert len(midi_bytes) > 32
    assert midi_bytes.startswith(b"MThd")
    assert midi_bytes[8:10] == (1).to_bytes(2, "big")
    assert midi_bytes[10:12] == (2).to_bytes(2, "big")
    assert midi_bytes.count(b"MTrk") == 2
    assert midi_bytes.endswith(b"\x00\xff\x2f\x00")


def test_render_to_midi_returns_structurally_valid_midi() -> None:
    engine = MIDIEngine()
    tracks = (
        engine.generate_melody(MelodyConfig(tempo_bpm=120, bars=1), seed=3),
        engine.generate_drum_pattern(DrumPatternConfig(tempo_bpm=120, bars=1), seed=3),
    )

    midi_bytes = render_to_midi(tracks)

    assert len(midi_bytes) > 32
    assert midi_bytes.startswith(b"MThd")
    assert midi_bytes.count(b"MTrk") == 3


def _starts_by_pitch(notes: tuple[Note, ...]) -> dict[int, list[float]]:
    starts: dict[int, list[float]] = {}
    for note in notes:
        starts.setdefault(note.pitch, []).append(note.start_time)
    return starts

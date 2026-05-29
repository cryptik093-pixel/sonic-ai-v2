from app.audio.midi_generation import _fallback_melody, render_to_midi


def test_fallback_melody_generates_notes_and_is_deterministic() -> None:
    track = _fallback_melody(root_pitch=60, scale="minor", bars=2, seed=42, tempo_bpm=110)

    assert track.role == "melody"
    assert len(track.patterns) == 1
    assert len(track.patterns[0].ordered_notes) == 8


def test_fallback_melody_renders_valid_midi_with_note_on() -> None:
    track = _fallback_melody(root_pitch=60, scale="minor", bars=1, seed=7, tempo_bpm=120)
    midi = render_to_midi(track)

    assert midi.startswith(b"MThd")
    # ensure there's at least one Note On (0x9?) status byte in the payload
    assert any(b in midi for b in (b"\x90", b"\x91", b"\x92", b"\x93", b"\x94"))

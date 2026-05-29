from app.api.audio.prompt_to_midi import generate_prompt_midi


def test_generate_prompt_midi_bytes():
    """Smoke test: generation returns non-empty Standard MIDI File bytes (MThd header)."""
    result = generate_prompt_midi("dark trap melody at 140 bpm in D minor", seed=42)
    midi_bytes = result.midi_bytes
    assert midi_bytes, "MIDI bytes should not be empty"
    # Standard MIDI header
    assert midi_bytes[:4] == b"MThd"

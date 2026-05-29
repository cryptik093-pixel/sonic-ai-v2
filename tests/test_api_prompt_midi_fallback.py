import base64

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract_note_on_events(midi_bytes: bytes) -> int:
    """Count Note-On events (0x9x) in raw MIDI bytes."""
    return sum(1 for b in midi_bytes if (b & 0xF0) == 0x90)


def test_prompt_midi_fallback_binary():
    """
    Ensures that even if the internal generator produces zero notes,
    the API still returns a valid, non-silent MIDI file via fallback.
    """
    resp = client.post(
        "/api/v2/prompt-midi",
        data={"prompt": "generate absolutely nothing"},
    )
    assert resp.status_code == 200

    midi_bytes = resp.content
    assert midi_bytes.startswith(b"MThd")
    assert len(midi_bytes) > 200

    note_on_count = extract_note_on_events(midi_bytes)
    assert note_on_count > 0


def test_prompt_midi_fallback_json():
    """
    Same as above, but for JSON mode.
    Ensures the fallback melody is encoded and returned correctly.
    """
    resp = client.post(
        "/api/v2/prompt-midi?format=json",
        data={"prompt": "generate absolutely nothing"},
    )
    assert resp.status_code == 200

    payload = resp.json()
    assert payload["status"] == "completed"
    assert "midi" in payload
    assert payload["midi"]["encoding"] == "base64"

    midi_bytes = base64.b64decode(payload["midi"]["data_base64"])
    assert midi_bytes.startswith(b"MThd")
    assert len(midi_bytes) > 200

    note_on_count = extract_note_on_events(midi_bytes)
    assert note_on_count > 0

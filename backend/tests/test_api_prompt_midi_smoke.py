import base64

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


CANONICAL_PROMPTS = [
    "dark trap melody at 140 bpm in D minor",
    "emotional chord progression at 92 bpm in F# minor",
    "bouncy melody in C major",
]


def _has_note_on(midi_bytes: bytes) -> bool:
    # Search for any MIDI status byte in the Note On range (0x90-0x9F)
    return any((b & 0xF0) == 0x90 for b in midi_bytes)


def test_prompt_midi_returns_nonempty_midi_and_contain_note_on():
    for prompt in CANONICAL_PROMPTS:
        resp = client.post("/api/v2/prompt-midi", json={"prompt": prompt, "seed": 12})
        assert resp.status_code == 200
        midi_bytes = resp.content
        assert midi_bytes.startswith(b"MThd")
        assert len(midi_bytes) > 100
        assert _has_note_on(midi_bytes)


def test_prompt_midi_json_format_returns_valid_base64_midi_and_contains_notes():
    for prompt in CANONICAL_PROMPTS:
        resp = client.post("/api/v2/prompt-midi?format=json", json={"prompt": prompt, "seed": 12})
        assert resp.status_code == 200
        data = resp.json()
        # Expect canonical structure with data under ['midi']['data_base64']
        assert "midi" in data
        b64 = data["midi"]["data_base64"]
        midi_bytes = base64.b64decode(b64)
        assert midi_bytes.startswith(b"MThd")
        assert _has_note_on(midi_bytes)


def test_prompt_midi_download_endpoint_returns_midi():
    prompt = CANONICAL_PROMPTS[0]
    resp = client.post("/api/v2/prompt-midi/download", json={"prompt": prompt, "seed": 7})
    assert resp.status_code == 200
    assert resp.content.startswith(b"MThd")
    assert _has_note_on(resp.content)

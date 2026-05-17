import base64

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_prompt_midi_returns_midi_for_valid_prompt() -> None:
    response = client.post(
        "/api/v2/prompt-midi",
        json={"prompt": "dark trap melody at 140 bpm in D minor", "seed": 42},
    )

    assert response.status_code == 200
    assert response.content.startswith(b"MThd")
    assert response.headers["x-prompt"] == "dark trap melody at 140 bpm in D minor"
    assert response.headers["x-seed"] == "42"
    assert response.headers["x-key"] == "D"
    assert response.headers["x-mode"] == "minor"


def test_prompt_midi_rejects_empty_prompt() -> None:
    response = client.post("/api/v2/prompt-midi", json={"prompt": "   "})

    assert response.status_code == 400
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "empty_prompt",
            "message": "Prompt must not be empty.",
        },
    }


def test_prompt_midi_content_type_is_audio_midi() -> None:
    response = client.post(
        "/api/v2/prompt-midi",
        json={"prompt": "emotional chords in F# minor", "seed": 3},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/midi")


def test_prompt_midi_same_prompt_and_seed_returns_identical_bytes() -> None:
    payload = {"prompt": "dark trap melody at 140 bpm in D minor", "seed": 12}

    first = client.post("/api/v2/prompt-midi", json=payload)
    second = client.post("/api/v2/prompt-midi", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content == second.content


def test_prompt_midi_different_seeds_return_different_bytes() -> None:
    prompt = "dark trap melody at 140 bpm in D minor"

    first = client.post("/api/v2/prompt-midi", json={"prompt": prompt, "seed": 12})
    second = client.post("/api/v2/prompt-midi", json={"prompt": prompt, "seed": 13})

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.content != second.content


def test_prompt_midi_json_format_returns_base64_and_metadata() -> None:
    payload = {"prompt": "dark trap melody at 140 bpm in D minor", "seed": 12}
    response = client.post("/api/v2/prompt-midi?format=json", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "completed"
    assert "prompt" in data and "midi" in data
    assert data["prompt"]["seed"] == 12
    assert data["midi"]["encoding"] == "base64"

    midi_bytes = base64.b64decode(data["midi"]["data_base64"])
    assert midi_bytes.startswith(b"MThd")


def test_prompt_midi_json() -> None:
    resp = client.post(
        "/api/v2/prompt-midi",
        data={"prompt": "simple melody", "format": "json"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "midi_base64" in data
    assert len(data["midi_base64"]) > 10

    midi_bytes = base64.b64decode(data["midi_base64"])
    assert midi_bytes.startswith(b"MThd")


def test_prompt_midi_download() -> None:
    resp = client.post(
        "/api/v2/prompt-midi/download",
        data={"prompt": "simple melody"},
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "audio/midi"
    assert "Content-Disposition" in resp.headers

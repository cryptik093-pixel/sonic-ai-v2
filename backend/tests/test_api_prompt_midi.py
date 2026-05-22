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

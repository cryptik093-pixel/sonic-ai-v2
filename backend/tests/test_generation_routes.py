import base64

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_prompt_midi_returns_json_with_base64_midi_when_requested() -> None:
    response = client.post(
        "/api/v2/prompt-midi",
        json={"prompt": "dark trap melody at 140 bpm in D minor", "seed": 12},
        headers={"Accept": "application/json"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()
    midi_bytes = base64.b64decode(body["midi"]["data_base64"])

    assert body["status"] == "completed"
    assert body["prompt"]["raw"] == "dark trap melody at 140 bpm in D minor"
    assert body["prompt"]["seed"] == 12
    assert body["prompt"]["tempo_bpm"] == 140
    assert body["prompt"]["key"] == "D"
    assert body["prompt"]["mode"] == "minor"
    assert body["prompt"]["pattern_type"] == "melody"
    assert body["prompt"]["rhythm_style"] == "trap"
    assert body["midi"]["media_type"] == "audio/midi"
    assert body["midi"]["encoding"] == "base64"
    assert body["midi"]["byte_length"] == len(midi_bytes)
    assert midi_bytes.startswith(b"MThd")


def test_prompt_midi_rejects_blank_prompt_with_json_error() -> None:
    response = client.post("/api/v2/prompt-midi", json={"prompt": "   "})

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "empty_prompt",
            "message": "Prompt must not be empty.",
        },
    }


def test_prompt_midi_openapi_uses_valid_request_examples() -> None:
    schema = app.openapi()
    request_schema = schema["components"]["schemas"]["PromptMIDIRequest"]

    assert request_schema["examples"][0] == {
        "prompt": "dark trap melody at 140 bpm in D minor",
        "seed": 12,
    }
    assert request_schema["properties"]["prompt"]["examples"] == [
        "dark trap melody at 140 bpm in D minor"
    ]
    assert request_schema["properties"]["seed"]["examples"] == [12]

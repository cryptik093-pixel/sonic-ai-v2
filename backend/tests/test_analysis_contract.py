from io import BytesIO

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import app

client = TestClient(app)


def test_analyze_with_generated_wav_returns_completed_analysis() -> None:
    response = client.post(
        "/api/v2/analyze",
        files={"file": ("generated.wav", _wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")

    body = response.json()
    assert body["status"] == "completed"
    assert body["analysis"]["engine_version"] == "sonic-ai-v2-analysis-core-0.1.0"
    assert body["analysis"]["filename"] == "generated.wav"
    assert "integrated_lufs" in body["analysis"]["metrics"]
    assert "true_peak_dbfs" in body["analysis"]["metrics"]
    assert "overall_severity" in body["analysis"]["reference_comparison"]
    assert isinstance(body["analysis"]["engineering_report"], dict)
    assert set(body["analysis"]["engineering_report"]) == {
        "summary",
        "scorecard",
        "priority_moves",
        "mastering_chain",
        "mix_translation",
        "warnings",
        "export_layout",
        "metadata",
    }


def test_analyze_target_profile_can_be_set_to_streaming_balanced() -> None:
    response = client.post(
        "/api/v2/analyze",
        data={"target_profile": "streaming_balanced"},
        files={"file": ("generated.wav", _wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["analysis"]["profile_id"] == "streaming_balanced"
    assert body["analysis"]["reference_comparison"]["profile_id"] == "streaming_balanced"


def test_analyze_target_profile_can_be_set_by_query_param() -> None:
    response = client.post(
        "/api/v2/analyze?target_profile=streaming_balanced",
        files={"file": ("generated.wav", _wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    assert response.json()["analysis"]["profile_id"] == "streaming_balanced"


def test_unknown_target_profile_returns_400_json_error() -> None:
    response = client.post(
        "/api/v2/analyze",
        data={"target_profile": "unknown"},
        files={"file": ("generated.wav", _wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "unknown_target_profile",
            "message": "Unknown reference profile: 'unknown'.",
        },
    }


def test_unknown_target_profile_is_rejected_before_audio_decode() -> None:
    response = client.post(
        "/api/v2/analyze",
        data={"target_profile": "MIX_MASTER"},
        files={"file": ("corrupt.wav", b"not a valid wav", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "unknown_target_profile",
            "message": "Unknown reference profile: 'MIX_MASTER'.",
        },
    }


def test_unsupported_file_extension_returns_400_json_error() -> None:
    response = client.post(
        "/api/v2/analyze",
        files={"file": ("generated.txt", b"not audio", "text/plain")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "unsupported_audio_format"


def test_empty_file_returns_400_json_error() -> None:
    response = client.post(
        "/api/v2/analyze",
        files={"file": ("empty.wav", b"", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "empty_file",
            "message": "Uploaded audio file is empty.",
        },
    }


def test_oversized_file_returns_413_json_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SONIC_AI_MAX_UPLOAD_BYTES", "8")
    get_settings.cache_clear()

    response = client.post(
        "/api/v2/analyze",
        files={"file": ("too-large.wav", b"123456789", "audio/wav")},
    )
    get_settings.cache_clear()

    assert response.status_code == 413
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "file_too_large"
    assert body["error"]["message"] == "Uploaded audio file exceeds the 8 byte limit."


def test_corrupt_wav_returns_400_json_error() -> None:
    response = client.post(
        "/api/v2/analyze",
        files={"file": ("corrupt.wav", b"not a valid wav", "audio/wav")},
    )

    assert response.status_code == 400
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["status"] == "error"
    assert body["error"]["code"] == "audio_load_failed"
    assert "could not be loaded" in body["error"]["message"]


def test_missing_file_returns_json_error() -> None:
    response = client.post("/api/v2/analyze")

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "invalid_request",
            "message": "Request validation failed.",
        },
    }


def test_unknown_api_route_returns_json_error_envelope() -> None:
    response = client.get("/api/v2/does-not-exist")

    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "not_found",
            "message": "Not Found",
        },
    }


def test_wrong_method_returns_json_error_envelope() -> None:
    response = client.get("/api/v2/analyze")

    assert response.status_code == 405
    assert response.headers["content-type"].startswith("application/json")
    assert response.json() == {
        "status": "error",
        "error": {
            "code": "method_not_allowed",
            "message": "Method Not Allowed",
        },
    }


def test_analyze_openapi_exposes_valid_target_profile_options() -> None:
    schema = app.openapi()
    analyze_operation = schema["paths"]["/api/v2/analyze"]["post"]
    query_profile = next(
        parameter
        for parameter in analyze_operation["parameters"]
        if parameter["name"] == "target_profile"
    )
    form_schema_ref = analyze_operation["requestBody"]["content"]["multipart/form-data"][
        "schema"
    ]["$ref"]
    form_schema_name = form_schema_ref.rsplit("/", 1)[-1]
    form_profile = schema["components"]["schemas"][form_schema_name]["properties"][
        "target_profile"
    ]

    assert query_profile["schema"]["enum"] == [
        "modern_hiphop_master",
        "streaming_balanced",
        "club_trap_master",
    ]
    assert form_profile["enum"] == [
        "modern_hiphop_master",
        "streaming_balanced",
        "club_trap_master",
    ]
    assert "Valid values" in query_profile["description"]


def _wav_bytes() -> bytes:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.25 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32)
    buffer = BytesIO()
    sf.write(buffer, samples, sample_rate_hz, format="WAV")
    return buffer.getvalue()

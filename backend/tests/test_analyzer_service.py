from dataclasses import is_dataclass
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.audio.loader import LoadedAudio
from app.audio.metrics import AudioMetrics
from app.audio.reference_profiles import ReferenceComparison
from app.services.analyzer_service import (
    ENGINE_VERSION,
    AnalysisServiceError,
    AnalyzerService,
    SonicAnalysisResult,
    analysis_result_to_dict,
)


def _loaded_audio(samples: np.ndarray, sample_rate_hz: int = 48_000) -> LoadedAudio:
    samples = np.asarray(samples, dtype=np.float32)
    frames = int(samples.shape[0])
    channels = int(samples.shape[1])
    return LoadedAudio(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        frames=frames,
        duration_seconds=float(frames / sample_rate_hz),
        peak_abs=float(np.max(np.abs(samples))),
        filename="generated.wav",
    )


def _sine_audio() -> LoadedAudio:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.25 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32).reshape(-1, 1)
    return _loaded_audio(samples=samples, sample_rate_hz=sample_rate_hz)


def test_analyze_loaded_audio_returns_sonic_analysis_result() -> None:
    result = AnalyzerService().analyze_loaded_audio(_sine_audio())

    assert isinstance(result, SonicAnalysisResult)
    assert is_dataclass(result)
    assert result.engine_version == ENGINE_VERSION
    assert result.filename == "generated.wav"
    assert result.profile_id == "modern_hiphop_master"


def test_analyze_loaded_audio_calculates_metrics_from_generated_signal() -> None:
    result = AnalyzerService().analyze_loaded_audio(_sine_audio())

    assert isinstance(result.metrics, AudioMetrics)
    assert result.metrics.sample_rate_hz == 48_000
    assert result.metrics.channels == 1
    assert result.metrics.frames == 48_000
    assert result.metrics.peak_abs == pytest.approx(0.25, rel=0.02)
    assert result.metrics.rms > 0.0


def test_analyze_loaded_audio_includes_reference_comparison() -> None:
    result = AnalyzerService().analyze_loaded_audio(_sine_audio())

    assert isinstance(result.reference_comparison, ReferenceComparison)
    assert result.reference_comparison.profile_id == "modern_hiphop_master"
    assert result.reference_comparison.deltas


def test_analyze_file_path_works_on_generated_temporary_wav(tmp_path: Path) -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.2 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
    path = tmp_path / "temporary.wav"
    sf.write(path, samples, sample_rate_hz)

    result = AnalyzerService().analyze_file_path(path)

    assert isinstance(result, SonicAnalysisResult)
    assert result.filename == "temporary.wav"
    assert result.metrics.channels == 1
    assert result.reference_comparison.profile_id == "modern_hiphop_master"


def test_unknown_profile_raises_clear_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown reference profile"):
        AnalyzerService().analyze_loaded_audio(_sine_audio(), profile_id="unknown")


def test_invalid_loaded_audio_type_raises_service_error() -> None:
    with pytest.raises(AnalysisServiceError, match="LoadedAudio"):
        AnalyzerService().analyze_loaded_audio("not audio")  # type: ignore[arg-type]


def test_serialization_returns_plain_dict_values() -> None:
    result = AnalyzerService().analyze_loaded_audio(_sine_audio())
    serialized = analysis_result_to_dict(result)

    assert isinstance(serialized, dict)
    assert serialized["engine_version"] == ENGINE_VERSION
    assert serialized["filename"] == "generated.wav"
    assert serialized["profile_id"] == "modern_hiphop_master"
    assert isinstance(serialized["metrics"], dict)
    assert isinstance(serialized["reference_comparison"], dict)
    _assert_plain_serializable(serialized)


def _assert_plain_serializable(value: object) -> None:
    if isinstance(value, dict):
        for item in value.values():
            _assert_plain_serializable(item)
        return
    if isinstance(value, list):
        for item in value:
            _assert_plain_serializable(item)
        return
    assert value is None or isinstance(value, str | int | float | bool)

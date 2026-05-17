import numpy as np
import pytest

from app.audio.loader import LoadedAudio
from app.audio.metrics import calculate_basic_metrics


def _audio(samples: np.ndarray, sample_rate_hz: int = 48_000) -> LoadedAudio:
    samples = np.asarray(samples, dtype=np.float32)
    frames = int(samples.shape[0]) if samples.ndim >= 1 else 0
    channels = int(samples.shape[1]) if samples.ndim == 2 else 0
    return LoadedAudio(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        frames=frames,
        duration_seconds=float(frames / sample_rate_hz) if sample_rate_hz > 0 else 0.0,
        peak_abs=float(np.max(np.abs(samples))) if samples.size else 0.0,
        filename="generated.wav",
    )


def test_silence_returns_safe_floor_and_no_clipping() -> None:
    metrics = calculate_basic_metrics(_audio(np.zeros((8, 1), dtype=np.float32)))

    assert metrics.rms == 0.0
    assert metrics.peak_abs == 0.0
    assert metrics.peak_dbfs == -120.0
    assert metrics.integrated_lufs == -120.0
    assert metrics.short_term_lufs == -120.0
    assert metrics.true_peak_abs == 0.0
    assert metrics.true_peak_dbfs == -120.0
    assert metrics.rms_dbfs == -120.0
    assert metrics.crest_factor == 0.0
    assert metrics.crest_factor_db == 0.0
    assert metrics.dynamic_range_db == 0.0
    assert metrics.clipping_sample_count == 0
    assert metrics.clipping_ratio == 0.0
    assert metrics.clipping_risk == "none"
    assert metrics.loudness_profile == "silent"
    assert metrics.true_peak_risk == "none"
    assert metrics.stereo_balance == 0.0
    assert metrics.stereo_correlation == 1.0
    assert metrics.side_energy == 0.0
    assert metrics.side_energy_ratio == 0.0
    assert metrics.stereo_width == 0.0
    assert metrics.stereo_profile == "mono"
    assert metrics.spectral_centroid_hz == 0.0
    assert metrics.sub_band_ratio == 0.0
    assert metrics.low_band_ratio == 0.0
    assert metrics.mid_band_ratio == 0.0
    assert metrics.high_band_ratio == 0.0
    assert metrics.harsh_band_ratio == 0.0
    assert metrics.bass_band_ratio == 0.0
    assert metrics.low_mid_band_ratio == 0.0
    assert metrics.high_mid_band_ratio == 0.0
    assert metrics.low_end_profile == "silent"
    assert metrics.harshness_profile == "silent"


def test_constant_half_scale_signal_returns_expected_peak_and_rms() -> None:
    metrics = calculate_basic_metrics(_audio(np.full((8, 1), 0.5, dtype=np.float32)))

    assert metrics.peak_abs == pytest.approx(0.5)
    assert metrics.peak_dbfs == pytest.approx(-6.020599913)
    assert metrics.rms == pytest.approx(0.5)
    assert metrics.rms_dbfs == pytest.approx(-6.020599913)
    assert metrics.crest_factor == pytest.approx(1.0)
    assert metrics.crest_factor_db == pytest.approx(0.0)
    assert metrics.clipping_risk == "none"


def test_clipped_signal_returns_high_clipping_risk() -> None:
    samples = np.zeros((1_000, 1), dtype=np.float32)
    samples[:2, 0] = 1.0

    metrics = calculate_basic_metrics(_audio(samples))

    assert metrics.clipping_sample_count == 2
    assert metrics.clipping_ratio == pytest.approx(0.002)
    assert metrics.clipping_risk == "high"


def test_invalid_sample_shape_raises_value_error() -> None:
    with pytest.raises(ValueError, match="samples must be a 2D array"):
        calculate_basic_metrics(_audio(np.zeros(8, dtype=np.float32)))


def test_stereo_signal_calculates_across_all_samples() -> None:
    samples = np.array(
        [
            [0.0, 0.5],
            [-0.5, 0.0],
        ],
        dtype=np.float32,
    )

    metrics = calculate_basic_metrics(_audio(samples))

    assert metrics.channels == 2
    assert metrics.frames == 2
    assert metrics.peak_abs == pytest.approx(0.5)
    assert metrics.rms == pytest.approx(np.sqrt(0.125))
    assert metrics.crest_factor == pytest.approx(0.5 / np.sqrt(0.125))


def test_moderate_sine_wave_returns_finite_loudness_and_true_peak() -> None:
    sample_rate_hz = 48_000
    seconds = 1.0
    t = np.arange(int(sample_rate_hz * seconds), dtype=np.float64) / sample_rate_hz
    samples = (0.25 * np.sin(2.0 * np.pi * 440.0 * t)).astype(np.float32).reshape(-1, 1)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert np.isfinite(metrics.integrated_lufs)
    assert np.isfinite(metrics.short_term_lufs)
    assert np.isfinite(metrics.true_peak_abs)
    assert np.isfinite(metrics.true_peak_dbfs)
    assert metrics.integrated_lufs > -120.0
    assert metrics.short_term_lufs > -120.0
    assert metrics.true_peak_abs == pytest.approx(0.25, rel=0.02)
    assert metrics.true_peak_dbfs == pytest.approx(-12.041199826, abs=0.25)
    assert metrics.true_peak_risk == "none"


def test_near_ceiling_signal_returns_watch_or_high_true_peak_risk() -> None:
    samples = np.full((48_000, 1), 0.99, dtype=np.float32)

    metrics = calculate_basic_metrics(_audio(samples))

    assert metrics.true_peak_abs == pytest.approx(0.99, rel=0.02)
    assert metrics.true_peak_risk in {"watch", "high"}


def test_no_returned_audio_metrics_field_is_nan_or_inf() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.1 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32).reshape(-1, 1)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    for value in metrics.__dict__.values():
        if isinstance(value, float):
            assert np.isfinite(value)


def test_stereo_identical_left_right_returns_high_correlation_and_low_side_energy() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    mono = 0.25 * np.sin(2.0 * np.pi * 440.0 * t)
    samples = np.column_stack([mono, mono]).astype(np.float32)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert metrics.stereo_balance == pytest.approx(0.0)
    assert metrics.stereo_correlation == pytest.approx(1.0)
    assert metrics.side_energy == pytest.approx(0.0)
    assert metrics.side_energy_ratio == pytest.approx(0.0)
    assert metrics.stereo_width == pytest.approx(0.0)
    assert metrics.stereo_profile == "centered"


def test_stereo_opposite_polarity_returns_high_side_energy_ratio() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    left = 0.25 * np.sin(2.0 * np.pi * 440.0 * t)
    right = -left
    samples = np.column_stack([left, right]).astype(np.float32)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert metrics.stereo_correlation == pytest.approx(-1.0)
    assert metrics.mid_energy == pytest.approx(0.0)
    assert metrics.side_energy_ratio == pytest.approx(1.0)
    assert metrics.stereo_width == pytest.approx(1.0)
    assert metrics.stereo_profile == "very_wide"


def test_low_frequency_sine_has_more_low_end_than_high_band_energy() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.25 * np.sin(2.0 * np.pi * 50.0 * t)).astype(np.float32).reshape(-1, 1)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert metrics.sub_band_ratio + metrics.low_band_ratio > metrics.high_band_ratio
    assert metrics.sub_band_ratio > 0.90
    assert metrics.bass_band_ratio == pytest.approx(metrics.low_band_ratio)
    assert metrics.low_end_profile == "heavy"


def test_high_frequency_sine_has_more_high_and_harsh_energy_than_low_band() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz, dtype=np.float64) / sample_rate_hz
    samples = (0.25 * np.sin(2.0 * np.pi * 5_000.0 * t)).astype(np.float32).reshape(-1, 1)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert metrics.high_band_ratio > metrics.low_band_ratio
    assert metrics.harsh_band_ratio > metrics.low_band_ratio
    assert metrics.high_mid_band_ratio > metrics.low_mid_band_ratio
    assert metrics.harsh_band_ratio > 0.90
    assert metrics.harshness_profile == "harsh"


def test_level_change_over_time_returns_positive_dynamic_range() -> None:
    sample_rate_hz = 48_000
    t = np.arange(sample_rate_hz * 2, dtype=np.float64) / sample_rate_hz
    quiet = 0.05 * np.sin(2.0 * np.pi * 220.0 * t[:sample_rate_hz])
    loud = 0.40 * np.sin(2.0 * np.pi * 220.0 * t[sample_rate_hz:])
    samples = np.concatenate([quiet, loud]).astype(np.float32).reshape(-1, 1)

    metrics = calculate_basic_metrics(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert metrics.dynamic_range_db > 6.0

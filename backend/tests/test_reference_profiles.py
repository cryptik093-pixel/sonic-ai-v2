from dataclasses import asdict, is_dataclass

import numpy as np
import pytest

from app.audio.metrics import AudioMetrics
from app.audio.reference_profiles import (
    MetricDelta,
    compare_metrics_to_profile,
    get_reference_profile,
    list_reference_profiles,
)


def _metrics(**overrides: float) -> AudioMetrics:
    values = {
        "duration_seconds": 180.0,
        "sample_rate_hz": 48_000,
        "channels": 2,
        "frames": 8_640_000,
        "peak_abs": 0.95,
        "peak_dbfs": -0.45,
        "integrated_lufs": -9.0,
        "short_term_lufs": -8.5,
        "true_peak_abs": 0.92,
        "true_peak_dbfs": -0.8,
        "rms": 0.25,
        "rms_dbfs": -12.0,
        "crest_factor": 3.0,
        "crest_factor_db": 10.0,
        "dynamic_range_db": 6.0,
        "clipping_sample_count": 0,
        "clipping_ratio": 0.0,
        "clipping_risk": "none",
        "stereo_balance": 0.0,
        "stereo_correlation": 0.8,
        "mid_energy": 0.05,
        "side_energy": 0.01,
        "side_energy_ratio": 0.15,
        "stereo_width": 0.45,
        "spectral_centroid_hz": 1800.0,
        "low_band_ratio": 0.22,
        "mid_band_ratio": 0.50,
        "high_band_ratio": 0.20,
        "harsh_band_ratio": 0.10,
        "sub_band_ratio": 0.10,
        "bass_band_ratio": 0.22,
        "low_mid_band_ratio": 0.35,
        "high_mid_band_ratio": 0.15,
        "low_end_profile": "balanced",
        "stereo_profile": "centered",
        "harshness_profile": "present",
        "loudness_profile": "loud_master",
        "true_peak_risk": "watch",
    }
    values.update(overrides)
    return AudioMetrics(**values)


def test_list_reference_profiles_returns_expected_profiles() -> None:
    profile_ids = {profile.profile_id for profile in list_reference_profiles()}

    assert profile_ids == {
        "modern_hiphop_master",
        "streaming_balanced",
        "club_trap_master",
    }


def test_get_reference_profile_returns_modern_hiphop_master() -> None:
    profile = get_reference_profile("modern_hiphop_master")

    assert profile.profile_id == "modern_hiphop_master"
    assert profile.display_name == "Modern Hip-Hop Master"
    assert "integrated_lufs" in profile.ranges


def test_unknown_profile_raises_value_error() -> None:
    with pytest.raises(ValueError, match="Unknown reference profile"):
        get_reference_profile("unknown")


def test_metrics_inside_target_range_return_no_overall_severity() -> None:
    comparison = compare_metrics_to_profile(_metrics())

    assert comparison.overall_severity == "none"
    assert comparison.strongest_issues == []
    assert all(delta.severity == "none" for delta in comparison.deltas)


def test_metrics_below_lufs_target_create_below_target_delta() -> None:
    comparison = compare_metrics_to_profile(_metrics(integrated_lufs=-14.0))
    delta = _delta(comparison.deltas, "integrated_lufs")

    assert delta.direction == "below_target"
    assert delta.delta_to_range == pytest.approx(-3.5)
    assert delta.severity == "medium"


def test_metrics_above_harsh_band_ratio_target_create_above_target_delta() -> None:
    comparison = compare_metrics_to_profile(_metrics(harsh_band_ratio=0.30))
    delta = _delta(comparison.deltas, "harsh_band_ratio")

    assert delta.direction == "above_target"
    assert delta.delta_to_range == pytest.approx(0.10)
    assert delta.severity == "medium"


def test_strongest_issues_sort_high_before_medium_before_low() -> None:
    comparison = compare_metrics_to_profile(
        _metrics(
            integrated_lufs=-20.0,
            harsh_band_ratio=0.30,
            low_band_ratio=0.12,
        )
    )

    assert [delta.metric_name for delta in comparison.strongest_issues[:3]] == [
        "integrated_lufs",
        "harsh_band_ratio",
        "low_band_ratio",
    ]
    assert [delta.severity for delta in comparison.strongest_issues[:3]] == [
        "high",
        "medium",
        "low",
    ]


def test_no_returned_numeric_delta_contains_nan_or_inf() -> None:
    comparison = compare_metrics_to_profile(_metrics(integrated_lufs=-14.0))

    for delta in comparison.deltas:
        assert np.isfinite(delta.measured)
        assert np.isfinite(delta.target_min)
        assert np.isfinite(delta.target_max)
        assert np.isfinite(delta.delta_to_range)


def test_comparison_dataclasses_contain_plain_serializable_values() -> None:
    comparison = compare_metrics_to_profile(_metrics(integrated_lufs=-14.0))

    assert is_dataclass(comparison)
    serialized = asdict(comparison)
    _assert_plain_serializable(serialized)


def _delta(deltas: list[MetricDelta], metric_name: str) -> MetricDelta:
    return next(delta for delta in deltas if delta.metric_name == metric_name)


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

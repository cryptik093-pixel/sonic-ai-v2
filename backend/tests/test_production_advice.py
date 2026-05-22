from fastapi.testclient import TestClient

from app.audio.metrics import AudioMetrics
from app.audio.production_advice import (
    EngineeringIssue,
    ProductionAdvice,
    engineering_report_to_dict,
    generate_engineering_issues,
    generate_engineering_report,
    generate_production_advice,
    production_advice_to_dict,
)
from app.audio.reference_profiles import MetricDelta, ReferenceComparison
from app.main import app

client = TestClient(app)


def test_healthy_comparison_returns_one_info_move() -> None:
    advice = generate_production_advice(_metrics(), _comparison(overall_severity="none"))

    assert isinstance(advice, ProductionAdvice)
    assert advice.profile_id == "modern_hiphop_master"
    assert advice.risk_summary == "No major corrective issues detected."
    assert len(advice.moves) == 1
    assert advice.moves[0].id == "profile_alignment_stable"
    assert advice.moves[0].domain == "dynamics"
    assert advice.moves[0].severity == "info"


def test_quiet_signal_below_lufs_target_returns_loudness_move() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("integrated_lufs", -14.0, -10.5, -8.0, -3.5, "below_target", "medium")),
    )

    assert advice.risk_summary == "Moderate production adjustments recommended."
    assert advice.moves[0].id == "increase_integrated_loudness"
    assert advice.moves[0].domain == "loudness"
    assert advice.moves[0].severity == "moderate"


def test_low_sub_band_returns_low_end_move() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("sub_band_ratio", 0.01, 0.04, 0.16, -0.03, "below_target", "low")),
    )

    assert advice.risk_summary == "Minor production adjustments recommended."
    assert advice.moves[0].id == "increase_sub_band_ratio"
    assert advice.moves[0].domain == "low_end"
    assert advice.moves[0].severity == "mild"


def test_excessive_harsh_band_ratio_returns_high_end_move() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("harsh_band_ratio", 0.30, 0.06, 0.20, 0.10, "above_target", "medium")),
    )

    assert advice.moves[0].id == "reduce_harsh_band_ratio"
    assert advice.moves[0].domain == "high_end"
    assert advice.moves[0].severity == "moderate"


def test_narrow_side_energy_ratio_returns_stereo_move() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("side_energy_ratio", 0.02, 0.08, 0.32, -0.06, "below_target", "medium")),
    )

    assert advice.moves[0].id == "increase_side_energy_ratio"
    assert advice.moves[0].domain == "stereo"


def test_low_crest_factor_returns_transients_move() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("crest_factor_db", 3.0, 6.0, 14.0, -3.0, "below_target", "low")),
    )

    assert advice.moves[0].id == "restore_transient_contrast"
    assert advice.moves[0].domain == "transients"
    assert advice.moves[0].severity == "mild"


def test_production_advice_to_dict_returns_json_safe_values() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(_delta("integrated_lufs", -14.0, -10.5, -8.0, -3.5, "below_target", "medium")),
    )

    serialized = production_advice_to_dict(advice)

    assert isinstance(serialized, dict)
    assert serialized["profile_id"] == "modern_hiphop_master"
    assert isinstance(serialized["moves"], list)
    _assert_plain_serializable(serialized)


def test_engineering_rules_detect_low_end_buildup_and_harsh_high_mids() -> None:
    metrics = _metrics(
        sub_band_ratio=0.24,
        bass_band_ratio=0.31,
        low_band_ratio=0.31,
        high_mid_band_ratio=0.40,
    )

    issues = generate_engineering_issues(metrics)

    assert [issue.issue_type for issue in issues][:2] == [
        "harsh_high_mids",
        "low_end_buildup",
    ]
    assert all(isinstance(issue, EngineeringIssue) for issue in issues)
    low_end = next(issue for issue in issues if issue.issue_type == "low_end_buildup")
    assert low_end.severity == "severe"
    assert any("kick and bass" in action for action in low_end.suggested_actions)


def test_engineering_rules_detect_overcompression_and_true_peak_risk() -> None:
    metrics = _metrics(
        true_peak_dbfs=-0.1,
        crest_factor_db=3.5,
        dynamic_range_db=1.5,
    )

    issues = generate_engineering_issues(metrics)

    assert {issue.issue_type for issue in issues} >= {
        "overcompressed",
        "true_peak_too_hot",
    }
    overcompressed = next(issue for issue in issues if issue.issue_type == "overcompressed")
    true_peak = next(issue for issue in issues if issue.issue_type == "true_peak_too_hot")

    assert overcompressed.severity == "severe"
    assert true_peak.severity == "severe"


def test_engineering_rules_detect_stereo_phase_risk() -> None:
    metrics = _metrics(stereo_correlation=-0.25, stereo_width=1.0, side_energy_ratio=0.55)

    issues = generate_engineering_issues(metrics)

    assert "phase_correlation_risk" in {issue.issue_type for issue in issues}
    phase_issue = next(issue for issue in issues if issue.issue_type == "phase_correlation_risk")
    assert phase_issue.severity == "severe"
    assert any("mono" in action for action in phase_issue.suggested_actions)


def test_engineering_report_returns_required_sections_and_structured_issues() -> None:
    metrics = _metrics(true_peak_dbfs=-0.1)
    report = generate_engineering_report(metrics, _comparison())
    serialized = engineering_report_to_dict(report)

    assert set(serialized["sections"]) == {
        "Loudness & Leveling",
        "Dynamics",
        "Frequency Balance",
        "Stereo Image",
        "Technical Issues",
        "Suggested Fixes",
    }
    assert serialized["issues"][0]["issue_type"] == "true_peak_too_hot"
    assert serialized["suggested_fixes"]
    _assert_plain_serializable(serialized)


def test_moves_sort_by_severity_priority_then_domain_and_id() -> None:
    advice = generate_production_advice(
        _metrics(),
        _comparison(
            _delta("low_band_ratio", 0.10, 0.16, 0.34, -0.06, "below_target", "medium"),
            _delta("integrated_lufs", -16.0, -10.5, -8.0, -5.5, "below_target", "high"),
            _delta("side_energy_ratio", 0.02, 0.08, 0.32, -0.06, "below_target", "medium"),
            _delta("crest_factor_db", 3.0, 6.0, 14.0, -3.0, "below_target", "low"),
        ),
    )

    assert [(move.severity, move.domain, move.id) for move in advice.moves] == [
        ("critical", "loudness", "increase_integrated_loudness"),
        ("moderate", "low_end", "increase_low_band_ratio"),
        ("moderate", "stereo", "increase_side_energy_ratio"),
        ("mild", "transients", "restore_transient_contrast"),
    ]
    assert advice.risk_summary == "Critical production adjustments recommended before release."


def test_existing_api_behavior_remains_unchanged() -> None:
    response = client.post(
        "/api/v2/analyze",
        files={"file": ("generated.wav", _minimal_wav_bytes(), "audio/wav")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert set(body.keys()) == {"status", "analysis"}
    assert "moves" not in body["analysis"]


def _metrics(**overrides: object) -> AudioMetrics:
    values = dict(
        duration_seconds=180.0,
        sample_rate_hz=48_000,
        channels=2,
        frames=8_640_000,
        peak_abs=0.95,
        peak_dbfs=-0.45,
        integrated_lufs=-9.0,
        short_term_lufs=-8.5,
        true_peak_abs=0.92,
        true_peak_dbfs=-0.8,
        rms=0.25,
        rms_dbfs=-12.0,
        crest_factor=3.0,
        crest_factor_db=10.0,
        dynamic_range_db=6.0,
        clipping_sample_count=0,
        clipping_ratio=0.0,
        clipping_risk="none",
        stereo_balance=0.0,
        stereo_correlation=0.8,
        mid_energy=0.05,
        side_energy=0.01,
        side_energy_ratio=0.15,
        stereo_width=0.45,
        spectral_centroid_hz=1800.0,
        low_band_ratio=0.22,
        mid_band_ratio=0.50,
        high_band_ratio=0.20,
        harsh_band_ratio=0.10,
        sub_band_ratio=0.10,
        bass_band_ratio=0.22,
        low_mid_band_ratio=0.35,
        high_mid_band_ratio=0.15,
        low_end_profile="balanced",
        stereo_profile="centered",
        harshness_profile="present",
        loudness_profile="loud_master",
        true_peak_risk="watch",
    )
    values.update(overrides)
    return AudioMetrics(
        **values,  # type: ignore[arg-type]
    )


def _comparison(*deltas: MetricDelta, overall_severity: str | None = None) -> ReferenceComparison:
    delta_list = list(deltas)
    return ReferenceComparison(
        profile_id="modern_hiphop_master",
        display_name="Modern Hip-Hop Master",
        deltas=delta_list,
        overall_severity=overall_severity or _overall_severity(delta_list),
        strongest_issues=delta_list,
    )


def _delta(
    metric_name: str,
    measured: float,
    target_min: float,
    target_max: float,
    delta_to_range: float,
    direction: str,
    severity: str,
) -> MetricDelta:
    return MetricDelta(
        metric_name=metric_name,
        measured=measured,
        target_min=target_min,
        target_max=target_max,
        delta_to_range=delta_to_range,
        direction=direction,
        severity=severity,
        unit="ratio",
    )


def _overall_severity(deltas: list[MetricDelta]) -> str:
    priority = {"none": 0, "low": 1, "medium": 2, "high": 3}
    worst = max((priority[delta.severity] for delta in deltas), default=0)
    return next(severity for severity, value in priority.items() if value == worst)


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


def _minimal_wav_bytes() -> bytes:
    import io

    import numpy as np
    import soundfile as sf

    sample_rate_hz = 48_000
    samples = np.zeros(sample_rate_hz, dtype=np.float32)
    buffer = io.BytesIO()
    sf.write(buffer, samples, sample_rate_hz, format="WAV")
    return buffer.getvalue()

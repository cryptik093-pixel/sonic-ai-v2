from dataclasses import dataclass
from math import isfinite
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.audio.metrics import AudioMetrics


SEVERITY_PRIORITY = {"none": 0, "low": 1, "medium": 2, "high": 3}


@dataclass(frozen=True)
class ReferenceRange:
    metric_name: str
    target_min: float
    target_max: float
    warning_tolerance: float
    critical_tolerance: float
    unit: str


@dataclass(frozen=True)
class ReferenceProfile:
    profile_id: str
    display_name: str
    description: str
    ranges: dict[str, ReferenceRange]


@dataclass(frozen=True)
class MetricDelta:
    metric_name: str
    measured: float
    target_min: float
    target_max: float
    delta_to_range: float
    direction: str
    severity: str
    unit: str


@dataclass(frozen=True)
class ReferenceComparison:
    profile_id: str
    display_name: str
    deltas: list[MetricDelta]
    overall_severity: str
    strongest_issues: list[MetricDelta]


def get_reference_profile(profile_id: str) -> ReferenceProfile:
    try:
        return REFERENCE_PROFILES[profile_id]
    except KeyError as exc:
        raise ValueError(f"Unknown reference profile: '{profile_id}'.") from exc


def list_reference_profiles() -> list[ReferenceProfile]:
    return list(REFERENCE_PROFILES.values())


def compare_metrics_to_profile(
    metrics: "AudioMetrics",
    profile_id: str = "modern_hiphop_master",
) -> ReferenceComparison:
    profile = get_reference_profile(profile_id)
    deltas = [
        _compare_range(metrics, reference_range)
        for reference_range in profile.ranges.values()
    ]
    strongest_issues = sorted(
        (delta for delta in deltas if delta.severity != "none"),
        key=lambda delta: (SEVERITY_PRIORITY[delta.severity], abs(delta.delta_to_range)),
        reverse=True,
    )[:5]

    return ReferenceComparison(
        profile_id=profile.profile_id,
        display_name=profile.display_name,
        deltas=deltas,
        overall_severity=_overall_severity(deltas),
        strongest_issues=strongest_issues,
    )


def _range(metric_name: str, target_min: float, target_max: float, unit: str) -> ReferenceRange:
    warning_tolerance, critical_tolerance = _tolerances(metric_name)
    return ReferenceRange(
        metric_name=metric_name,
        target_min=float(target_min),
        target_max=float(target_max),
        warning_tolerance=warning_tolerance,
        critical_tolerance=critical_tolerance,
        unit=unit,
    )


def _tolerances(metric_name: str) -> tuple[float, float]:
    if metric_name == "integrated_lufs":
        return 2.0, 5.0
    if metric_name == "true_peak_dbfs":
        return 0.7, 1.5
    if metric_name == "crest_factor_db":
        return 3.0, 6.0
    return 0.05, 0.15


def _compare_range(metrics: "AudioMetrics", reference_range: ReferenceRange) -> MetricDelta:
    measured = _metric_value(metrics, reference_range.metric_name)
    if measured < reference_range.target_min:
        delta_to_range = float(measured - reference_range.target_min)
        direction = "below_target"
    elif measured > reference_range.target_max:
        delta_to_range = float(measured - reference_range.target_max)
        direction = "above_target"
    else:
        delta_to_range = 0.0
        direction = "inside_target"

    return MetricDelta(
        metric_name=reference_range.metric_name,
        measured=measured,
        target_min=float(reference_range.target_min),
        target_max=float(reference_range.target_max),
        delta_to_range=delta_to_range,
        direction=direction,
        severity=_severity(
            delta_to_range=delta_to_range,
            warning_tolerance=reference_range.warning_tolerance,
            critical_tolerance=reference_range.critical_tolerance,
        ),
        unit=reference_range.unit,
    )


def _metric_value(metrics: "AudioMetrics", metric_name: str) -> float:
    if not hasattr(metrics, metric_name):
        raise ValueError(f"AudioMetrics is missing required metric: '{metric_name}'.")

    value = float(getattr(metrics, metric_name))
    if not isfinite(value):
        raise ValueError(f"AudioMetrics metric '{metric_name}' is not finite.")
    return value


def _severity(delta_to_range: float, warning_tolerance: float, critical_tolerance: float) -> str:
    distance = abs(delta_to_range)
    if distance == 0.0:
        return "none"
    if distance <= warning_tolerance:
        return "low"
    if distance <= critical_tolerance:
        return "medium"
    return "high"


def _overall_severity(deltas: list[MetricDelta]) -> str:
    worst = max((SEVERITY_PRIORITY[delta.severity] for delta in deltas), default=0)
    for severity, priority in SEVERITY_PRIORITY.items():
        if priority == worst:
            return severity
    return "none"


REFERENCE_PROFILES: dict[str, ReferenceProfile] = {
    "modern_hiphop_master": ReferenceProfile(
        profile_id="modern_hiphop_master",
        display_name="Modern Hip-Hop Master",
        description="Dense, loud modern hip-hop master target with controlled lows and width.",
        ranges={
            "integrated_lufs": _range("integrated_lufs", -10.5, -8.0, "LUFS"),
            "true_peak_dbfs": _range("true_peak_dbfs", -1.2, -0.3, "dBFS"),
            "low_band_ratio": _range("low_band_ratio", 0.16, 0.34, "ratio"),
            "sub_band_ratio": _range("sub_band_ratio", 0.04, 0.16, "ratio"),
            "mid_band_ratio": _range("mid_band_ratio", 0.35, 0.62, "ratio"),
            "high_band_ratio": _range("high_band_ratio", 0.12, 0.32, "ratio"),
            "harsh_band_ratio": _range("harsh_band_ratio", 0.06, 0.20, "ratio"),
            "side_energy_ratio": _range("side_energy_ratio", 0.08, 0.32, "ratio"),
            "stereo_correlation": _range("stereo_correlation", 0.35, 0.98, "ratio"),
            "crest_factor_db": _range("crest_factor_db", 6.0, 14.0, "dB"),
        },
    ),
    "streaming_balanced": ReferenceProfile(
        profile_id="streaming_balanced",
        display_name="Streaming Balanced",
        description="Balanced streaming target with conservative loudness and true peak margin.",
        ranges={
            "integrated_lufs": _range("integrated_lufs", -16.0, -12.0, "LUFS"),
            "true_peak_dbfs": _range("true_peak_dbfs", -2.0, -1.0, "dBFS"),
            "low_band_ratio": _range("low_band_ratio", 0.12, 0.28, "ratio"),
            "sub_band_ratio": _range("sub_band_ratio", 0.02, 0.12, "ratio"),
            "mid_band_ratio": _range("mid_band_ratio", 0.40, 0.68, "ratio"),
            "high_band_ratio": _range("high_band_ratio", 0.10, 0.34, "ratio"),
            "harsh_band_ratio": _range("harsh_band_ratio", 0.04, 0.18, "ratio"),
            "side_energy_ratio": _range("side_energy_ratio", 0.05, 0.28, "ratio"),
            "stereo_correlation": _range("stereo_correlation", 0.45, 0.99, "ratio"),
            "crest_factor_db": _range("crest_factor_db", 8.0, 18.0, "dB"),
        },
    ),
    "club_trap_master": ReferenceProfile(
        profile_id="club_trap_master",
        display_name="Club Trap Master",
        description="Loud club and trap target with extended low-end weight.",
        ranges={
            "integrated_lufs": _range("integrated_lufs", -9.5, -6.5, "LUFS"),
            "true_peak_dbfs": _range("true_peak_dbfs", -1.0, -0.1, "dBFS"),
            "low_band_ratio": _range("low_band_ratio", 0.20, 0.40, "ratio"),
            "sub_band_ratio": _range("sub_band_ratio", 0.07, 0.20, "ratio"),
            "mid_band_ratio": _range("mid_band_ratio", 0.30, 0.58, "ratio"),
            "high_band_ratio": _range("high_band_ratio", 0.10, 0.30, "ratio"),
            "harsh_band_ratio": _range("harsh_band_ratio", 0.05, 0.22, "ratio"),
            "side_energy_ratio": _range("side_energy_ratio", 0.08, 0.36, "ratio"),
            "stereo_correlation": _range("stereo_correlation", 0.30, 0.98, "ratio"),
            "crest_factor_db": _range("crest_factor_db", 5.0, 12.0, "dB"),
        },
    ),
}

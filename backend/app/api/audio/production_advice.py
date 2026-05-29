from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Literal

import numpy as np

from app.audio.metrics import AudioMetrics
from app.audio.reference_profiles import MetricDelta, ReferenceComparison

AdviceDomain = Literal[
    "loudness",
    "dynamics",
    "low_end",
    "midrange",
    "high_end",
    "stereo",
    "space",
    "transients",
]
AdviceSeverity = Literal["info", "mild", "moderate", "critical"]
IssueSeverity = Literal["mild", "moderate", "severe"]

DELTA_SEVERITY_TO_ADVICE: dict[str, AdviceSeverity] = {
    "low": "mild",
    "medium": "moderate",
    "high": "critical",
}
ADVICE_SEVERITY_PRIORITY = {"info": 0, "mild": 1, "moderate": 2, "critical": 3}
ISSUE_SEVERITY_PRIORITY = {"mild": 1, "moderate": 2, "severe": 3}


@dataclass(frozen=True)
class EngineeringRuleThresholds:
    """Thresholds for deterministic mix/master issue detection."""

    hot_true_peak_dbfs: float = -0.3
    elevated_true_peak_dbfs: float = -1.0
    overcompressed_crest_factor_db: float = 6.0
    flat_dynamic_range_db: float = 3.0
    low_end_buildup_ratio: float = 0.42
    thin_low_end_ratio: float = 0.10
    harsh_high_mid_ratio: float = 0.28
    dark_high_ratio: float = 0.08
    phase_risk_correlation: float = 0.20
    excessive_width: float = 0.85
    narrow_width: float = 0.12


ENGINEERING_THRESHOLDS = EngineeringRuleThresholds()


@dataclass(frozen=True)
class ProductionMove:
    id: str
    domain: AdviceDomain
    severity: AdviceSeverity
    rationale: str
    suggested_actions: list[str]


@dataclass(frozen=True)
class ProductionAdvice:
    profile_id: str
    risk_summary: str
    moves: list[ProductionMove]


@dataclass(frozen=True)
class EngineeringIssue:
    issue_type: str
    severity: IssueSeverity
    description: str
    suggested_actions: list[str]


@dataclass(frozen=True)
class EngineeringReport:
    sections: dict[str, list[str]]
    issues: list[EngineeringIssue]
    suggested_fixes: list[str]


def generate_production_advice(
    metrics: AudioMetrics,
    comparison: ReferenceComparison,
) -> ProductionAdvice:
    if comparison.overall_severity == "none":
        moves = [_healthy_move()]
    else:
        moves = [
            move
            for delta in comparison.deltas
            if (move := _move_for_delta(delta)) is not None
        ]
        moves = _sort_moves(moves)

    return ProductionAdvice(
        profile_id=comparison.profile_id,
        risk_summary=_risk_summary(moves),
        moves=moves,
    )


def generate_engineering_issues(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds = ENGINEERING_THRESHOLDS,
) -> list[EngineeringIssue]:
    """Detect deterministic engineering issues from measured audio metrics."""
    issues = [
        issue
        for issue in (
            _true_peak_issue(metrics, thresholds),
            _overcompressed_issue(metrics, thresholds),
            _low_end_issue(metrics, thresholds),
            _harsh_high_mid_issue(metrics, thresholds),
            _dark_top_end_issue(metrics, thresholds),
            _stereo_phase_issue(metrics, thresholds),
            _stereo_width_issue(metrics, thresholds),
        )
        if issue is not None
    ]
    return sorted(
        issues,
        key=lambda issue: (-ISSUE_SEVERITY_PRIORITY[issue.severity], issue.issue_type),
    )


def generate_engineering_report(
    metrics: AudioMetrics,
    comparison: ReferenceComparison,
) -> EngineeringReport:
    """Build a sectioned technical report from deterministic metrics and issues."""
    issues = generate_engineering_issues(metrics)
    sections = {
        "Loudness & Leveling": [
            f"Integrated loudness: {metrics.integrated_lufs:.2f} LUFS.",
            f"Short-term loudness peak: {metrics.short_term_lufs:.2f} LUFS.",
            f"True peak: {metrics.true_peak_dbfs:.2f} dBFS.",
        ],
        "Dynamics": [
            f"Crest factor: {metrics.crest_factor_db:.2f} dB.",
            f"Basic dynamic range: {metrics.dynamic_range_db:.2f} dB.",
            f"Clipping risk: {metrics.clipping_risk}.",
        ],
        "Frequency Balance": [
            f"Sub: {metrics.sub_band_ratio:.3f}.",
            f"Bass: {metrics.bass_band_ratio:.3f}.",
            f"Low-mid: {metrics.low_mid_band_ratio:.3f}.",
            f"High-mid: {metrics.high_mid_band_ratio:.3f}.",
            f"High: {metrics.high_band_ratio:.3f}.",
        ],
        "Stereo Image": [
            f"Stereo correlation: {metrics.stereo_correlation:.3f}.",
            f"Width estimate: {metrics.stereo_width:.3f}.",
            f"Side energy ratio: {metrics.side_energy_ratio:.3f}.",
        ],
        "Technical Issues": [
            issue.description for issue in issues
        ] or ["No major technical issues detected by deterministic rules."],
        "Suggested Fixes": _suggested_fixes(issues),
    }
    return EngineeringReport(
        sections=sections,
        issues=issues,
        suggested_fixes=sections["Suggested Fixes"],
    )


def production_advice_to_dict(advice: ProductionAdvice) -> dict[str, Any]:
    return _to_plain_python(advice)


def engineering_report_to_dict(report: EngineeringReport) -> dict[str, Any]:
    return _to_plain_python(report)


def _move_for_delta(delta: MetricDelta) -> ProductionMove | None:
    if delta.severity == "none":
        return None

    severity = DELTA_SEVERITY_TO_ADVICE[delta.severity]
    match delta.metric_name:
        case "integrated_lufs":
            return _loudness_move(delta, severity)
        case "true_peak_dbfs":
            return _true_peak_move(delta, severity)
        case "low_band_ratio" | "sub_band_ratio":
            return _low_end_move(delta, severity)
        case "mid_band_ratio":
            return _midrange_move(delta, severity)
        case "harsh_band_ratio" | "high_band_ratio":
            return _high_end_move(delta, severity)
        case "side_energy_ratio" | "stereo_correlation":
            return _stereo_move(delta, severity)
        case "crest_factor_db":
            return _crest_factor_move(delta, severity)
    return None


def _healthy_move() -> ProductionMove:
    return ProductionMove(
        id="profile_alignment_stable",
        domain="dynamics",
        severity="info",
        rationale="Core metrics are inside the selected reference profile ranges.",
        suggested_actions=[
            "Preserve the current balance before making creative changes.",
            "Use small A/B moves rather than broad corrective processing.",
        ],
    )


def _loudness_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove:
    if delta.direction == "below_target":
        return ProductionMove(
            id="increase_integrated_loudness",
            domain="loudness",
            severity=severity,
            rationale="Integrated loudness is below the selected reference range.",
            suggested_actions=[
                "Raise controlled level into the reference range before final limiting.",
                "Use gain staging or compression before relying on limiter output.",
            ],
        )
    return ProductionMove(
        id="reduce_integrated_loudness",
        domain="loudness",
        severity=severity,
        rationale="Integrated loudness is above the selected reference range.",
        suggested_actions=[
            "Reduce limiter drive or upstream bus gain.",
            "Check whether saturation or clipping is creating unnecessary density.",
        ],
    )


def _true_peak_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove | None:
    if delta.direction != "above_target":
        return None
    return ProductionMove(
        id="reduce_true_peak",
        domain="dynamics",
        severity=severity,
        rationale="True peak level is above the selected reference ceiling.",
        suggested_actions=[
            "Lower limiter ceiling or output trim.",
            "Recheck codec headroom after reducing true peak level.",
        ],
    )


def _low_end_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove:
    if delta.direction == "below_target":
        return ProductionMove(
            id=f"increase_{delta.metric_name}",
            domain="low_end",
            severity=severity,
            rationale=f"{delta.metric_name} is below the selected reference range.",
            suggested_actions=[
                "Review kick and bass level balance before broad EQ changes.",
                "Use focused low-band EQ or arrangement cleanup to support the low end.",
            ],
        )
    return ProductionMove(
        id=f"reduce_{delta.metric_name}",
        domain="low_end",
        severity=severity,
        rationale=f"{delta.metric_name} is above the selected reference range.",
        suggested_actions=[
            "Reduce low-frequency buildup with source balance or narrow EQ moves.",
            "Check limiter behavior after reducing excess low-end energy.",
        ],
    )


def _midrange_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove:
    action = "increase" if delta.direction == "below_target" else "reduce"
    return ProductionMove(
        id=f"{action}_mid_band_ratio",
        domain="midrange",
        severity=severity,
        rationale="Midrange energy is outside the selected reference range.",
        suggested_actions=[
            "Adjust vocal, lead, and harmonic instrument balance first.",
            "Use moderate EQ moves and compare against level-matched references.",
        ],
    )


def _high_end_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove:
    if delta.metric_name == "harsh_band_ratio":
        return ProductionMove(
            id="reduce_harsh_band_ratio",
            domain="high_end",
            severity=severity,
            rationale="Harsh-band energy is above the selected reference range.",
            suggested_actions=[
                "Reduce aggressive upper-mid resonances before final limiting.",
                "Use de-essing or dynamic EQ on harsh sources instead of broad dulling.",
            ],
        )

    action = "increase" if delta.direction == "below_target" else "reduce"
    return ProductionMove(
        id=f"{action}_high_band_ratio",
        domain="high_end",
        severity=severity,
        rationale="High-band energy is outside the selected reference range.",
        suggested_actions=[
            "Adjust cymbal, air-band, and brightness balance with level-matched checks.",
            "Use subtle shelving or source-level changes before heavy bus processing.",
        ],
    )


def _stereo_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove | None:
    if delta.metric_name == "side_energy_ratio":
        action = "increase" if delta.direction == "below_target" else "reduce"
        return ProductionMove(
            id=f"{action}_side_energy_ratio",
            domain="stereo",
            severity=severity,
            rationale="Stereo side energy is outside the selected reference range.",
            suggested_actions=[
                "Adjust width on supporting elements before widening the full mix.",
                "Check mono compatibility after stereo balance changes.",
            ],
        )

    if delta.direction != "below_target":
        return None
    return ProductionMove(
        id="increase_stereo_correlation",
        domain="stereo",
        severity=severity,
        rationale="Stereo correlation is below the selected reference range.",
        suggested_actions=[
            "Inspect polarity and phase-heavy widening processors.",
            "Narrow low-frequency stereo content and recheck mono compatibility.",
        ],
    )


def _crest_factor_move(delta: MetricDelta, severity: AdviceSeverity) -> ProductionMove:
    if delta.direction == "below_target":
        return ProductionMove(
            id="restore_transient_contrast",
            domain="transients",
            severity=severity,
            rationale="Crest factor is below the selected reference range.",
            suggested_actions=[
                "Reduce over-compression or limiter drive.",
                "Restore transient contrast on drums and other leading elements.",
            ],
        )
    return ProductionMove(
        id="control_dynamic_range",
        domain="dynamics",
        severity=severity,
        rationale="Crest factor is above the selected reference range.",
        suggested_actions=[
            "Use controlled compression where level movement feels excessive.",
            "Check whether transient peaks are limiting achievable loudness.",
        ],
    )


def _risk_summary(moves: list[ProductionMove]) -> str:
    corrective_moves = [move for move in moves if move.severity != "info"]
    if not corrective_moves:
        return "No major corrective issues detected."

    highest = max(ADVICE_SEVERITY_PRIORITY[move.severity] for move in corrective_moves)
    if highest == ADVICE_SEVERITY_PRIORITY["mild"]:
        return "Minor production adjustments recommended."
    if highest == ADVICE_SEVERITY_PRIORITY["moderate"]:
        return "Moderate production adjustments recommended."
    return "Critical production adjustments recommended before release."


def _sort_moves(moves: list[ProductionMove]) -> list[ProductionMove]:
    return sorted(
        moves,
        key=lambda move: (-ADVICE_SEVERITY_PRIORITY[move.severity], move.domain, move.id),
    )


def _true_peak_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if metrics.true_peak_dbfs < thresholds.elevated_true_peak_dbfs:
        return None
    severity: IssueSeverity = (
        "severe" if metrics.true_peak_dbfs >= thresholds.hot_true_peak_dbfs else "moderate"
    )
    return EngineeringIssue(
        issue_type="true_peak_too_hot",
        severity=severity,
        description="True peak headroom is too tight for reliable delivery and codec conversion.",
        suggested_actions=[
            "Lower limiter ceiling to at least -1.0 dBTP for streaming-safe delivery.",
            "Reduce final limiter input if the ceiling reduction audibly changes transients.",
        ],
    )


def _overcompressed_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if (
        metrics.crest_factor_db > thresholds.overcompressed_crest_factor_db
        and metrics.dynamic_range_db > thresholds.flat_dynamic_range_db
    ):
        return None
    severity: IssueSeverity = (
        "severe"
        if metrics.crest_factor_db < 4.0 and metrics.dynamic_range_db < 2.0
        else "moderate"
    )
    return EngineeringIssue(
        issue_type="overcompressed",
        severity=severity,
        description=(
            "Transient contrast and level movement are low, suggesting excessive "
            "compression or limiting."
        ),
        suggested_actions=[
            "Back off bus compression or final limiter drive and regain level downstream.",
            "Use slower attack or parallel compression to preserve drum and vocal transients.",
        ],
    )


def _low_end_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    low_end_ratio = metrics.sub_band_ratio + metrics.bass_band_ratio
    if low_end_ratio >= thresholds.low_end_buildup_ratio:
        return EngineeringIssue(
            issue_type="low_end_buildup",
            severity="severe" if low_end_ratio >= 0.55 else "moderate",
            description="Sub and bass energy dominate the spectrum and may reduce translation.",
            suggested_actions=[
                "Tighten kick and bass overlap with source balance, sidechain, or narrow EQ.",
                "High-pass non-bass elements and recheck limiter gain reduction after cleanup.",
            ],
        )
    if low_end_ratio <= thresholds.thin_low_end_ratio:
        return EngineeringIssue(
            issue_type="thin_low_end",
            severity="moderate",
            description="Low-frequency energy is light relative to the rest of the spectrum.",
            suggested_actions=[
                "Check kick and bass level before adding broad low-shelf EQ.",
                "Compare against level-matched references on small and full-range monitors.",
            ],
        )
    return None


def _harsh_high_mid_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if metrics.high_mid_band_ratio < thresholds.harsh_high_mid_ratio:
        return None
    return EngineeringIssue(
        issue_type="harsh_high_mids",
        severity="severe" if metrics.high_mid_band_ratio >= 0.38 else "moderate",
        description="High-mid energy is elevated and may read as harshness or vocal edge.",
        suggested_actions=[
            "Use dynamic EQ or de-essing around harsh sources before broad master EQ.",
            "Level-match A/B checks after reducing 2-6 kHz buildup.",
        ],
    )


def _dark_top_end_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if metrics.high_band_ratio > thresholds.dark_high_ratio:
        return None
    return EngineeringIssue(
        issue_type="dark_top_end",
        severity="mild",
        description="High-band energy is low, which may make the master feel muted or closed.",
        suggested_actions=[
            "Raise source brightness on cymbals, vocals, or harmonic elements first.",
            "Use subtle high-shelf EQ only after confirming the mix is not level-biased.",
        ],
    )


def _stereo_phase_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if metrics.stereo_correlation >= thresholds.phase_risk_correlation:
        return None
    return EngineeringIssue(
        issue_type="phase_correlation_risk",
        severity="severe" if metrics.stereo_correlation < 0.0 else "moderate",
        description="Stereo correlation is low, indicating mono compatibility or polarity risk.",
        suggested_actions=[
            "Inspect stereo wideners, chorus, Haas delays, and polarity on doubled sources.",
            "Narrow low frequencies and verify the chorus or drop in mono.",
        ],
    )


def _stereo_width_issue(
    metrics: AudioMetrics,
    thresholds: EngineeringRuleThresholds,
) -> EngineeringIssue | None:
    if metrics.stereo_width >= thresholds.excessive_width:
        return EngineeringIssue(
            issue_type="excessive_width",
            severity="moderate",
            description=(
                "Side energy is high relative to mid energy, which can weaken center impact."
            ),
            suggested_actions=[
                "Reduce full-mix widening and keep kick, bass, lead vocal, and snare centered.",
                "Use band-limited widening above the low end and recheck mono fold-down.",
            ],
        )
    if metrics.channels > 1 and metrics.stereo_width <= thresholds.narrow_width:
        return EngineeringIssue(
            issue_type="narrow_stereo_image",
            severity="mild",
            description=(
                "Stereo width is narrow, leaving limited contrast between center "
                "and side elements."
            ),
            suggested_actions=[
                "Add width to supporting instruments rather than widening the full master.",
                "Use arrangement panning before stereo bus processing.",
            ],
        )
    return None


def _suggested_fixes(issues: list[EngineeringIssue]) -> list[str]:
    fixes: list[str] = []
    for issue in issues:
        for action in issue.suggested_actions:
            if action not in fixes:
                fixes.append(action)
    return fixes or [
        "Preserve current engineering balance and continue with level-matched A/B checks."
    ]


def _to_plain_python(value: Any) -> Any:
    if is_dataclass(value):
        return _to_plain_python(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_plain_python(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_to_plain_python(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    return value

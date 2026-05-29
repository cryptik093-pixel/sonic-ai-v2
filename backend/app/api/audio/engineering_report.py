from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Literal

import numpy as np

Confidence = Literal["high", "medium", "low"]
Grade = Literal["excellent", "strong", "needs_work", "problematic", "unknown"]
MoveSeverity = Literal["critical", "major", "minor"]
ChainType = Literal["clean_master", "loud_modern_master", "corrective_mix_prep", "unknown"]

REPORT_VERSION = "engineering-report-0.1.0"
IMPORTANT_METRICS = (
    "integrated_lufs",
    "true_peak_dbfs",
    "crest_factor_db",
    "dynamic_range_db",
    "stereo_correlation",
    "sub_band_ratio",
    "bass_band_ratio",
    "high_band_ratio",
    "high_mid_band_ratio",
)
SEVERITY_PRIORITY = {"minor": 1, "major": 2, "critical": 3}


@dataclass(frozen=True)
class EngineeringReport:
    summary: "ReportSummary"
    scorecard: "ReportScorecard"
    priority_moves: list["ReportMove"]
    mastering_chain: "MasteringChainRecommendation"
    mix_translation: "MixTranslationNotes"
    warnings: list["ReportWarning"]
    export_layout: "ReportExportLayout"
    metadata: "ReportMetadata"


@dataclass(frozen=True)
class ReportSummary:
    overall_grade: Grade
    short_verdict: str
    main_issue: str | None
    confidence: Confidence


@dataclass(frozen=True)
class ReportScorecard:
    loudness: int
    dynamics: int
    low_end: int
    stereo: int
    spectral_balance: int
    translation: int


@dataclass(frozen=True)
class ReportMove:
    id: str
    title: str
    domain: str
    severity: MoveSeverity
    reason: str
    action: str
    confidence: Confidence


@dataclass(frozen=True)
class MasteringChainRecommendation:
    chain_type: ChainType
    recommended_chain: list[str]
    warning: str | None


@dataclass(frozen=True)
class MixTranslationNotes:
    club_translation: str
    phone_translation: str
    car_translation: str
    mono_translation: str


@dataclass(frozen=True)
class ReportWarning:
    code: str
    message: str
    severity: MoveSeverity


@dataclass(frozen=True)
class ReportExportLayout:
    layout_version: str
    format: str
    title: str
    subtitle: str
    section_order: list[str]
    sections: list["ReportExportSection"]


@dataclass(frozen=True)
class ReportExportSection:
    id: str
    title: str
    kind: str
    items: list[str]


@dataclass(frozen=True)
class ReportMetadata:
    deterministic: bool
    report_version: str
    limitations: list[str]


def build_engineering_report(
    analysis: dict[str, Any],
    target_profile: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic producer-facing report from an analysis payload."""
    context = _ReportContext(analysis=analysis, target_profile=target_profile)
    warnings = _missing_metric_warnings(context)
    warnings.extend(_technical_warnings(context))
    confidence = _confidence(context, warnings)
    scorecard = _scorecard(context)
    moves = _priority_moves(context, confidence)
    summary = _summary(scorecard, moves, confidence)
    mastering_chain = _mastering_chain(summary.overall_grade, moves, confidence)
    mix_translation = _mix_translation(context)
    limitations = _limitations(context, target_profile)
    report = EngineeringReport(
        summary=summary,
        scorecard=scorecard,
        priority_moves=moves,
        mastering_chain=mastering_chain,
        mix_translation=mix_translation,
        warnings=warnings,
        export_layout=_export_layout(
            context=context,
            summary=summary,
            scorecard=scorecard,
            moves=moves,
            mastering_chain=mastering_chain,
            mix_translation=mix_translation,
            warnings=warnings,
            limitations=limitations,
        ),
        metadata=ReportMetadata(
            deterministic=True,
            report_version=REPORT_VERSION,
            limitations=limitations,
        ),
    )
    return _to_plain_python(report)


class _ReportContext:
    def __init__(self, analysis: dict[str, Any], target_profile: str | None) -> None:
        self.analysis = analysis if isinstance(analysis, dict) else {}
        self.target_profile = target_profile or _string_value(self.analysis.get("profile_id"))
        self.metrics = _dict_value(self.analysis.get("metrics"))
        self.comparison = _dict_value(self.analysis.get("reference_comparison"))
        self.deltas = _list_value(self.comparison.get("deltas"))
        self.strongest_issues = _list_value(self.comparison.get("strongest_issues"))

    def metric(self, *names: str) -> float | None:
        for name in names:
            value = _number_from_path(self.metrics, name)
            if value is not None:
                return value
        return None

    def delta(self, metric_name: str) -> dict[str, Any] | None:
        for item in [*self.strongest_issues, *self.deltas]:
            delta = _dict_value(item)
            if delta.get("metric_name") == metric_name:
                return delta
        return None

    def profile_severity(self) -> str:
        severity = _string_value(self.comparison.get("overall_severity"))
        return severity or "none"


def _scorecard(context: _ReportContext) -> ReportScorecard:
    loudness = _loudness_score(context)
    dynamics = _dynamics_score(context)
    low_end = _low_end_score(context)
    stereo = _stereo_score(context)
    spectral = _spectral_score(context)
    translation = _bounded_score(round((loudness + dynamics + low_end + stereo + spectral) / 5))
    return ReportScorecard(
        loudness=loudness,
        dynamics=dynamics,
        low_end=low_end,
        stereo=stereo,
        spectral_balance=spectral,
        translation=translation,
    )


def _loudness_score(context: _ReportContext) -> int:
    score = 100
    integrated_lufs = context.metric("integrated_lufs", "lufs")
    true_peak_dbfs = context.metric("true_peak_dbfs", "true_peak_db", "true_peak")
    if integrated_lufs is None:
        score -= 35
    elif integrated_lufs > -7.0:
        score -= 28
    elif integrated_lufs > -8.0:
        score -= 15
    elif integrated_lufs < -22.0:
        score -= 26
    elif integrated_lufs < -16.0:
        score -= 12

    if true_peak_dbfs is None:
        score -= 30
    elif true_peak_dbfs >= -0.3:
        score -= 32
    elif true_peak_dbfs >= -1.0:
        score -= 14
    return _apply_delta_penalty(
        _bounded_score(score),
        context,
        ("integrated_lufs", "true_peak_dbfs"),
    )


def _dynamics_score(context: _ReportContext) -> int:
    score = 100
    crest = context.metric("crest_factor_db")
    dynamic_range = context.metric("dynamic_range_db")
    clipping_ratio = context.metric("clipping_ratio")
    if crest is None:
        score -= 18
    elif crest < 4.0:
        score -= 34
    elif crest < 6.0:
        score -= 18
    if dynamic_range is None:
        score -= 18
    elif dynamic_range < 2.0:
        score -= 28
    elif dynamic_range < 4.0:
        score -= 12
    if clipping_ratio is not None and clipping_ratio > 0.001:
        score -= 20
    return _apply_delta_penalty(_bounded_score(score), context, ("crest_factor_db",))


def _low_end_score(context: _ReportContext) -> int:
    sub = context.metric("sub_band_ratio")
    bass = context.metric("bass_band_ratio", "low_band_ratio")
    if sub is None or bass is None:
        return 55
    low_end = sub + bass
    score = 100
    if low_end >= 0.55:
        score -= 36
    elif low_end >= 0.42:
        score -= 20
    elif low_end <= 0.08:
        score -= 24
    elif low_end <= 0.12:
        score -= 12
    return _apply_delta_penalty(
        _bounded_score(score),
        context,
        ("sub_band_ratio", "low_band_ratio"),
    )


def _stereo_score(context: _ReportContext) -> int:
    score = 100
    correlation = context.metric("stereo_correlation")
    width = context.metric("stereo_width", "side_energy_ratio")
    if correlation is None:
        score -= 28
    elif correlation < 0.0:
        score -= 42
    elif correlation < 0.2:
        score -= 26
    if width is None:
        score -= 14
    elif width > 0.9:
        score -= 18
    return _apply_delta_penalty(
        _bounded_score(score),
        context,
        ("stereo_correlation", "side_energy_ratio"),
    )


def _spectral_score(context: _ReportContext) -> int:
    score = 100
    high_mid = context.metric("high_mid_band_ratio", "harsh_band_ratio")
    high = context.metric("high_band_ratio")
    if high_mid is None:
        score -= 18
    elif high_mid >= 0.38:
        score -= 30
    elif high_mid >= 0.28:
        score -= 16
    if high is None:
        score -= 14
    elif high <= 0.05:
        score -= 16
    elif high <= 0.08:
        score -= 8
    return _apply_delta_penalty(
        _bounded_score(score),
        context,
        ("high_mid_band_ratio", "harsh_band_ratio", "high_band_ratio", "mid_band_ratio"),
    )


def _priority_moves(context: _ReportContext, confidence: Confidence) -> list[ReportMove]:
    candidates = [
        _true_peak_move(context, confidence),
        _loudness_move(context, confidence),
        _dynamics_move(context, confidence),
        _low_end_move(context, confidence),
        _stereo_move(context, confidence),
        _spectral_move(context, confidence),
    ]
    moves = [move for move in candidates if move is not None]
    return sorted(
        moves,
        key=lambda move: (-SEVERITY_PRIORITY[move.severity], move.domain, move.id),
    )[:5]


def _true_peak_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    true_peak = context.metric("true_peak_dbfs", "true_peak_db", "true_peak")
    if true_peak is None or true_peak < -1.0:
        return None
    severity: MoveSeverity = "critical" if true_peak >= -0.3 else "major"
    return ReportMove(
        id="control_true_peak_headroom",
        title="Create safer true-peak headroom",
        domain="loudness",
        severity=severity,
        reason="Measured true peak is close to or above common delivery-safe headroom.",
        action=(
            "Lower limiter ceiling or output trim, then recheck loudness after codec-safe "
            "headroom is restored."
        ),
        confidence=confidence,
    )


def _loudness_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    lufs = context.metric("integrated_lufs", "lufs")
    if lufs is None or -16.0 <= lufs <= -8.0:
        return None
    if lufs > -8.0:
        return ReportMove(
            id="reduce_excess_loudness",
            title="Reduce limiter density",
            domain="loudness",
            severity="major" if lufs > -7.0 else "minor",
            reason="Integrated loudness is very hot and may reduce punch or translation.",
            action=(
                "Back off limiter input, saturation, or clipper drive before chasing final "
                "level."
            ),
            confidence=confidence,
        )
    return ReportMove(
        id="raise_controlled_loudness",
        title="Raise controlled loudness",
        domain="loudness",
        severity="major" if lufs < -22.0 else "minor",
        reason="Integrated loudness is below modern release targets for most producer workflows.",
        action="Use gain staging and controlled bus compression before final limiting.",
        confidence=confidence,
    )


def _dynamics_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    crest = context.metric("crest_factor_db")
    dynamic_range = context.metric("dynamic_range_db")
    if (crest is None or crest >= 6.0) and (dynamic_range is None or dynamic_range >= 4.0):
        return None
    return ReportMove(
        id="restore_dynamic_contrast",
        title="Restore transient contrast",
        domain="dynamics",
        severity=(
            "critical"
            if (crest or 99.0) < 4.0 and (dynamic_range or 99.0) < 2.0
            else "major"
        ),
        reason=(
            "Crest factor or short-window dynamic range suggests compression is flattening "
            "the mix."
        ),
        action=(
            "Reduce bus compression or limiter drive and preserve drum and vocal transient "
            "shape."
        ),
        confidence=confidence,
    )


def _low_end_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    sub = context.metric("sub_band_ratio")
    bass = context.metric("bass_band_ratio", "low_band_ratio")
    if sub is None or bass is None:
        return None
    low_end = sub + bass
    if low_end >= 0.42:
        return ReportMove(
            id="clean_low_end_buildup",
            title="Clean up low-end buildup",
            domain="low_end",
            severity="critical" if low_end >= 0.55 else "major",
            reason="Sub and bass energy are dominating the measured spectrum.",
            action=(
                "Tighten kick and bass overlap with source balance, sidechain, or focused EQ "
                "before mastering."
            ),
            confidence=confidence,
        )
    if low_end <= 0.10:
        return ReportMove(
            id="support_thin_low_end",
            title="Support the low end",
            domain="low_end",
            severity="major",
            reason="Measured low-frequency energy is light relative to the rest of the mix.",
            action=(
                "Check kick and bass level first, then use focused low-band support if "
                "references confirm it."
            ),
            confidence=confidence,
        )
    return None


def _stereo_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    correlation = context.metric("stereo_correlation")
    if correlation is None or correlation >= 0.2:
        return None
    return ReportMove(
        id="fix_mono_compatibility",
        title="Fix mono compatibility risk",
        domain="stereo",
        severity="critical" if correlation < 0.0 else "major",
        reason="Stereo correlation is low, indicating phase or mono fold-down risk.",
        action="Inspect wideners, polarity, Haas delays, and stereo low-end before release checks.",
        confidence=confidence,
    )


def _spectral_move(context: _ReportContext, confidence: Confidence) -> ReportMove | None:
    high_mid = context.metric("high_mid_band_ratio", "harsh_band_ratio")
    if high_mid is None or high_mid < 0.28:
        return None
    return ReportMove(
        id="control_high_mid_harshness",
        title="Control high-mid harshness",
        domain="spectral_balance",
        severity="critical" if high_mid >= 0.38 else "major",
        reason="Measured high-mid energy can read as edge, glare, or harsh vocal presence.",
        action="Use source-level control, dynamic EQ, or de-essing before broad master EQ.",
        confidence=confidence,
    )


def _summary(
    scorecard: ReportScorecard,
    moves: list[ReportMove],
    confidence: Confidence,
) -> ReportSummary:
    average = round(
        (
            scorecard.loudness
            + scorecard.dynamics
            + scorecard.low_end
            + scorecard.stereo
            + scorecard.spectral_balance
            + scorecard.translation
        )
        / 6
    )
    critical_count = sum(1 for move in moves if move.severity == "critical")
    if confidence == "low":
        grade: Grade = "unknown"
    elif critical_count:
        grade = "problematic"
    elif average >= 88:
        grade = "excellent"
    elif average >= 74:
        grade = "strong"
    else:
        grade = "needs_work"

    main_move = moves[0] if moves else None
    verdicts = {
        "excellent": "Release checks look technically stable against the available measurements.",
        "strong": "The mix is close, with a few focused engineering checks recommended.",
        "needs_work": (
            "Several measured areas need attention before this should drive a premium "
            "report or release decision."
        ),
        "problematic": (
            "A high-priority technical issue should be corrected before mastering or "
            "delivery."
        ),
        "unknown": (
            "Important metrics are missing, so this report should be treated as a limited "
            "technical review."
        ),
    }
    return ReportSummary(
        overall_grade=grade,
        short_verdict=verdicts[grade],
        main_issue=main_move.title if main_move else None,
        confidence=confidence,
    )


def _mastering_chain(
    grade: Grade,
    moves: list[ReportMove],
    confidence: Confidence,
) -> MasteringChainRecommendation:
    if confidence == "low" or grade == "unknown":
        return MasteringChainRecommendation(
            chain_type="unknown",
            recommended_chain=["Technical analysis review", "Manual mix check"],
            warning=(
                "Important metrics are missing; use the chain only after reviewing the "
                "source mix."
            ),
        )
    if grade in {"problematic", "needs_work"} or any(
        move.severity == "critical" for move in moves
    ):
        return MasteringChainRecommendation(
            chain_type="corrective_mix_prep",
            recommended_chain=[
                "Low-end cleanup",
                "Harshness control",
                "Dynamic balance correction",
                "Stereo/mono compatibility check",
                "Pre-master gain staging",
            ],
            warning="Correct measured mix issues before pushing final loudness.",
        )
    if any(move.domain == "loudness" and move.id == "raise_controlled_loudness" for move in moves):
        return MasteringChainRecommendation(
            chain_type="loud_modern_master",
            recommended_chain=[
                "Corrective EQ",
                "Multiband compression",
                "Parallel saturation",
                "Clipper",
                "True peak limiter",
            ],
            warning=None,
        )
    return MasteringChainRecommendation(
        chain_type="clean_master",
        recommended_chain=[
            "Corrective EQ",
            "Gentle bus compression",
            "Soft saturation",
            "Stereo safety check",
            "True peak limiter",
        ],
        warning=None,
    )


def _mix_translation(context: _ReportContext) -> MixTranslationNotes:
    low_end_score = _low_end_score(context)
    stereo_score = _stereo_score(context)
    loudness_score = _loudness_score(context)
    spectral_score = _spectral_score(context)
    return MixTranslationNotes(
        club_translation=(
            "Low-end weight should translate on larger systems."
            if low_end_score >= 75
            else "Low-end balance needs review before trusting club playback."
        ),
        phone_translation=(
            "Midrange and loudness should remain readable on small speakers."
            if min(loudness_score, spectral_score) >= 75
            else "Small speakers may expose loudness imbalance or harsh/dark tonal balance."
        ),
        car_translation=(
            "Car playback should be a useful final check rather than a problem-finding step."
            if min(low_end_score, loudness_score, spectral_score) >= 75
            else "Car playback may exaggerate low-end buildup, harshness, or level density."
        ),
        mono_translation=(
            "Mono fold-down risk is low from the available stereo measurements."
            if stereo_score >= 75
            else "Mono playback needs verification because stereo correlation or width is risky."
        ),
    )


def _export_layout(
    context: _ReportContext,
    summary: ReportSummary,
    scorecard: ReportScorecard,
    moves: list[ReportMove],
    mastering_chain: MasteringChainRecommendation,
    mix_translation: MixTranslationNotes,
    warnings: list[ReportWarning],
    limitations: list[str],
) -> ReportExportLayout:
    sections = [
        ReportExportSection(
            id="cover_summary",
            title="Mix Review Summary",
            kind="summary",
            items=[
                f"Grade: {summary.overall_grade}.",
                f"Confidence: {summary.confidence}.",
                summary.short_verdict,
                (
                    f"Main issue: {summary.main_issue}."
                    if summary.main_issue
                    else "Main issue: none detected."
                ),
            ],
        ),
        ReportExportSection(
            id="scorecard",
            title="Engineering Scorecard",
            kind="scorecard",
            items=[
                f"Loudness: {scorecard.loudness}/100.",
                f"Dynamics: {scorecard.dynamics}/100.",
                f"Low end: {scorecard.low_end}/100.",
                f"Stereo: {scorecard.stereo}/100.",
                f"Spectral balance: {scorecard.spectral_balance}/100.",
                f"Translation: {scorecard.translation}/100.",
            ],
        ),
        ReportExportSection(
            id="measured_metrics",
            title="Measured Metrics",
            kind="metric_table",
            items=_metric_rows(context),
        ),
        ReportExportSection(
            id="priority_moves",
            title="Priority Moves",
            kind="action_list",
            items=_move_rows(moves),
        ),
        ReportExportSection(
            id="mastering_chain",
            title="Recommended Mastering Chain",
            kind="ordered_chain",
            items=[
                f"Chain type: {mastering_chain.chain_type}.",
                *[
                    f"{index}. {step}."
                    for index, step in enumerate(mastering_chain.recommended_chain, start=1)
                ],
                *([f"Warning: {mastering_chain.warning}"] if mastering_chain.warning else []),
            ],
        ),
        ReportExportSection(
            id="translation_checks",
            title="Translation Checks",
            kind="notes",
            items=[
                f"Club: {mix_translation.club_translation}",
                f"Phone: {mix_translation.phone_translation}",
                f"Car: {mix_translation.car_translation}",
                f"Mono: {mix_translation.mono_translation}",
            ],
        ),
        ReportExportSection(
            id="warnings_and_limits",
            title="Warnings & Limitations",
            kind="disclosure",
            items=[
                *[
                    f"{warning.severity}: {warning.message}"
                    for warning in warnings
                ],
                *limitations,
            ],
        ),
    ]
    return ReportExportLayout(
        layout_version="export-layout-0.1.0",
        format="single_page_sections",
        title="Sonic AI Engineering Report",
        subtitle=f"Target profile: {context.target_profile or 'unspecified'}",
        section_order=[section.id for section in sections],
        sections=sections,
    )


def _metric_rows(context: _ReportContext) -> list[str]:
    rows = [
        _metric_row(context, "Integrated loudness", "integrated_lufs", "LUFS", precision=2),
        _metric_row(context, "True peak", "true_peak_dbfs", "dBFS", precision=2),
        _metric_row(context, "Crest factor", "crest_factor_db", "dB", precision=2),
        _metric_row(context, "Dynamic range", "dynamic_range_db", "dB", precision=2),
        _metric_row(context, "Stereo correlation", "stereo_correlation", "", precision=3),
        _metric_row(context, "Sub ratio", "sub_band_ratio", "", precision=3),
        _metric_row(context, "Bass ratio", "bass_band_ratio", "", precision=3),
        _metric_row(context, "High-mid ratio", "high_mid_band_ratio", "", precision=3),
        _metric_row(context, "High ratio", "high_band_ratio", "", precision=3),
    ]
    return [row for row in rows if row is not None] or ["Measured metrics were unavailable."]


def _metric_row(
    context: _ReportContext,
    label: str,
    metric_name: str,
    unit: str,
    precision: int,
) -> str | None:
    value = context.metric(metric_name)
    if value is None:
        return None
    suffix = f" {unit}" if unit else ""
    return f"{label}: {value:.{precision}f}{suffix}."


def _move_rows(moves: list[ReportMove]) -> list[str]:
    return [
        f"{move.severity}: {move.title} - {move.action}"
        for move in moves
    ] or ["No priority corrective moves detected by deterministic rules."]


def _missing_metric_warnings(context: _ReportContext) -> list[ReportWarning]:
    warnings: list[ReportWarning] = []
    for metric_name in IMPORTANT_METRICS:
        if context.metric(metric_name) is None:
            warnings.append(
                ReportWarning(
                    code=f"missing_{metric_name}",
                    message=(
                        f"Metric '{metric_name}' is unavailable; related scoring is lower "
                        "confidence."
                    ),
                    severity="minor",
                )
            )
    return warnings


def _technical_warnings(context: _ReportContext) -> list[ReportWarning]:
    warnings: list[ReportWarning] = []
    correlation = context.metric("stereo_correlation")
    if correlation is not None and correlation < 0.2:
        warnings.append(
            ReportWarning(
                code="unsafe_stereo_correlation",
                message="Stereo correlation is low enough to require mono compatibility review.",
                severity="critical" if correlation < 0.0 else "major",
            )
        )
    true_peak = context.metric("true_peak_dbfs", "true_peak_db", "true_peak")
    if true_peak is not None and true_peak >= -0.3:
        warnings.append(
            ReportWarning(
                code="hot_true_peak",
                message=(
                    "True peak is close to full scale and may create codec or limiter "
                    "artifacts."
                ),
                severity="critical",
            )
        )
    return warnings


def _confidence(context: _ReportContext, warnings: list[ReportWarning]) -> Confidence:
    missing_count = sum(1 for warning in warnings if warning.code.startswith("missing_"))
    if missing_count >= 4 or not context.metrics:
        return "low"
    if missing_count or context.profile_severity() == "none" and not context.deltas:
        return "medium"
    return "high"


def _limitations(context: _ReportContext, target_profile: str | None) -> list[str]:
    limitations = [
        "Report is generated from deterministic audio metrics and fixed rule templates only.",
        "Recommendations are engineering checks, not a replacement for level-matched listening.",
    ]
    if not target_profile and not context.target_profile:
        limitations.append("No explicit target profile was supplied to the report builder.")
    if not context.comparison:
        limitations.append("Reference-profile comparison data was unavailable.")
    return limitations


def _apply_delta_penalty(score: int, context: _ReportContext, metric_names: tuple[str, ...]) -> int:
    penalty = 0
    for metric_name in metric_names:
        delta = context.delta(metric_name)
        if not delta:
            continue
        severity = _string_value(delta.get("severity"))
        penalty += {"low": 5, "medium": 12, "high": 22}.get(severity, 0)
    return _bounded_score(score - penalty)


def _bounded_score(score: int | float) -> int:
    return max(0, min(100, int(round(score))))


def _number_from_path(source: dict[str, Any], *path: str) -> float | None:
    current: Any = source
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    if isinstance(current, bool) or current is None:
        return None
    try:
        value = float(current)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(value):
        return None
    return value


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _string_value(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


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

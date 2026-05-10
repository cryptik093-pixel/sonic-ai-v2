from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.engineering_report import build_engineering_report
from app.audio.loader import LoadedAudio, load_audio_file
from app.audio.metrics import AudioMetrics, calculate_basic_metrics
from app.audio.reference_profiles import ReferenceComparison, compare_metrics_to_profile
from app.models.analysis_models import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisWarning,
    ReferenceProfile,
)

ENGINE_VERSION = "sonic-ai-v2-analysis-core-0.1.0"


@dataclass(frozen=True)
class SonicAnalysisResult:
    engine_version: str
    filename: str
    profile_id: str
    metrics: AudioMetrics
    reference_comparison: ReferenceComparison
    engineering_report: dict[str, Any]


class AnalysisServiceError(Exception):
    """Raised when the analyzer service cannot produce a real analysis result."""


class AnalyzerService:
    """Coordinates audio analysis without faking unavailable DSP work."""

    def analyze(self, request: AnalysisRequest) -> AnalysisResponse:
        return AnalysisResponse(
            status="not_implemented",
            analysis_id=None,
            message="Audio analysis is not implemented yet. No audio was analyzed.",
            input=request,
            metrics=None,
            reference_profile=ReferenceProfile(
                id="balanced_streaming",
                name="Balanced Streaming",
                description=(
                    "General-purpose streaming delivery target for balanced modern music releases."
                ),
            ),
            warnings=[
                AnalysisWarning(
                    code="analysis_not_implemented",
                    message=(
                        "The endpoint contract is active, but deterministic audio analysis "
                        "has not been built yet."
                    ),
                )
            ],
        )

    def analyze_loaded_audio(
        self,
        audio: LoadedAudio,
        profile_id: str = "modern_hiphop_master",
    ) -> SonicAnalysisResult:
        if not isinstance(audio, LoadedAudio):
            raise AnalysisServiceError("audio must be a LoadedAudio instance.")

        metrics = calculate_basic_metrics(audio)
        reference_comparison = compare_metrics_to_profile(metrics, profile_id)
        base_analysis = _to_plain_python(
            {
                "profile_id": profile_id,
                "metrics": metrics,
                "reference_comparison": reference_comparison,
            }
        )
        engineering_report = build_engineering_report(base_analysis, target_profile=profile_id)
        return SonicAnalysisResult(
            engine_version=ENGINE_VERSION,
            filename=audio.filename,
            profile_id=profile_id,
            metrics=metrics,
            reference_comparison=reference_comparison,
            engineering_report=engineering_report,
        )

    def analyze_file_path(
        self,
        path: str | Path,
        profile_id: str = "modern_hiphop_master",
    ) -> SonicAnalysisResult:
        audio = load_audio_file(str(path))
        return self.analyze_loaded_audio(audio=audio, profile_id=profile_id)


def analysis_result_to_dict(result: SonicAnalysisResult) -> dict[str, Any]:
    if not isinstance(result, SonicAnalysisResult):
        raise AnalysisServiceError("result must be a SonicAnalysisResult instance.")
    return _to_plain_python(result)


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
    if isinstance(value, np.ndarray):
        return [_to_plain_python(item) for item in value.tolist()]
    return value

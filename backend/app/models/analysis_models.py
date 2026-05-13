from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AnalysisSource(BaseModel):
    kind: Literal["not_uploaded_yet"] = "not_uploaded_yet"


class AnalysisOptions(BaseModel):
    target_profile: str = Field(default="modern_hiphop_master", min_length=1)


class AnalysisRequest(BaseModel):
    source: AnalysisSource
    options: AnalysisOptions = Field(default_factory=AnalysisOptions)


class ReferenceProfile(BaseModel):
    id: str
    name: str
    description: str


class AnalysisWarning(BaseModel):
    code: str
    message: str


class AnalysisMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration_seconds: float
    sample_rate_hz: int
    channel_count: int
    peak_dbfs: float
    integrated_lufs: float | None = None


class AnalysisResponse(BaseModel):
    status: Literal["complete", "not_implemented", "error"]
    analysis_id: str | None
    message: str
    input: AnalysisRequest
    metrics: AnalysisMetrics | None
    reference_profile: ReferenceProfile
    warnings: list[AnalysisWarning] = Field(default_factory=list)


class APIErrorDetail(BaseModel):
    code: str
    message: str


class APIErrorResponse(BaseModel):
    status: Literal["error"] = "error"
    error: APIErrorDetail


class AnalyzeSuccessResponse(BaseModel):
    status: Literal["completed"] = "completed"
    analysis: dict[str, Any]

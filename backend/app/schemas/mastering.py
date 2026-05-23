from __future__ import annotations

from pydantic import BaseModel, Field


class MasterAudioJsonResponse(BaseModel):
    status: str = Field(..., example="completed")
    byte_length: int
    media_type: str = Field(default="audio/wav")
    encoding: str = Field(default="base64")
    data_base64: str

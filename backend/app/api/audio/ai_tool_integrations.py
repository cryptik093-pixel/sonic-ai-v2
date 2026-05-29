from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

IntegrationStatus = Literal["active", "approved_optional", "deferred", "sandbox_only", "blocked"]
IntegrationDomain = Literal[
    "symbolic_generation",
    "realtime_composition",
    "audio_analysis",
    "audio_editing",
    "ml_training",
    "raw_audio_generation",
    "external_api",
]


@dataclass(frozen=True)
class MusicAIToolIntegration:
    """Compatibility decision for a music AI tool in Sonic AI V2.

    The catalog is intentionally code-owned so dependency decisions stay
    testable and do not drift into random package installs.
    """

    tool_id: str
    display_name: str
    domain: IntegrationDomain
    status: IntegrationStatus
    package_name: str | None
    install_extra: str | None
    reason: str
    sonic_ai_use: str


MUSIC_AI_TOOL_INTEGRATIONS: tuple[MusicAIToolIntegration, ...] = (
    MusicAIToolIntegration(
        tool_id="librosa",
        display_name="Librosa",
        domain="audio_analysis",
        status="active",
        package_name="librosa",
        install_extra=None,
        reason="Already part of the backend dependency set for deterministic feature extraction.",
        sonic_ai_use="Tempo, pitch, spectral, and analysis support around uploaded audio.",
    ),
    MusicAIToolIntegration(
        tool_id="muspy",
        display_name="MusPy",
        domain="symbolic_generation",
        status="approved_optional",
        package_name="muspy",
        install_extra="music-lab",
        reason=(
            "Useful for symbolic music datasets and MIDI/MusicXML workflows "
            "without changing the core API."
        ),
        sonic_ai_use=(
            "Offline composition experiments, MIDI dataset import/export, and "
            "future symbolic evaluation."
        ),
    ),
    MusicAIToolIntegration(
        tool_id="scamp",
        display_name="SCAMP",
        domain="realtime_composition",
        status="approved_optional",
        package_name="scamp",
        install_extra="music-lab",
        reason=(
            "Python 3.12 compatible and useful for local/live algorithmic "
            "composition experiments."
        ),
        sonic_ai_use=(
            "Local playback sketches and future real-time composition prototypes "
            "outside request handlers."
        ),
    ),
    MusicAIToolIntegration(
        tool_id="pydub",
        display_name="pydub",
        domain="audio_editing",
        status="approved_optional",
        package_name="pydub",
        install_extra="music-lab",
        reason=(
            "Small optional utility for offline slicing and simple audio edits; "
            "requires ffmpeg for many formats."
        ),
        sonic_ai_use=(
            "Developer tools for audio fixture preparation and future non-core "
            "editing utilities."
        ),
    ),
    MusicAIToolIntegration(
        tool_id="torchaudio",
        display_name="torchaudio",
        domain="ml_training",
        status="deferred",
        package_name="torchaudio",
        install_extra=None,
        reason="Heavy ML dependency that should be isolated from the production FastAPI runtime.",
        sonic_ai_use="Future model-training sandbox only, paired with a pinned torch stack.",
    ),
    MusicAIToolIntegration(
        tool_id="tensorflow",
        display_name="TensorFlow",
        domain="ml_training",
        status="deferred",
        package_name="tensorflow",
        install_extra=None,
        reason=(
            "Heavy ML runtime; not needed for the deterministic analyzer or "
            "current MIDI engine."
        ),
        sonic_ai_use="Future offline model-training research, not request-time generation.",
    ),
    MusicAIToolIntegration(
        tool_id="essentia",
        display_name="Essentia",
        domain="audio_analysis",
        status="deferred",
        package_name="essentia",
        install_extra=None,
        reason=(
            "Powerful MIR library, but binary wheel/platform support must be "
            "verified before adding to Windows V2."
        ),
        sonic_ai_use="Future MIR comparison after a dedicated install/runtime proof.",
    ),
    MusicAIToolIntegration(
        tool_id="magenta",
        display_name="Magenta",
        domain="symbolic_generation",
        status="sandbox_only",
        package_name="magenta",
        install_extra=None,
        reason=(
            "Current package pins older dependencies that conflict with Sonic AI "
            "V2's Python 3.12/librosa stack."
        ),
        sonic_ai_use=(
            "Keep as a quarantined research sandbox; do not import it in the "
            "FastAPI runtime."
        ),
    ),
    MusicAIToolIntegration(
        tool_id="musenet",
        display_name="MuseNet API",
        domain="external_api",
        status="blocked",
        package_name=None,
        install_extra=None,
        reason=(
            "Not a local Python package and not a stable Sonic AI V2 backend "
            "dependency."
        ),
        sonic_ai_use="Do not wire into V2 production flows.",
    ),
    MusicAIToolIntegration(
        tool_id="riffusion",
        display_name="Riffusion",
        domain="raw_audio_generation",
        status="deferred",
        package_name=None,
        install_extra=None,
        reason=(
            "Model/server integration is larger than a Python library install "
            "and needs a separate GPU plan."
        ),
        sonic_ai_use=(
            "Future sandbox for text-to-audio experiments, not current "
            "deterministic MIDI generation."
        ),
    ),
    MusicAIToolIntegration(
        tool_id="jukebox",
        display_name="Jukebox",
        domain="raw_audio_generation",
        status="blocked",
        package_name=None,
        install_extra=None,
        reason="Large legacy raw-audio model stack unsuitable for the production V2 runtime.",
        sonic_ai_use="Do not integrate into the main app.",
    ),
)


def list_music_ai_integrations(
    status: IntegrationStatus | None = None,
) -> tuple[MusicAIToolIntegration, ...]:
    if status is None:
        return MUSIC_AI_TOOL_INTEGRATIONS
    return tuple(tool for tool in MUSIC_AI_TOOL_INTEGRATIONS if tool.status == status)


def get_music_ai_integration(tool_id: str) -> MusicAIToolIntegration:
    normalized = tool_id.strip().lower().replace(" ", "_")
    for tool in MUSIC_AI_TOOL_INTEGRATIONS:
        if tool.tool_id == normalized:
            return tool
    raise KeyError(f"Unknown music AI integration: {tool_id!r}")

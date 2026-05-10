from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".wave", ".flac", ".aiff", ".aif", ".mp3", ".ogg"}


class AudioLoadError(Exception):
    """Raised when an audio file cannot be loaded into a valid deterministic shape."""


@dataclass(frozen=True)
class LoadedAudio:
    samples: np.ndarray
    sample_rate_hz: int
    channels: int
    frames: int
    duration_seconds: float
    peak_abs: float
    filename: str


def load_audio_file(path: str) -> LoadedAudio:
    audio_path = Path(path)
    _validate_path(audio_path)

    try:
        samples, sample_rate_hz = sf.read(audio_path, always_2d=True, dtype="float32")
    except Exception as exc:
        raise AudioLoadError(f"Could not load audio file '{audio_path.name}'.") from exc

    samples = np.asarray(samples, dtype=np.float32)
    np.nan_to_num(samples, copy=False, nan=0.0, posinf=0.0, neginf=0.0)

    _validate_loaded_audio(samples=samples, sample_rate_hz=sample_rate_hz, filename=audio_path.name)

    frames = int(samples.shape[0])
    channels = int(samples.shape[1])
    return LoadedAudio(
        samples=samples,
        sample_rate_hz=int(sample_rate_hz),
        channels=channels,
        frames=frames,
        duration_seconds=float(frames / sample_rate_hz),
        peak_abs=float(np.max(np.abs(samples))),
        filename=audio_path.name,
    )


def _validate_path(path: Path) -> None:
    if not path.exists():
        raise AudioLoadError(f"Audio file does not exist: '{path}'.")
    if not path.is_file():
        raise AudioLoadError(f"Audio path is not a file: '{path}'.")
    if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
        allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS))
        raise AudioLoadError(
            f"Unsupported audio file extension '{path.suffix}'. Allowed: {allowed}."
        )


def _validate_loaded_audio(samples: np.ndarray, sample_rate_hz: int, filename: str) -> None:
    if sample_rate_hz <= 0:
        raise AudioLoadError(f"Audio file '{filename}' has an invalid sample rate.")
    if samples.ndim != 2:
        raise AudioLoadError(f"Audio file '{filename}' did not load as a 2D array.")
    if samples.shape[0] < 1:
        raise AudioLoadError(f"Audio file '{filename}' contains no audio frames.")
    if samples.shape[1] < 1:
        raise AudioLoadError(f"Audio file '{filename}' contains no audio channels.")

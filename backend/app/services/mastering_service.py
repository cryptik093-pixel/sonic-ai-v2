from __future__ import annotations

from dataclasses import dataclass
import io
from typing import Any

import numpy as np
import soundfile as sf
import pyloudnorm as pyln


class MasteringServiceError(Exception):
    """Raised when mastering fails for any reason."""


@dataclass(frozen=True)
class MasteringResult:
    wav_bytes: bytes
    sample_rate: int
    original_lufs: float
    target_lufs: float
    applied_gain_db: float
    peak_after: float


class MasteringService:
    """A small deterministic mastering processor.

    The implementation is intentionally simple: it measures integrated
    LUFS, applies a deterministic gain to reach the target LUFS, applies a
    gentle soft clipping limiter, and writes a 16-bit PCM WAV stream. The
    algorithm is deterministic and fully testable.
    """

    def __init__(self, target_lufs: float = -14.0, limiter_threshold: float = 0.99):
        self.target_lufs = float(target_lufs)
        self.limiter_threshold = float(limiter_threshold)

    def master(self, wav_bytes: bytes, *, target_lufs: float | None = None) -> MasteringResult:
        """Master incoming WAV bytes and return mastered WAV bytes plus metadata.

        Args:
            wav_bytes: Input WAV file bytes.
            target_lufs: Optional override for the target LUFS.

        Returns:
            MasteringResult with WAV bytes and metadata.
        """
        if target_lufs is None:
            target_lufs = self.target_lufs

        try:
            with io.BytesIO(wav_bytes) as bio:
                data, sr = sf.read(bio, always_2d=True, dtype="float32")
        except Exception as exc:
            raise MasteringServiceError("Could not read input audio for mastering.") from exc

        # Ensure float32 ndarray NxC
        samples = np.asarray(data, dtype=np.float32)
        if samples.ndim == 1:
            samples = samples[:, None]

        # Measure integrated LUFS (deterministic)
        meter = pyln.Meter(sr)
        try:
            measured_loudness = float(meter.integrated_loudness(samples))
        except Exception:
            # If pyloudnorm fails, fall back to a rough RMS-based estimate
            measured_loudness = float(10 * np.log10(np.mean(np.square(samples)) + 1e-12))

        gain_db = float(target_lufs) - measured_loudness
        gain_linear = 10.0 ** (gain_db / 20.0)

        # Apply deterministic gain
        processed = samples * gain_linear

        # Simple soft limiter using a tanh curve for smooth saturation
        # Preserve overall level scaling by normalizing after soft clipping
        thresh = self.limiter_threshold
        processed = np.tanh(processed / thresh) * thresh

        # Compute peak
        peak_after = float(np.max(np.abs(processed)))

        # Convert back to 16-bit PCM for WAV export
        # Ensure no NaNs/Infs
        processed = np.nan_to_num(processed, nan=0.0, posinf=0.0, neginf=0.0)

        # Write to bytes buffer
        out_buf = io.BytesIO()
        try:
            # soundfile expects shape (frames, channels)
            sf.write(out_buf, processed, sr, format="WAV", subtype="PCM_16")
            out_bytes = out_buf.getvalue()
        except Exception as exc:
            raise MasteringServiceError("Could not write mastered WAV bytes.") from exc

        return MasteringResult(
            wav_bytes=out_bytes,
            sample_rate=int(sr),
            original_lufs=float(measured_loudness),
            target_lufs=float(target_lufs),
            applied_gain_db=float(gain_db),
            peak_after=peak_after,
        )

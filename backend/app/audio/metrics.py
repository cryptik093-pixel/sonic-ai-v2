from dataclasses import dataclass

import numpy as np
import pyloudnorm as pyln
from scipy.signal import resample_poly

from app.audio.loader import LoadedAudio

DBFS_FLOOR = -120.0
CLIPPING_THRESHOLD = 0.999
TRUE_PEAK_OVERSAMPLE_FACTOR = 4
TRUE_PEAK_EDGE_PAD_FRAMES = 32
SHORT_TERM_LOUDNESS_WINDOW_SECONDS = 3.0
DYNAMIC_RANGE_WINDOW_SECONDS = 0.4
DYNAMIC_RANGE_LOWER_PERCENTILE = 10.0
DYNAMIC_RANGE_UPPER_PERCENTILE = 95.0


@dataclass(frozen=True)
class AudioMetrics:
    duration_seconds: float
    sample_rate_hz: int
    channels: int
    frames: int
    peak_abs: float
    peak_dbfs: float
    integrated_lufs: float
    short_term_lufs: float
    true_peak_abs: float
    true_peak_dbfs: float
    rms: float
    rms_dbfs: float
    crest_factor: float
    crest_factor_db: float
    dynamic_range_db: float
    clipping_sample_count: int
    clipping_ratio: float
    clipping_risk: str
    stereo_balance: float
    stereo_correlation: float
    mid_energy: float
    side_energy: float
    side_energy_ratio: float
    stereo_width: float
    spectral_centroid_hz: float
    low_band_ratio: float
    mid_band_ratio: float
    high_band_ratio: float
    harsh_band_ratio: float
    sub_band_ratio: float
    bass_band_ratio: float
    low_mid_band_ratio: float
    high_mid_band_ratio: float
    low_end_profile: str
    stereo_profile: str
    harshness_profile: str
    loudness_profile: str
    true_peak_risk: str


def calculate_basic_metrics(audio: LoadedAudio) -> AudioMetrics:
    _validate_loaded_audio(audio)

    samples = audio.samples
    peak_abs = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))
    peak_dbfs = _safe_dbfs(peak_abs)
    integrated_lufs = _integrated_lufs(
        samples=samples,
        sample_rate_hz=audio.sample_rate_hz,
        rms=rms,
    )
    short_term_lufs = _short_term_lufs(
        samples=samples,
        sample_rate_hz=audio.sample_rate_hz,
        integrated_lufs=integrated_lufs,
        rms=rms,
    )
    true_peak_abs = _true_peak_abs(samples)
    true_peak_dbfs = _safe_dbfs(true_peak_abs)
    rms_dbfs = _safe_dbfs(rms)
    total_sample_count = int(samples.size)
    clipping_sample_count = int(np.count_nonzero(np.abs(samples) >= CLIPPING_THRESHOLD))
    clipping_ratio = float(clipping_sample_count / total_sample_count)
    stereo_metrics = _stereo_metrics(samples)
    spectral_metrics = _spectral_metrics(
        samples=samples,
        sample_rate_hz=audio.sample_rate_hz,
        rms=rms,
    )

    return AudioMetrics(
        duration_seconds=float(audio.duration_seconds),
        sample_rate_hz=int(audio.sample_rate_hz),
        channels=int(audio.channels),
        frames=int(audio.frames),
        peak_abs=peak_abs,
        peak_dbfs=peak_dbfs,
        integrated_lufs=integrated_lufs,
        short_term_lufs=short_term_lufs,
        true_peak_abs=true_peak_abs,
        true_peak_dbfs=true_peak_dbfs,
        rms=rms,
        rms_dbfs=rms_dbfs,
        crest_factor=float(peak_abs / rms) if rms > 0.0 else 0.0,
        crest_factor_db=float(peak_dbfs - rms_dbfs),
        dynamic_range_db=_dynamic_range_db(
            samples=samples,
            sample_rate_hz=audio.sample_rate_hz,
            rms=rms,
        ),
        clipping_sample_count=clipping_sample_count,
        clipping_ratio=clipping_ratio,
        clipping_risk=_clipping_risk(clipping_ratio),
        stereo_balance=stereo_metrics["stereo_balance"],
        stereo_correlation=stereo_metrics["stereo_correlation"],
        mid_energy=stereo_metrics["mid_energy"],
        side_energy=stereo_metrics["side_energy"],
        side_energy_ratio=stereo_metrics["side_energy_ratio"],
        stereo_width=stereo_metrics["stereo_width"],
        spectral_centroid_hz=spectral_metrics["spectral_centroid_hz"],
        low_band_ratio=spectral_metrics["low_band_ratio"],
        mid_band_ratio=spectral_metrics["mid_band_ratio"],
        high_band_ratio=spectral_metrics["high_band_ratio"],
        harsh_band_ratio=spectral_metrics["harsh_band_ratio"],
        sub_band_ratio=spectral_metrics["sub_band_ratio"],
        bass_band_ratio=spectral_metrics["bass_band_ratio"],
        low_mid_band_ratio=spectral_metrics["low_mid_band_ratio"],
        high_mid_band_ratio=spectral_metrics["high_mid_band_ratio"],
        low_end_profile=_low_end_profile(
            sub_band_ratio=spectral_metrics["sub_band_ratio"],
            low_band_ratio=spectral_metrics["low_band_ratio"],
            rms=rms,
        ),
        stereo_profile=stereo_metrics["stereo_profile"],
        harshness_profile=_harshness_profile(
            harsh_band_ratio=spectral_metrics["harsh_band_ratio"],
            rms=rms,
        ),
        loudness_profile=_loudness_profile(integrated_lufs=integrated_lufs, rms=rms),
        true_peak_risk=_true_peak_risk(true_peak_dbfs),
    )


def _safe_dbfs(value: float) -> float:
    if not np.isfinite(value) or value <= 0.0:
        return DBFS_FLOOR
    return float(20.0 * np.log10(value))


def _integrated_lufs(samples: np.ndarray, sample_rate_hz: int, rms: float) -> float:
    if rms <= 0.0:
        return DBFS_FLOOR

    meter = pyln.Meter(sample_rate_hz)
    try:
        integrated_lufs = float(meter.integrated_loudness(samples))
    except ValueError:
        return DBFS_FLOOR

    if not np.isfinite(integrated_lufs):
        return DBFS_FLOOR
    return integrated_lufs


def _short_term_lufs(
    samples: np.ndarray,
    sample_rate_hz: int,
    integrated_lufs: float,
    rms: float,
) -> float:
    """Return the loudest 3-second loudness window, falling back for short clips."""
    if rms <= 0.0:
        return DBFS_FLOOR

    window_frames = int(sample_rate_hz * SHORT_TERM_LOUDNESS_WINDOW_SECONDS)
    if samples.shape[0] < window_frames:
        return integrated_lufs

    hop_frames = max(1, window_frames // 2)
    meter = pyln.Meter(sample_rate_hz)
    loudness_values: list[float] = []
    for start in range(0, samples.shape[0] - window_frames + 1, hop_frames):
        window = samples[start : start + window_frames]
        window_rms = float(np.sqrt(np.mean(np.square(window, dtype=np.float64))))
        if window_rms <= 0.0:
            continue
        try:
            loudness = float(meter.integrated_loudness(window))
        except ValueError:
            continue
        if np.isfinite(loudness):
            loudness_values.append(loudness)

    return max(loudness_values) if loudness_values else integrated_lufs


def _true_peak_abs(samples: np.ndarray) -> float:
    if not np.any(samples):
        return 0.0

    pad_frames = min(TRUE_PEAK_EDGE_PAD_FRAMES, samples.shape[0])
    padded_samples = np.pad(
        samples.astype(np.float64, copy=False),
        pad_width=((pad_frames, pad_frames), (0, 0)),
        mode="edge",
    )
    oversampled = resample_poly(
        padded_samples,
        up=TRUE_PEAK_OVERSAMPLE_FACTOR,
        down=1,
        axis=0,
    )
    crop_start = pad_frames * TRUE_PEAK_OVERSAMPLE_FACTOR
    crop_end = crop_start + (samples.shape[0] * TRUE_PEAK_OVERSAMPLE_FACTOR)
    oversampled = oversampled[crop_start:crop_end]
    true_peak = float(np.max(np.abs(oversampled)))
    if not np.isfinite(true_peak):
        return 0.0
    return true_peak


def _dynamic_range_db(samples: np.ndarray, sample_rate_hz: int, rms: float) -> float:
    """Estimate macro dynamic range from short-window RMS percentile spread."""
    if rms <= 0.0:
        return 0.0

    mono = np.mean(samples.astype(np.float64, copy=False), axis=1)
    window_frames = max(1, int(sample_rate_hz * DYNAMIC_RANGE_WINDOW_SECONDS))
    hop_frames = max(1, window_frames // 2)
    rms_db_values: list[float] = []
    for start in range(0, mono.size - window_frames + 1, hop_frames):
        window = mono[start : start + window_frames]
        window_rms = float(np.sqrt(np.mean(np.square(window))))
        if window_rms > 0.0:
            rms_db_values.append(_safe_dbfs(window_rms))

    if not rms_db_values:
        return 0.0

    upper = float(np.percentile(rms_db_values, DYNAMIC_RANGE_UPPER_PERCENTILE))
    lower = float(np.percentile(rms_db_values, DYNAMIC_RANGE_LOWER_PERCENTILE))
    return _finite_or_zero(max(0.0, upper - lower))


def _clipping_risk(clipping_ratio: float) -> str:
    if clipping_ratio == 0.0:
        return "none"
    if clipping_ratio <= 0.0001:
        return "low"
    if clipping_ratio <= 0.001:
        return "medium"
    return "high"


def _stereo_metrics(samples: np.ndarray) -> dict[str, float | str]:
    if samples.shape[1] == 1:
        return {
            "stereo_balance": 0.0,
            "stereo_correlation": 1.0,
            "mid_energy": float(np.mean(np.square(samples[:, 0], dtype=np.float64))),
            "side_energy": 0.0,
            "side_energy_ratio": 0.0,
            "stereo_width": 0.0,
            "stereo_profile": "mono",
        }

    left = samples[:, 0].astype(np.float64, copy=False)
    right = samples[:, 1].astype(np.float64, copy=False)
    stereo_balance = float(np.mean(np.abs(left)) - np.mean(np.abs(right)))
    stereo_correlation = _stereo_correlation(left=left, right=right)
    mid = (left + right) / 2.0
    side = (left - right) / 2.0
    mid_energy = float(np.mean(np.square(mid)))
    side_energy = float(np.mean(np.square(side)))
    total_energy = mid_energy + side_energy
    side_energy_ratio = float(side_energy / total_energy) if total_energy > 0.0 else 0.0
    stereo_width = _stereo_width(mid_energy=mid_energy, side_energy=side_energy)

    return {
        "stereo_balance": stereo_balance,
        "stereo_correlation": stereo_correlation,
        "mid_energy": mid_energy,
        "side_energy": side_energy,
        "side_energy_ratio": side_energy_ratio,
        "stereo_width": stereo_width,
        "stereo_profile": _stereo_profile(stereo_balance, side_energy_ratio),
    }


def _stereo_width(mid_energy: float, side_energy: float) -> float:
    """Return side-to-mid energy ratio as a bounded practical width estimate."""
    if mid_energy <= 0.0:
        return 1.0 if side_energy > 0.0 else 0.0
    return _finite_or_zero(float(np.sqrt(side_energy / mid_energy)))


def _stereo_correlation(left: np.ndarray, right: np.ndarray) -> float:
    if not np.any(left) and not np.any(right):
        return 1.0
    if np.allclose(left, right):
        return 1.0
    if np.allclose(left, -right):
        return -1.0

    left_std = float(np.std(left))
    right_std = float(np.std(right))
    if left_std <= 0.0 or right_std <= 0.0:
        return 0.0

    correlation = float(np.corrcoef(left, right)[0, 1])
    if not np.isfinite(correlation):
        return 0.0
    return correlation


def _stereo_profile(stereo_balance: float, side_energy_ratio: float) -> str:
    if stereo_balance >= 0.03:
        return "left_heavy"
    if stereo_balance <= -0.03:
        return "right_heavy"
    if abs(stereo_balance) < 0.03 and side_energy_ratio < 0.20:
        return "centered"
    if side_energy_ratio < 0.45:
        return "wide"
    return "very_wide"


def _spectral_metrics(
    samples: np.ndarray,
    sample_rate_hz: int,
    rms: float,
) -> dict[str, float]:
    if rms <= 0.0:
        return {
            "spectral_centroid_hz": 0.0,
            "sub_band_ratio": 0.0,
            "low_band_ratio": 0.0,
            "mid_band_ratio": 0.0,
            "high_band_ratio": 0.0,
            "harsh_band_ratio": 0.0,
            "bass_band_ratio": 0.0,
            "low_mid_band_ratio": 0.0,
            "high_mid_band_ratio": 0.0,
        }

    mono = np.mean(samples.astype(np.float64, copy=False), axis=1)
    spectrum = np.fft.rfft(mono)
    power = np.square(np.abs(spectrum))
    frequencies = np.fft.rfftfreq(mono.size, d=1.0 / sample_rate_hz)
    total_power = float(np.sum(power))
    if total_power <= 0.0 or not np.isfinite(total_power):
        return {
            "spectral_centroid_hz": 0.0,
            "sub_band_ratio": 0.0,
            "low_band_ratio": 0.0,
            "mid_band_ratio": 0.0,
            "high_band_ratio": 0.0,
            "harsh_band_ratio": 0.0,
            "bass_band_ratio": 0.0,
            "low_mid_band_ratio": 0.0,
            "high_mid_band_ratio": 0.0,
        }

    spectral_centroid_hz = float(np.sum(frequencies * power) / total_power)
    return {
        "spectral_centroid_hz": _finite_or_zero(spectral_centroid_hz),
        "sub_band_ratio": _band_ratio(frequencies, power, total_power, 20.0, 60.0),
        "bass_band_ratio": _band_ratio(frequencies, power, total_power, 60.0, 250.0),
        "low_mid_band_ratio": _band_ratio(frequencies, power, total_power, 250.0, 2000.0),
        "high_mid_band_ratio": _band_ratio(frequencies, power, total_power, 2000.0, 6000.0),
        "low_band_ratio": _band_ratio(frequencies, power, total_power, 60.0, 250.0),
        "mid_band_ratio": _band_ratio(frequencies, power, total_power, 250.0, 4000.0),
        "high_band_ratio": _band_ratio(
            frequencies,
            power,
            total_power,
            4000.0,
            sample_rate_hz / 2.0,
        ),
        "harsh_band_ratio": _band_ratio(frequencies, power, total_power, 2500.0, 6000.0),
    }


def _band_ratio(
    frequencies: np.ndarray,
    power: np.ndarray,
    total_power: float,
    low_hz: float,
    high_hz: float,
) -> float:
    band = (frequencies >= low_hz) & (frequencies < high_hz)
    if not np.any(band):
        return 0.0
    return _finite_or_zero(float(np.sum(power[band]) / total_power))


def _finite_or_zero(value: float) -> float:
    if not np.isfinite(value):
        return 0.0
    return float(value)


def _low_end_profile(sub_band_ratio: float, low_band_ratio: float, rms: float) -> str:
    if rms == 0.0:
        return "silent"
    low_end_ratio = sub_band_ratio + low_band_ratio
    if low_end_ratio < 0.10:
        return "thin"
    if low_end_ratio < 0.35:
        return "balanced"
    return "heavy"


def _harshness_profile(harsh_band_ratio: float, rms: float) -> str:
    if rms == 0.0:
        return "silent"
    if harsh_band_ratio < 0.10:
        return "smooth"
    if harsh_band_ratio < 0.25:
        return "present"
    return "harsh"


def _loudness_profile(integrated_lufs: float, rms: float) -> str:
    if rms == 0.0:
        return "silent"
    if integrated_lufs < -24.0:
        return "very_quiet"
    if integrated_lufs < -12.0:
        return "streaming_safe"
    if integrated_lufs < -8.0:
        return "loud_master"
    return "aggressive_master"


def _true_peak_risk(true_peak_dbfs: float) -> str:
    if true_peak_dbfs < -1.0:
        return "none"
    if true_peak_dbfs < -0.3:
        return "watch"
    return "high"


def _validate_loaded_audio(audio: LoadedAudio) -> None:
    if audio.samples.ndim != 2:
        raise ValueError("samples must be a 2D array shaped (frames, channels)")
    if audio.sample_rate_hz <= 0:
        raise ValueError("sample_rate_hz must be positive")
    if audio.frames <= 0:
        raise ValueError("frames must be positive")
    if audio.channels <= 0:
        raise ValueError("channels must be positive")
    if audio.samples.shape != (audio.frames, audio.channels):
        raise ValueError("LoadedAudio metadata does not match sample shape")
    if not np.all(np.isfinite(audio.samples)):
        raise ValueError("samples must contain only finite values")

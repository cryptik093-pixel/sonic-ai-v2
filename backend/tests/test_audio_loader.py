from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from app.audio.loader import AudioLoadError, load_audio_file


def test_load_audio_file_returns_mono_as_frames_by_one_channel(tmp_path: Path) -> None:
    sample_rate_hz = 48_000
    samples = np.array([0.0, 0.5, -0.25], dtype=np.float32)
    path = tmp_path / "mono.wav"
    sf.write(path, samples, sample_rate_hz)

    loaded = load_audio_file(str(path))

    assert loaded.filename == "mono.wav"
    assert loaded.sample_rate_hz == sample_rate_hz
    assert loaded.samples.dtype == np.float32
    assert loaded.samples.shape == (3, 1)
    assert loaded.channels == 1
    assert loaded.frames == 3
    assert loaded.duration_seconds == 3 / sample_rate_hz
    assert loaded.peak_abs == pytest.approx(0.5, abs=1e-4)


def test_load_audio_file_returns_stereo_as_frames_by_two_channels(tmp_path: Path) -> None:
    sample_rate_hz = 44_100
    samples = np.array(
        [
            [0.0, 0.25],
            [0.5, -0.75],
            [-0.25, 0.125],
        ],
        dtype=np.float32,
    )
    path = tmp_path / "stereo.flac"
    sf.write(path, samples, sample_rate_hz)

    loaded = load_audio_file(str(path))

    assert loaded.filename == "stereo.flac"
    assert loaded.sample_rate_hz == sample_rate_hz
    assert loaded.samples.dtype == np.float32
    assert loaded.samples.shape == (3, 2)
    assert loaded.channels == 2
    assert loaded.frames == 3
    assert loaded.peak_abs == pytest.approx(0.75, abs=1e-4)


def test_load_audio_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(AudioLoadError, match="does not exist"):
        load_audio_file(str(tmp_path / "missing.wav"))


def test_load_audio_file_rejects_unsupported_extension(tmp_path: Path) -> None:
    path = tmp_path / "audio.txt"
    path.write_text("not audio", encoding="utf-8")

    with pytest.raises(AudioLoadError, match="Unsupported audio file extension"):
        load_audio_file(str(path))


def test_load_audio_file_wraps_soundfile_errors(tmp_path: Path) -> None:
    path = tmp_path / "corrupt.wav"
    path.write_bytes(b"not a valid wav")

    with pytest.raises(AudioLoadError, match="Could not load audio file 'corrupt.wav'"):
        load_audio_file(str(path))


def test_load_audio_file_rejects_non_finite_samples(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "malformed.wav"
    path.write_bytes(b"placeholder")

    def fake_read(*_args: object, **_kwargs: object) -> tuple[np.ndarray, int]:
        return np.array([[0.0], [np.nan], [np.inf]], dtype=np.float32), 48_000

    monkeypatch.setattr(sf, "read", fake_read)

    with pytest.raises(AudioLoadError, match="non-finite sample values"):
        load_audio_file(str(path))

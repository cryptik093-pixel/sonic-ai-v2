import io

import numpy as np
import soundfile as sf

from app.services.mastering_service import MasteringService


def generate_sine_wav_bytes(freq=440.0, duration=1.0, sr=44100, amp=0.1):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    samples = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    # stereo
    stereo = np.stack((samples, samples), axis=-1)
    buf = io.BytesIO()
    sf.write(buf, stereo, sr, format="WAV", subtype="PCM_16")
    return buf.getvalue()


def test_mastering_service_applies_gain_and_returns_wav_bytes():
    wav_bytes = generate_sine_wav_bytes()
    svc = MasteringService(target_lufs=-14.0)
    result = svc.master(wav_bytes)

    assert isinstance(result.wav_bytes, (bytes, bytearray))
    assert result.sample_rate == 44100
    assert isinstance(result.original_lufs, float)
    assert isinstance(result.applied_gain_db, float)
    # Check output is a WAV file
    assert result.wav_bytes[:4] == b"RIFF"

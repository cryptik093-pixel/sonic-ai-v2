import io

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from app.main import app


def generate_sine_wav_bytes(freq=440.0, duration=0.5, sr=44100, amp=0.1):
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    samples = (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)
    stereo = np.stack((samples, samples), axis=-1)
    buf = io.BytesIO()
    sf.write(buf, stereo, sr, format="WAV", subtype="PCM_16")
    buf.seek(0)
    return buf


client = TestClient(app)


def test_master_audio_route_streams_wav():
    wav_file = generate_sine_wav_bytes()
    files = {"file": ("sine.wav", wav_file, "audio/wav")}
    response = client.post("/api/v2/master-audio", files=files)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"

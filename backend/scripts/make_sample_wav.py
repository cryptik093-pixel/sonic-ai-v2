import numpy as np
import soundfile as sf
from pathlib import Path


def make_sine(path: Path, duration_s: float = 1.0, sr: int = 48000, freq: float = 440.0):
    t = np.linspace(0, duration_s, int(sr * duration_s), endpoint=False)
    samples = 0.25 * np.sin(2 * np.pi * freq * t)
    samples = samples.astype('float32')
    sf.write(str(path), samples, sr, format='WAV')


if __name__ == '__main__':
    out = Path(__file__).resolve().parents[1] / 'frontend' / 'test_sample.wav'
    out.parent.mkdir(parents=True, exist_ok=True)
    make_sine(out)
    print(f'Wrote sample WAV to: {out}')

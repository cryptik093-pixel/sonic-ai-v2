import numpy as np
import sounddevice as sd
from scipy.signal import find_peaks

sample_rate = 44100
block_size = 2048  # small chunk for low-latency processing

# optional: force input/output device
# sd.default.device = (1, 3)

def audio_callback(indata, outdata, frames, time, status):
    if status:
        print(status)

    audio = indata[:, 0]  # mono

    # FFT on the chunk
    fft_data = np.abs(np.fft.rfft(audio))
    freqs = np.fft.rfftfreq(len(audio), 1 / sample_rate)

    # detect peaks
    peaks, _ = find_peaks(fft_data, height=np.max(fft_data) * 0.3)
    detected_freqs = freqs[peaks]

    # generate sound for this block
    t = np.linspace(0, len(audio)/sample_rate, len(audio))
    generated = np.zeros_like(t)
    for f in detected_freqs[:6]:  # limit number of oscillators per block
        generated += np.sin(2 * np.pi * f * t) * 0.1

    # normalize
    if np.max(np.abs(generated)) > 0:
        generated = generated / np.max(np.abs(generated))

    outdata[:, 0] = generated  # mono output
    outdata[:, 1] = generated  # stereo output

# open stream
with sd.Stream(channels=2, callback=audio_callback,
               blocksize=block_size,
               samplerate=sample_rate):
    print("Streaming environmental audio. Press Ctrl+C to stop.")
    try:
        while True:
            sd.sleep(1000)
    except KeyboardInterrupt:
        print("Stopped.")
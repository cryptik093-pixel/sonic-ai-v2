import numpy as np
import sounddevice as sd

# Record 3 seconds of audio
sample_rate = 44100
duration = 3

print("Recording for 3 seconds...")
recording = sd.rec(int(sample_rate * duration), samplerate=sample_rate, channels=2, dtype=np.float32)
sd.wait()

print("Playback...")
sd.play(recording, samplerate=sample_rate)
sd.wait()

print("Done!")

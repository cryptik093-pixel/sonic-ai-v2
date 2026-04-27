import sounddevice as sd
import numpy as np

duration = 3
samplerate = 44100
sd.default.device = (1, 3)
print("Recording...")
audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1)
sd.wait()

print("Playing back...")
sd.play(audio, samplerate)
sd.wait()
"""Quick test of unified analyzer with synthetic audio."""
import numpy as np
from unified_analyzer import SonicAnalyzer

# Generate synthetic test audio (4-beat drum pattern at 120 BPM)
sample_rate = 44100
duration = 3

t = np.linspace(0, duration, int(sample_rate * duration))
audio = np.zeros_like(t)

# Generate kick drum beats at 120 BPM
bpm = 120
beat_interval = 60 / bpm

for beat_num in range(int(duration / beat_interval)):
    beat_time = beat_num * beat_interval
    start_idx = int(beat_time * sample_rate)
    end_idx = int((beat_time + 0.1) * sample_rate)
    
    if end_idx <= len(audio):
        kick_t = t[start_idx:end_idx] - beat_time
        kick = 100 * np.sin(2 * np.pi * 60 * kick_t) * np.exp(-5 * kick_t)
        audio[start_idx:end_idx] += kick

# Add harmonic content (chord: C major)
chord_freqs = [131, 165, 196]  # C3, E3, G3
for freq in chord_freqs:
    audio += 0.3 * np.sin(2 * np.pi * freq * t)

print("Testing unified analyzer with synthetic audio...\n")

# Create analyzer
analyzer = SonicAnalyzer(sample_rate=sample_rate, duration=duration)

# Load synthetic audio instead of recording
analyzer.load_audio(audio)

# Run analysis pipeline
results = analyzer.analyze(record=False)

# Print human-readable report
analyzer.print_report()

# Print JSON output
print("\nJSON OUTPUT (for APIs/UIs):")
print(analyzer.get_json())

import numpy as np

# Generate a test signal with known frequencies
sample_rate = 44100
duration = 5
t = np.linspace(0, duration, int(sample_rate * duration))

# Mix of frequencies: 100 Hz, 250 Hz, 1000 Hz
signal = (0.5 * np.sin(2 * np.pi * 100 * t) +
          0.3 * np.sin(2 * np.pi * 250 * t) +
          0.2 * np.sin(2 * np.pi * 1000 * t))

# Apply window
window = np.hanning(len(signal))
signal_windowed = signal * window

# FFT
fft_data = np.abs(np.fft.rfft(signal_windowed))
frequencies = np.fft.rfftfreq(len(signal_windowed), 1 / sample_rate)

# Filter
valid = (frequencies > 40) & (frequencies < 5000)
filtered_fft = fft_data[valid]
filtered_freqs = frequencies[valid]

print(f"Total frequency bins: {len(frequencies)}")
print(f"Filtered bins (40-5000 Hz): {len(filtered_freqs)}")
print(f"FFT max: {np.max(fft_data):.4f}")
print(f"Filtered FFT max: {np.max(filtered_fft):.4f}")
print(f"Filtered FFT min: {np.min(filtered_fft):.4f}")

# Find approximate peak locations
sorted_indices = np.argsort(filtered_fft)[::-1]
top_10 = sorted_indices[:10]

print("\nTop 10 frequencies in filtered range:")
for idx in top_10:
    freq = filtered_freqs[idx]
    if freq > 40:  # Only show valid frequencies
        mag = filtered_fft[idx]
        print(f"  {freq:.1f} Hz: magnitude {mag:.4f}")

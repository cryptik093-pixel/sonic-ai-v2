import numpy as np
import sounddevice as sd
import math
from scipy import signal

# ===== BPM DETECTION FUNCTIONS =====

def energy_envelope(audio, sample_rate, hop_length=512):
    """Compute instantaneous energy envelope of audio."""
    energy = []
    for i in range(0, len(audio) - hop_length, hop_length):
        frame = audio[i:i + hop_length]
        frame_energy = np.sum(frame ** 2)
        energy.append(frame_energy)
    return np.array(energy)

def onset_detection(energy_envelope, threshold_factor=1.5):
    """Detect onsets (attack points) from energy envelope."""
    smoothed = signal.medfilt(energy_envelope, kernel_size=3)
    novelty = np.zeros_like(smoothed)
    for i in range(1, len(smoothed)):
        novelty[i] = max(0, smoothed[i] - smoothed[i-1])
    
    threshold = np.mean(novelty) + threshold_factor * np.std(novelty)
    onsets = np.where(novelty > threshold)[0]
    
    if len(onsets) > 0:
        filtered_onsets = [onsets[0]]
        for onset in onsets[1:]:
            if onset - filtered_onsets[-1] > 10:
                filtered_onsets.append(onset)
        onsets = np.array(filtered_onsets)
    
    return onsets, novelty

def autocorrelation_tempo(onsets, sample_rate, hop_length=512, min_bpm=60, max_bpm=200):
    """Estimate BPM from onset intervals using autocorrelation."""
    if len(onsets) < 2:
        return None, 0, []
    
    onset_times = onsets * hop_length / sample_rate
    iois = np.diff(onset_times)
    
    if len(iois) == 0:
        return None, 0, []
    
    min_interval = 60 / max_bpm
    max_interval = 60 / min_bpm
    
    valid_iois = iois[(iois >= min_interval) & (iois <= max_interval)]
    
    if len(valid_iois) == 0:
        median_ioi = np.median(iois)
        estimated_bpm = 60 / median_ioi if median_ioi > 0 else None
        return estimated_bpm, 1.0 if estimated_bpm else 0, []
    
    autocorr = np.correlate(valid_iois, valid_iois, mode='full')
    autocorr = autocorr / np.max(autocorr)
    
    center = len(autocorr) // 2
    lags = np.arange(1, min(center, len(autocorr) // 2))
    
    if len(lags) == 0:
        median_ioi = np.median(valid_iois)
        estimated_bpm = 60 / median_ioi if median_ioi > 0 else None
        return estimated_bpm, 1.0 if estimated_bpm else 0, []
    
    corr_values = autocorr[center + lags]
    peak_lag = lags[np.argmax(corr_values)]
    period = np.mean(valid_iois) * peak_lag
    estimated_bpm = 60 / period if period > 0 else None
    
    confidence = np.max(corr_values) if len(corr_values) > 0 else 0
    
    if estimated_bpm and (estimated_bpm < min_bpm or estimated_bpm > max_bpm):
        estimated_bpm = None
        confidence = 0
    
    return estimated_bpm, confidence, valid_iois

# ===== TEST WITH SYNTHETIC DRUM BEAT =====

print("Generating synthetic drum beat at 120 BPM...")
sample_rate = 44100
duration = 4
target_bpm = 120
beat_interval = 60 / target_bpm

# Generate kick drum at 120 BPM
t = np.linspace(0, duration, int(sample_rate * duration))
audio = np.zeros_like(t)

# Sine wave drum click (kick)
for beat_num in range(int(duration / beat_interval)):
    beat_time = beat_num * beat_interval
    
    # Find indices for this beat
    start_idx = int(beat_time * sample_rate)
    end_idx = int((beat_time + 0.1) * sample_rate)  # 100ms duration
    
    if end_idx <= len(audio):
        # Decaying sine wave (simulates kick drum)
        kick_t = t[start_idx:end_idx] - beat_time
        kick = 100 * np.sin(2 * np.pi * 60 * kick_t) * np.exp(-5 * kick_t)
        audio[start_idx:end_idx] += kick

print(f"Analyzing synthetic beat ({int(duration)} seconds)...")

# Analysis
hop_length = 512
energy = energy_envelope(audio, sample_rate, hop_length)
onsets_energy, novelty_energy = onset_detection(energy, threshold_factor=1.2)

print(f"\nDetected {len(onsets_energy)} onsets")

if len(onsets_energy) > 1:
    bpm_energy, confidence_energy, valid_iois = autocorrelation_tempo(
        onsets_energy, sample_rate, hop_length, min_bpm=60, max_bpm=200
    )
    
    print("\n" + "="*60)
    print("BPM DETECTION RESULTS")
    print("="*60)
    
    if bpm_energy is not None:
        print(f"\nTarget BPM: {target_bpm}")
        print(f"Detected BPM: {bpm_energy:.1f}")
        print(f"Error: {abs(bpm_energy - target_bpm):.1f} BPM ({abs(bpm_energy - target_bpm)/target_bpm*100:.1f}%)")
        print(f"Confidence: {confidence_energy:.3f}")
        
        # Note durations
        quarter_ms = 60000 / bpm_energy
        print(f"\nNote durations at {bpm_energy:.1f} BPM:")
        print(f"  Quarter note: {quarter_ms:.0f} ms")
        print(f"  Eighth note: {quarter_ms/2:.0f} ms")
        print(f"  Sixteenth note: {quarter_ms/4:.0f} ms")
    else:
        print("Could not detect BPM")
else:
    print("Not enough onsets detected")

# Play metronome
if bpm_energy is not None:
    print(f"\nGenerating metronome at {bpm_energy:.1f} BPM...")
    
    beat_duration = 60 / bpm_energy
    num_beats = 8
    total_duration = beat_duration * num_beats
    
    t_metro = np.linspace(0, total_duration, int(sample_rate * total_duration))
    metronome = np.zeros_like(t_metro)
    
    click_freq = 400
    click_duration = 0.1
    
    for beat_num in range(num_beats):
        beat_time = beat_num * beat_duration
        beat_start = int(beat_time * sample_rate)
        beat_end = int((beat_time + click_duration) * sample_rate)
        beat_end = min(beat_end, len(metronome))
        
        if beat_end > beat_start:
            click_length = beat_end - beat_start
            envelope = np.linspace(1, 0.1, click_length)
            click = np.sin(2 * np.pi * click_freq * t_metro[beat_start:beat_end]) * envelope
            metronome[beat_start:beat_end] += click
    
    metronome = metronome / np.max(np.abs(metronome)) * 0.8
    metronome_stereo = np.stack([metronome, metronome], axis=1)
    
    try:
        sd.play(metronome_stereo, sample_rate)
        sd.wait()
        print("Metronome playback complete.")
    except KeyboardInterrupt:
        print("\nPlayback interrupted.")
    except Exception as e:
        print(f"Playback error: {e}")

print("\n" + "="*60)
print("BPM ANALYSIS COMPLETE")
print("="*60)

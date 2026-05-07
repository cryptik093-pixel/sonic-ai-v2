# Sonic AI V2 Real-Time Audio and MIDI Architecture

## Purpose

This document defines a future real-time audio and MIDI platform track for Sonic AI V2.
It does not change the current API contract and does not claim that the existing FastAPI
backend is a hard real-time audio engine.

The current Sonic AI V2 backend performs deterministic analysis on uploaded audio files
through `/api/v2/analyze`. Real-time audio callback processing, MIDI scheduling, and
plugin-host integration require a separate callback-safe engine architecture.

## System Layers

### Current Python SaaS Backend

The existing backend remains focused on uploaded-file analysis:

- FastAPI routes, including `/api/v2/analyze`.
- Explicit Pydantic request and response models.
- Deterministic DSP metrics derived from actual audio data.
- JSON success and error payloads.
- Offline or near-time processing where file I/O, full-buffer analysis, and Python
  scientific libraries are appropriate.

This layer must not be described as hard real-time. Python, FastAPI, file upload handling,
and batch analysis libraries are useful for SaaS analysis workflows, but they are not
appropriate inside an audio callback.

### Future Real-Time Engine

The real-time engine should be a native, callback-safe DSP and MIDI core. Suitable
implementation targets include C++, Rust, JUCE, CLAP, VST3, AU, or a platform-specific
standalone engine.

Primary responsibilities:

- Receive audio input in fixed-size callback blocks.
- Run bounded time-domain analysis directly on the audio thread.
- Pass windowed audio or extracted features to worker threads using real-time-safe queues.
- Generate timestamped MIDI events with host-clock or standalone-clock synchronization.
- Optionally render DSP effects with declared latency and stable bypass behavior.

The audio callback must avoid blocking I/O, locks, heap allocation, logging, network calls,
unbounded loops, and dynamic graph mutation.

### Integration Layer

The integration layer adapts the native engine to product surfaces:

- DAW plugins: VST3, AU, AAX, CLAP.
- Standalone desktop apps using JUCE or a custom engine.
- Hardware-controller or MIDI-device integrations.
- Web prototypes using AudioWorklet and Web MIDI, with stricter CPU and browser limits.
- SaaS handoff flows that export deterministic reports, MIDI files, presets, or DAW-ready
  automation data.

The integration layer owns UI state, preset management, device selection, host transport
sync, persistence, and communication with the existing Sonic AI V2 backend when needed.

## Target Data Flow

```text
audio input
  -> real-time-safe input conditioning
  -> block analysis
  -> feature extraction
  -> decision logic
  -> MIDI event scheduling
  -> optional DSP/rendering
  -> audio and MIDI output
```

Recommended thread split:

- Audio thread: fixed-block DSP, sample-accurate event rendering, cheap meters, bounded
  feature extraction, lock-free queue writes.
- Analysis worker: FFT/STFT, pitch tracking, onset aggregation, tempo estimation, chord
  inference, smoothing, confidence scoring.
- MIDI scheduler: lookahead event preparation, PPQ conversion, host transport handling,
  jitter control.
- UI thread: visualization, controls, preset editing, non-real-time logging.

Communication between threads should use preallocated single-producer/single-consumer
ring buffers, double-buffered snapshots, atomics for scalar parameters, and immutable
configuration swaps prepared outside the audio callback.

## Professional Defaults

Baseline operating assumptions:

- Sample rate: 48 kHz.
- Audio callback block size: 64 to 256 samples.
- Audio callback budget: below 50 percent of block duration under normal load.
- Time-domain analysis: per-block peak/RMS plus smoothed envelope followers.
- FFT analysis: 1024 to 2048 sample windows when latency permits.
- STFT hop size: 256 to 512 samples for responsive spectral features.
- Queueing: bounded lock-free SPSC queues for audio-to-worker and worker-to-audio/UI
  messages.
- Memory: allocate buffers, windows, filter states, and queues during initialization or
  prepare-to-play, not during processing.

At 48 kHz, a 64-sample block is about 1.33 ms and a 256-sample block is about 5.33 ms.
A 2048-sample FFT window spans about 42.7 ms before additional scheduling and smoothing
latency. These values are acceptable for spectral context and tempo decisions, but not for
instantaneous control that must feel sample-tight.

## Analysis Modules

### Time-Domain Analysis

Run these features directly on the audio thread when needed:

- Peak level per channel.
- RMS over the current block or a short rolling window.
- Envelope following with separate attack and release coefficients.
- Crest factor from peak and RMS.
- Zero-crossing rate for rough noisiness or pitch-candidate gating.
- Transient detection using envelope slope and adaptive thresholds.

Envelope followers should use stable one-pole smoothing:

```text
y[n] = coeff * y[n - 1] + (1 - coeff) * abs(x[n])
```

Use separate coefficients for rising and falling signal levels. Guard divisions with a
small epsilon and clamp denormal-prone states to zero where appropriate.

### Frequency-Domain Analysis

Run spectral analysis on a worker thread unless the window is very small and CPU budget is
proven safe:

- STFT magnitude frames with Hann or Blackman-Harris windows.
- Spectral centroid for brightness.
- Spectral roll-off for high-frequency extension.
- Spectral flux for onset support.
- Band energy distribution using fixed music-production bands.
- Inharmonicity or harmonic salience for pitched material.
- Optional perceptual filter banks for more stable display and decision logic.

Window and hop sizes must be explicit because they define the latency and resolution trade:
short windows react quickly but smear low-frequency pitch and kick/bass detail; long windows
improve low-frequency resolution but delay decisions.

### Pitch, Onset, Tempo, and Harmony

Stage these modules behind confidence scores:

- Pitch detection: YIN, autocorrelation, cepstrum, harmonic product spectrum, or a neural
  tracker outside the audio callback.
- Onset detection: spectral flux plus transient-envelope confirmation.
- Tempo estimation: onset interval histograms with host-tempo override when available.
- Groove extraction: microtiming offsets relative to host grid or inferred beat grid.
- Chord detection: chroma or harmonic pitch class profiles over longer windows.

Expected failure modes:

- Pitch trackers can octave-jump on distorted, polyphonic, or noisy sources.
- Onset detectors can false-trigger on vibrato, tremolo, sidechain pumping, and dense
  hi-hat patterns.
- Tempo inference is unreliable on sparse intros, rubato material, and tempo changes.
- Chord detection requires longer context and should not drive urgent real-time decisions.

## MIDI Generation and Scheduling

### Audio-to-MIDI Mapping

Supported future mappings:

- Monophonic pitch to note-on, pitch bend, and note-off.
- Drum transients to MIDI notes using band-limited onset detectors.
- Envelope or loudness to velocity and MIDI CC.
- Spectral brightness to filter cutoff, modulation depth, or automation CC.
- Chord and key estimates to constrained generative note selection.

Each MIDI event must carry a timestamp in the engine's timeline. The audio thread should
render or emit events at sample offsets within the current block whenever the plugin or
device API supports it.

### Clock and Jitter Control

The MIDI scheduler should support:

- Host PPQ position, tempo, time signature, loop state, and transport state.
- Standalone monotonic clock when no host clock exists.
- Lookahead scheduling on a non-audio thread.
- Sample-offset correction when events enter the current audio block.
- Bounded queues for pending MIDI events.

Jitter-sensitive decisions should be quantized or timestamped before the audio callback.
The callback should only consume ready events, translate them to sample offsets, and emit
them through the host or device API.

## DSP Platform Notes

### Gain, Metering, and Loudness

The real-time engine should maintain explicit gain staging:

- Input trim and output trim.
- Peak and RMS meters per channel.
- True peak or oversampled peak estimates when CPU permits.
- LUFS-style loudness on a worker thread or slower meter path.
- Headroom warnings that are factual and derived from measured audio.

Integrated loudness over long durations belongs to offline or worker analysis, not the
hard real-time callback.

### EQ and Dynamics

Minimum viable real-time DSP blocks:

- Stable biquad filters for high-pass, low-pass, shelving, and peaking EQ.
- Parameter smoothing for gain, frequency, and Q changes.
- Compressor, limiter, expander, and gate envelopes with explicit attack, release, knee,
  ratio, and makeup gain behavior.
- Optional multiband processing with latency-aware crossover design.

IIR filters are suitable for low-latency minimum-phase processing. Linear-phase FIR EQ
requires latency reporting and is inappropriate for zero-latency live monitoring unless
the user explicitly accepts the delay.

### Time-Based and Nonlinear Effects

Future effects may include delay, reverb, chorus, flanger, phaser, pitch shift, time
stretch, saturation, distortion, and waveshaping.

Implementation requirements:

- Delay lines and modulation buffers must be preallocated.
- Feedback paths must be bounded and numerically stable.
- Nonlinear processors need oversampling or antialiasing strategy when driven hard.
- Pitch shift and time stretch must declare algorithmic latency and artifacts.
- Bypass must avoid clicks and preserve latency compensation.

### Optimization

Performance work should prioritize:

- Struct-of-arrays or cache-friendly contiguous buffers for multichannel processing.
- SIMD/vectorized inner loops for gain, filters, windows, and spectral operations.
- Precomputed windows, filter coefficients, lookup tables, and band maps.
- Fixed upper bounds for channels, voices, queued events, and analysis frames.
- Profiling under worst-case block size, sample rate, channel count, and plugin instance
  count.

## Testing and Validation

Required future validation:

- Deterministic unit tests with generated sine, impulse, step, noise, and transient
  signals.
- Golden-value tests for RMS, peak, envelope, spectral centroid, band energy, and onset
  timing.
- MIDI scheduling tests for PPQ conversion, sample offsets, loop boundaries, tempo
  changes, and note-off ordering.
- Real-time safety checks for allocation-free and lock-free callback paths.
- Stress tests at 48 kHz and 96 kHz with 64-sample blocks.
- Null tests and bypass tests for DSP processors.
- Listening tests for dynamics, pitch, nonlinear processing, and time-based effects.
- Profiling reports for CPU load, worst-case callback duration, queue pressure, and event
  jitter.

The current documentation-only addition requires no runtime tests. Verification should
confirm that this document remains consistent with `docs/SONIC_AI_V2_SPEC.md` and
`docs/API_CONTRACT.md`, and that it does not claim current API endpoints provide hard
real-time processing or fake AI behavior.

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, log2
from typing import Literal

import numpy as np
from scipy.signal import medfilt

from app.audio.loader import LoadedAudio
from app.audio.midi_generation import Note, Pattern, Track, render_to_midi

ScaleName = Literal["major", "minor"]

MAJOR_SCALE_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE_INTERVALS = (0, 2, 3, 5, 7, 8, 10)
DRUM_NOTES = {"kick": 36, "snare": 38, "hat": 42}


@dataclass(frozen=True)
class TempoGrid:
    """Estimated tempo and beat timestamps derived from a full audio buffer."""

    tempo_bpm: float
    beat_grid: tuple[float, ...]


@dataclass(frozen=True)
class PitchEvent:
    """A smoothed monophonic pitch estimate at an analysis-frame timestamp."""

    time_seconds: float
    pitch_midi: int


@dataclass(frozen=True)
class DrumOnsets:
    """Band-classified drum onset timestamps in seconds."""

    kick_onsets: tuple[float, ...]
    snare_onsets: tuple[float, ...]
    hat_onsets: tuple[float, ...]


@dataclass(frozen=True)
class AudioToMidiResult:
    """Internal audio-to-MIDI extraction result.

    `midi_bytes` is rendered with the internal Standard MIDI File adapter. This
    module intentionally has no FastAPI route and does not alter the public API
    contract.
    """

    tempo_grid: TempoGrid
    pitch_events: tuple[PitchEvent, ...]
    drum_onsets: DrumOnsets
    tracks: tuple[Track, ...]
    midi_bytes: bytes


@dataclass(frozen=True)
class ExtractedAudioMIDI:
    """Typed summary of audio-derived MIDI material for later hybrid transforms.

    This is an inspectable, immutable handoff object. It does not perform
    extraction or rendering; Phase 12 uses it only to decide which deterministic
    transform paths are eligible.
    """

    tempo_bpm: float
    beat_grid: tuple[float, ...]
    melody_track: Track | None = None
    drum_track: Track | None = None
    chord_hints: tuple[int, ...] | None = None
    key: str | None = None
    mode: str | None = None
    rhythm_grid: str = "straight_eighth_grid"


def extract_audio_to_midi(
    audio: LoadedAudio,
    *,
    scale: ScaleName = "minor",
    include_bass: bool = True,
    include_chords: bool = True,
) -> AudioToMidiResult:
    """Convert uploaded audio into deterministic internal MIDI structures.

    Feature extraction is full-buffer, offline work for the SaaS backend. It is
    not callback-safe real-time processing. Determinism comes from fixed window
    sizes, percentile/MAD thresholds, stable sorting, and explicit tie-breaking
    toward earlier timestamps and lower pitches.
    """

    _validate_audio(audio)
    tempo_grid = estimate_tempo_grid(audio)
    pitch_events = extract_monophonic_pitch_events(audio)
    drum_onsets = extract_drum_onsets(audio)
    tracks = map_features_to_tracks(
        tempo_grid=tempo_grid,
        pitch_events=pitch_events,
        drum_onsets=drum_onsets,
        duration_seconds=audio.duration_seconds,
        scale=scale,
        include_bass=include_bass,
        include_chords=include_chords,
    )
    return AudioToMidiResult(
        tempo_grid=tempo_grid,
        pitch_events=pitch_events,
        drum_onsets=drum_onsets,
        tracks=tracks,
        midi_bytes=render_to_midi(tracks),
    )


def estimate_tempo_grid(
    audio: LoadedAudio,
    *,
    min_bpm: float = 60.0,
    max_bpm: float = 200.0,
) -> TempoGrid:
    """Estimate tempo from onset-envelope autocorrelation.

    The onset envelope is built from positive frame-energy changes. Candidate
    beat lags are scored by autocorrelation; ties are resolved by selecting the
    shorter lag, which gives deterministic behavior for harmonically related
    periodicities.
    """

    _validate_audio(audio)
    hop_length = _analysis_hop(audio.sample_rate_hz)
    envelope, frame_times = _onset_envelope(_mono(audio), audio.sample_rate_hz, hop_length)
    duration_seconds = audio.duration_seconds
    if envelope.size < 3 or float(np.max(envelope)) <= 0.0:
        return _fallback_tempo_grid(duration_seconds)

    centered = envelope - float(np.mean(envelope))
    autocorrelation = np.correlate(centered, centered, mode="full")[centered.size - 1 :]
    min_lag = max(1, int(round((60.0 / max_bpm) * audio.sample_rate_hz / hop_length)))
    max_lag = min(
        autocorrelation.size - 1,
        int(round((60.0 / min_bpm) * audio.sample_rate_hz / hop_length)),
    )
    if max_lag < min_lag:
        return _fallback_tempo_grid(duration_seconds)

    candidate_lags = range(min_lag, max_lag + 1)
    best_lag = min(candidate_lags, key=lambda lag: (-float(autocorrelation[lag]), lag))
    tempo_bpm = float(60.0 * audio.sample_rate_hz / (best_lag * hop_length))
    tempo_bpm = float(np.clip(tempo_bpm, min_bpm, max_bpm))

    onset_indices = _pick_peak_indices(envelope, _adaptive_threshold(envelope), min_distance=2)
    first_beat = float(frame_times[onset_indices[0]]) if onset_indices else 0.0
    beat_grid = _beat_grid(first_beat, tempo_bpm, duration_seconds)
    return TempoGrid(tempo_bpm=round(tempo_bpm, 6), beat_grid=beat_grid)


def extract_monophonic_pitch_events(
    audio: LoadedAudio,
    *,
    fmin_hz: float = 80.0,
    fmax_hz: float = 1_000.0,
) -> tuple[PitchEvent, ...]:
    """Extract a smoothed autocorrelation F0 contour and quantize to MIDI.

    Each voiced frame selects the strongest normalized autocorrelation peak in
    the configured frequency range. Equal peak scores choose the lower lag,
    which maps to the higher F0 deterministically. A median filter suppresses
    single-frame octave jumps before MIDI quantization.
    """

    _validate_audio(audio)
    sample_rate_hz = audio.sample_rate_hz
    mono = _mono(audio)
    frame_length = max(1024, _next_power_of_two(int(sample_rate_hz * 0.046)))
    hop_length = max(256, frame_length // 2)
    min_lag = max(1, int(sample_rate_hz / fmax_hz))
    max_lag = min(frame_length - 1, int(sample_rate_hz / fmin_hz))
    if max_lag <= min_lag or mono.size < frame_length:
        return ()

    rms_gate = max(1e-5, float(np.percentile(np.abs(mono), 65)) * 0.15)
    pitches: list[int] = []
    times: list[float] = []
    window = np.hanning(frame_length)
    for start in range(0, mono.size - frame_length + 1, hop_length):
        frame = mono[start : start + frame_length].astype(np.float64, copy=False)
        if float(np.sqrt(np.mean(np.square(frame)))) < rms_gate:
            continue
        frame = (frame - float(np.mean(frame))) * window
        correlation = np.correlate(frame, frame, mode="full")[frame_length - 1 :]
        zero_lag = float(correlation[0])
        if zero_lag <= 1e-12:
            continue
        lag = min(
            range(min_lag, max_lag + 1),
            key=lambda candidate: (-float(correlation[candidate] / zero_lag), candidate),
        )
        confidence = float(correlation[lag] / zero_lag)
        if confidence < 0.25:
            continue
        frequency_hz = _octave_checked_frequency(frame, sample_rate_hz, sample_rate_hz / lag)
        pitches.append(_frequency_to_midi(frequency_hz))
        times.append(round((start + frame_length / 2) / sample_rate_hz, 6))

    if not pitches:
        return ()

    kernel_size = 3 if len(pitches) >= 3 else 1
    smoothed = medfilt(np.asarray(pitches, dtype=np.int16), kernel_size=kernel_size)
    events = tuple(
        PitchEvent(time_seconds=time, pitch_midi=int(pitch))
        for time, pitch in zip(times, smoothed, strict=True)
    )
    return _dedupe_pitch_events(events)


def extract_drum_onsets(audio: LoadedAudio) -> DrumOnsets:
    """Classify kick, snare, and hat onsets with band-limited spectral flux.

    Flux peaks are accepted only when the target band has enough frame-energy
    dominance for that drum class. Thresholds are median/MAD based, so generated
    test signals and repeated uploads produce identical onset decisions.
    """

    _validate_audio(audio)
    mono = _mono(audio)
    sample_rate_hz = audio.sample_rate_hz
    frame_length = max(512, _next_power_of_two(int(sample_rate_hz * 0.032)))
    hop_length = max(128, frame_length // 4)
    if mono.size < frame_length:
        return DrumOnsets((), (), ())

    spectra, frame_times, frequencies = _magnitude_spectra(
        mono, sample_rate_hz, frame_length, hop_length
    )
    bands = {
        "kick": _band_energy(spectra, frequencies, 35.0, 140.0),
        "snare": _band_energy(spectra, frequencies, 150.0, 3_000.0),
        "hat": _band_energy(spectra, frequencies, 5_000.0, min(16_000.0, sample_rate_hz / 2.0)),
    }
    total_energy = np.sum(np.square(spectra), axis=1) + 1e-12
    min_distance = max(1, int(round(0.07 * sample_rate_hz / hop_length)))

    kick = _class_onsets(
        bands["kick"],
        frame_times,
        min_distance=min_distance,
        dominance=bands["kick"] / total_energy,
        min_dominance=0.30,
    )
    snare = _class_onsets(
        bands["snare"],
        frame_times,
        min_distance=min_distance,
        dominance=bands["snare"] / total_energy,
        min_dominance=0.28,
    )
    hat = _class_onsets(
        bands["hat"],
        frame_times,
        min_distance=min_distance,
        dominance=bands["hat"] / total_energy,
        min_dominance=0.25,
    )
    return DrumOnsets(kick_onsets=kick, snare_onsets=snare, hat_onsets=hat)


def map_features_to_tracks(
    *,
    tempo_grid: TempoGrid,
    pitch_events: tuple[PitchEvent, ...],
    drum_onsets: DrumOnsets,
    duration_seconds: float,
    scale: ScaleName = "minor",
    include_bass: bool = True,
    include_chords: bool = True,
) -> tuple[Track, ...]:
    """Map extracted features into `Note`/`Pattern`/`Track` MIDI-core objects."""

    tempo_bpm = max(1, int(round(tempo_grid.tempo_bpm)))
    beat_duration = 60.0 / tempo_grid.tempo_bpm
    length_beats = max(4.0, float(ceil(duration_seconds / beat_duration)))
    root_pc = _infer_root_pitch_class(pitch_events)
    tracks: list[Track] = []

    melody_notes = _melody_notes(pitch_events, beat_duration, root_pc, scale, length_beats)
    drum_notes = _drum_notes(drum_onsets, beat_duration, length_beats)
    if melody_notes:
        tracks.append(
            Track(
                name="Extracted Melody",
                role="melody",
                patterns=(Pattern(melody_notes, tempo_bpm=tempo_bpm, length_beats=length_beats),),
            )
        )

    if drum_notes:
        tracks.append(
            Track(
                name="Extracted Drums",
                role="drums",
                patterns=(Pattern(drum_notes, tempo_bpm=tempo_bpm, length_beats=length_beats),),
            )
        )

    has_musical_source = bool(pitch_events or drum_notes)
    if include_bass and has_musical_source:
        tracks.append(_bass_track(root_pc, tempo_bpm, length_beats))
    if include_chords and has_musical_source:
        tracks.append(_chord_track(root_pc, scale, tempo_bpm, length_beats))

    if not tracks:
        tracks.append(
            Track(
                name="Extracted Silence Guide",
                role="melody",
                patterns=(Pattern((), tempo_bpm=tempo_bpm, length_beats=length_beats),),
            )
        )

    return tuple(tracks)


def _validate_audio(audio: LoadedAudio) -> None:
    if not isinstance(audio, LoadedAudio):
        raise TypeError("audio must be a LoadedAudio instance.")
    if audio.samples.ndim != 2:
        raise ValueError("audio samples must be a 2D array shaped (frames, channels).")
    if audio.sample_rate_hz <= 0 or audio.frames <= 0 or audio.channels <= 0:
        raise ValueError("audio metadata must contain positive sample rate, frames, and channels.")
    if audio.samples.shape != (audio.frames, audio.channels):
        raise ValueError("audio metadata does not match sample shape.")


def _mono(audio: LoadedAudio) -> np.ndarray:
    mono = np.mean(audio.samples.astype(np.float64, copy=False), axis=1)
    return np.nan_to_num(mono, copy=False, nan=0.0, posinf=0.0, neginf=0.0)


def _analysis_hop(sample_rate_hz: int) -> int:
    return max(128, int(round(sample_rate_hz * 0.01)))


def _onset_envelope(
    mono: np.ndarray, sample_rate_hz: int, hop_length: int
) -> tuple[np.ndarray, np.ndarray]:
    frame_length = max(512, _next_power_of_two(int(sample_rate_hz * 0.025)))
    if mono.size < frame_length:
        return np.zeros(0, dtype=np.float64), np.zeros(0, dtype=np.float64)

    energies: list[float] = []
    times: list[float] = []
    window = np.hanning(frame_length)
    for start in range(0, mono.size - frame_length + 1, hop_length):
        frame = mono[start : start + frame_length] * window
        energies.append(float(np.sqrt(np.mean(np.square(frame)))))
        times.append((start + frame_length / 2) / sample_rate_hz)

    energy = np.asarray(energies, dtype=np.float64)
    envelope = np.diff(energy, prepend=energy[0])
    envelope = np.maximum(envelope, 0.0)
    peak = float(np.max(envelope)) if envelope.size else 0.0
    if peak > 0.0:
        envelope = envelope / peak
    return envelope, np.asarray(times, dtype=np.float64)


def _fallback_tempo_grid(duration_seconds: float) -> TempoGrid:
    return TempoGrid(tempo_bpm=120.0, beat_grid=_beat_grid(0.0, 120.0, duration_seconds))


def _beat_grid(first_beat: float, tempo_bpm: float, duration_seconds: float) -> tuple[float, ...]:
    beat_duration = 60.0 / tempo_bpm
    if duration_seconds <= 0.0:
        return (0.0,)
    grid = []
    time = max(0.0, first_beat)
    while time <= duration_seconds + (beat_duration * 0.5):
        grid.append(round(time, 6))
        time += beat_duration
    return tuple(grid) if grid else (0.0,)


def _adaptive_threshold(values: np.ndarray, multiplier: float = 3.0) -> float:
    if values.size == 0:
        return 0.0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return median + multiplier * max(mad, 1e-9)


def _pick_peak_indices(
    values: np.ndarray,
    threshold: float,
    *,
    min_distance: int,
) -> list[int]:
    peaks: list[int] = []
    last_peak = -min_distance - 1
    for index in range(1, values.size - 1):
        current = float(values[index])
        if current < threshold:
            continue
        if current < float(values[index - 1]) or current < float(values[index + 1]):
            continue
        if index - last_peak < min_distance:
            if current > float(values[peaks[-1]]):
                peaks[-1] = index
                last_peak = index
            continue
        peaks.append(index)
        last_peak = index
    return peaks


def _frequency_to_midi(frequency_hz: float) -> int:
    return int(np.clip(round(69 + 12 * log2(frequency_hz / 440.0)), 0, 127))


def _octave_checked_frequency(frame: np.ndarray, sample_rate_hz: int, autocorr_hz: float) -> float:
    """Use spectral salience only to correct deterministic autocorrelation octave slips."""

    spectrum = np.abs(np.fft.rfft(frame))
    frequencies = np.fft.rfftfreq(frame.size, d=1.0 / sample_rate_hz)
    band = (frequencies >= 80.0) & (frequencies <= 1_000.0)
    if not np.any(band):
        return autocorr_hz

    band_indices = np.flatnonzero(band)
    local_index = min(
        band_indices,
        key=lambda index: (-float(spectrum[index]), abs(float(frequencies[index]) - autocorr_hz)),
    )
    spectral_hz = float(frequencies[local_index])
    autocorr_midi = _frequency_to_midi(autocorr_hz)
    spectral_midi = _frequency_to_midi(spectral_hz)
    if abs(spectral_midi - autocorr_midi) >= 7:
        return spectral_hz
    return autocorr_hz


def _dedupe_pitch_events(events: tuple[PitchEvent, ...]) -> tuple[PitchEvent, ...]:
    deduped: list[PitchEvent] = []
    previous_pitch: int | None = None
    for event in events:
        if event.pitch_midi == previous_pitch:
            continue
        deduped.append(event)
        previous_pitch = event.pitch_midi
    return tuple(deduped)


def _magnitude_spectra(
    mono: np.ndarray,
    sample_rate_hz: int,
    frame_length: int,
    hop_length: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    window = np.hanning(frame_length)
    spectra: list[np.ndarray] = []
    times: list[float] = []
    for start in range(0, mono.size - frame_length + 1, hop_length):
        frame = mono[start : start + frame_length] * window
        spectra.append(np.abs(np.fft.rfft(frame)))
        times.append((start + frame_length / 2) / sample_rate_hz)
    return (
        np.asarray(spectra, dtype=np.float64),
        np.asarray(times, dtype=np.float64),
        np.fft.rfftfreq(frame_length, d=1.0 / sample_rate_hz),
    )


def _band_energy(
    spectra: np.ndarray,
    frequencies: np.ndarray,
    low_hz: float,
    high_hz: float,
) -> np.ndarray:
    band = (frequencies >= low_hz) & (frequencies < high_hz)
    if not np.any(band):
        return np.zeros(spectra.shape[0], dtype=np.float64)
    return np.sum(np.square(spectra[:, band]), axis=1)


def _class_onsets(
    band_energy: np.ndarray,
    frame_times: np.ndarray,
    *,
    min_distance: int,
    dominance: np.ndarray,
    min_dominance: float,
) -> tuple[float, ...]:
    flux = np.maximum(np.diff(band_energy, prepend=band_energy[0]), 0.0)
    peak = float(np.max(flux)) if flux.size else 0.0
    if peak <= 0.0:
        return ()
    normalized = flux / peak
    threshold = max(0.10, _adaptive_threshold(normalized, multiplier=2.5))
    peaks = _pick_peak_indices(normalized, threshold, min_distance=min_distance)
    return tuple(
        round(float(frame_times[index]), 6)
        for index in peaks
        if float(dominance[index]) >= min_dominance
    )


def _infer_root_pitch_class(pitch_events: tuple[PitchEvent, ...]) -> int:
    if not pitch_events:
        return 0
    counts = np.zeros(12, dtype=np.int32)
    for event in pitch_events:
        counts[event.pitch_midi % 12] += 1
    return int(min(range(12), key=lambda pitch_class: (-int(counts[pitch_class]), pitch_class)))


def _melody_notes(
    pitch_events: tuple[PitchEvent, ...],
    beat_duration: float,
    root_pc: int,
    scale: ScaleName,
    length_beats: float,
) -> tuple[Note, ...]:
    notes: list[Note] = []
    for index, event in enumerate(pitch_events):
        start = _quantize_beat(event.time_seconds / beat_duration, step=0.25)
        if start >= length_beats:
            continue
        next_time = (
            pitch_events[index + 1].time_seconds
            if index + 1 < len(pitch_events)
            else event.time_seconds + beat_duration
        )
        duration = max(0.25, _quantize_beat((next_time - event.time_seconds) / beat_duration, 0.25))
        duration = min(duration, max(0.25, length_beats - start))
        notes.append(
            Note(
                pitch=_quantize_pitch_to_scale(event.pitch_midi, root_pc, scale),
                velocity=92,
                start_time=start,
                duration=duration,
                channel=0,
            )
        )
    return tuple(notes)


def _drum_notes(
    drum_onsets: DrumOnsets,
    beat_duration: float,
    length_beats: float,
) -> tuple[Note, ...]:
    notes: list[Note] = []
    for name, onsets in (
        ("kick", drum_onsets.kick_onsets),
        ("snare", drum_onsets.snare_onsets),
        ("hat", drum_onsets.hat_onsets),
    ):
        for onset in onsets:
            start = _quantize_beat(onset / beat_duration, step=0.25)
            if start < length_beats:
                notes.append(
                    Note(
                        pitch=DRUM_NOTES[name],
                        velocity=96 if name != "hat" else 78,
                        start_time=start,
                        duration=0.25,
                        channel=9,
                    )
                )
    return tuple(notes)


def _bass_track(root_pc: int, tempo_bpm: int, length_beats: float) -> Track:
    root_pitch = 36 + root_pc
    while root_pitch > 47:
        root_pitch -= 12
    notes = tuple(
        Note(root_pitch, 88, float(beat), 1.0, 1)
        for beat in range(0, int(length_beats), 4)
    )
    return Track(
        name="Extracted Bass",
        role="bass",
        patterns=(Pattern(notes, tempo_bpm=tempo_bpm, length_beats=length_beats),),
    )


def _chord_track(root_pc: int, scale: ScaleName, tempo_bpm: int, length_beats: float) -> Track:
    root_pitch = 48 + root_pc
    intervals = (0, 4, 7) if scale == "major" else (0, 3, 7)
    notes = tuple(
        Note(root_pitch + interval, 76, float(beat), min(3.75, length_beats - beat), 2)
        for beat in range(0, int(length_beats), 4)
        for interval in intervals
        if length_beats - beat > 0.0
    )
    return Track(
        name="Extracted Chords",
        role="chords",
        patterns=(Pattern(notes, tempo_bpm=tempo_bpm, length_beats=length_beats),),
    )


def _quantize_beat(value: float, step: float) -> float:
    return round(round(value / step) * step, 6)


def _quantize_pitch_to_scale(pitch: int, root_pc: int, scale: ScaleName) -> int:
    intervals = MAJOR_SCALE_INTERVALS if scale == "major" else MINOR_SCALE_INTERVALS
    allowed = []
    for midi_pitch in range(max(0, pitch - 12), min(127, pitch + 12) + 1):
        if (midi_pitch - root_pc) % 12 in intervals:
            allowed.append(midi_pitch)
    return min(allowed, key=lambda candidate: (abs(candidate - pitch), candidate))


def _next_power_of_two(value: int) -> int:
    return 1 << max(0, int(value - 1).bit_length())

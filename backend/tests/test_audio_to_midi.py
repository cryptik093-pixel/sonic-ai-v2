import numpy as np
import pytest

from app.audio.audio_to_midi import (
    DrumOnsets,
    PitchEvent,
    TempoGrid,
    estimate_tempo_grid,
    extract_audio_to_midi,
    extract_drum_onsets,
    extract_monophonic_pitch_events,
    map_features_to_tracks,
)
from app.audio.loader import LoadedAudio
from app.audio.midi_generation import render_to_midi


def test_same_audio_input_renders_identical_midi_bytes() -> None:
    audio = _audio(_sine_melody((440.0, 523.25), seconds_per_note=0.75, sample_rate_hz=16_000))

    first = extract_audio_to_midi(audio)
    second = extract_audio_to_midi(audio)

    assert first.midi_bytes == second.midi_bytes
    assert first.tracks == second.tracks


def test_tempo_estimation_tracks_synthetic_click_bpm() -> None:
    audio = _audio(_click_track(bpm=120, seconds=4.0, sample_rate_hz=16_000))

    tempo_grid = estimate_tempo_grid(audio)

    assert tempo_grid.tempo_bpm == pytest.approx(120.0, abs=3.0)
    assert len(tempo_grid.beat_grid) >= 7


def test_pitch_extraction_maps_synthetic_sine_notes_to_midi() -> None:
    samples = _sine_melody((440.0, 493.88, 523.25), seconds_per_note=0.35, sample_rate_hz=16_000)
    events = extract_monophonic_pitch_events(_audio(samples, sample_rate_hz=16_000))
    pitches = [event.pitch_midi for event in events]

    assert 69 in pitches
    assert 71 in pitches
    assert 72 in pitches


def test_pitch_extraction_follows_synthetic_sine_sweep_direction() -> None:
    sample_rate_hz = 16_000
    seconds = 1.2
    t = np.arange(int(sample_rate_hz * seconds), dtype=np.float64) / sample_rate_hz
    frequencies = np.linspace(440.0, 880.0, t.size)
    phase = 2.0 * np.pi * np.cumsum(frequencies) / sample_rate_hz
    samples = (0.35 * np.sin(phase)).astype(np.float32).reshape(-1, 1)

    events = extract_monophonic_pitch_events(_audio(samples, sample_rate_hz=sample_rate_hz))

    assert events[0].pitch_midi <= 71
    assert events[-1].pitch_midi >= 79
    assert events[-1].pitch_midi > events[0].pitch_midi


def test_drum_extraction_classifies_synthetic_kick_snare_and_hat_onsets() -> None:
    audio = _audio(_drum_fixture(sample_rate_hz=16_000), sample_rate_hz=16_000)

    onsets = extract_drum_onsets(audio)

    assert _has_onset_near(onsets.kick_onsets, 0.25, tolerance=0.08)
    assert _has_onset_near(onsets.snare_onsets, 0.75, tolerance=0.08)
    assert _has_onset_near(onsets.hat_onsets, 1.25, tolerance=0.08)


def test_mapping_uses_midi_core_track_roles_and_drum_notes() -> None:
    tracks = map_features_to_tracks(
        tempo_grid=TempoGrid(tempo_bpm=120.0, beat_grid=(0.0, 0.5, 1.0, 1.5)),
        pitch_events=(PitchEvent(time_seconds=0.0, pitch_midi=69),),
        drum_onsets=DrumOnsets(kick_onsets=(0.0,), snare_onsets=(0.5,), hat_onsets=(1.0,)),
        duration_seconds=2.0,
        include_bass=True,
        include_chords=True,
    )

    roles = [track.role for track in tracks]
    drum_track = next(track for track in tracks if track.role == "drums")
    drum_pitches = [note.pitch for note in drum_track.patterns[0].ordered_notes]

    assert roles == ["melody", "drums", "bass", "chords"]
    assert drum_pitches == [36, 38, 42]


def test_audio_to_midi_render_returns_valid_standard_midi_bytes() -> None:
    audio = _audio(_drum_fixture(sample_rate_hz=16_000), sample_rate_hz=16_000)

    result = extract_audio_to_midi(audio, include_bass=False, include_chords=False)

    assert result.midi_bytes.startswith(b"MThd")
    assert result.midi_bytes.count(b"MTrk") >= 2
    assert result.midi_bytes == render_to_midi(result.tracks)


def _audio(samples: np.ndarray, sample_rate_hz: int = 16_000) -> LoadedAudio:
    samples = np.asarray(samples, dtype=np.float32)
    frames = int(samples.shape[0])
    channels = int(samples.shape[1])
    return LoadedAudio(
        samples=samples,
        sample_rate_hz=sample_rate_hz,
        channels=channels,
        frames=frames,
        duration_seconds=float(frames / sample_rate_hz),
        peak_abs=float(np.max(np.abs(samples))) if samples.size else 0.0,
        filename="generated.wav",
    )


def _click_track(bpm: int, seconds: float, sample_rate_hz: int) -> np.ndarray:
    samples = np.zeros(int(seconds * sample_rate_hz), dtype=np.float32)
    interval = 60.0 / bpm
    click_length = int(0.01 * sample_rate_hz)
    click = np.hanning(click_length).astype(np.float32)
    time = 0.25
    while time < seconds:
        start = int(round(time * sample_rate_hz))
        available = max(0, min(click_length, samples.size - start))
        samples[start : start + click_length] += click[:available]
        time += interval
    return samples.reshape(-1, 1)


def _sine_melody(
    frequencies: tuple[float, ...],
    *,
    seconds_per_note: float,
    sample_rate_hz: int,
) -> np.ndarray:
    segments = []
    for frequency in frequencies:
        t = np.arange(int(seconds_per_note * sample_rate_hz), dtype=np.float64) / sample_rate_hz
        envelope = np.ones_like(t)
        fade = max(1, int(0.01 * sample_rate_hz))
        envelope[:fade] = np.linspace(0.0, 1.0, fade)
        envelope[-fade:] = np.linspace(1.0, 0.0, fade)
        segments.append(0.35 * np.sin(2.0 * np.pi * frequency * t) * envelope)
    return np.concatenate(segments).astype(np.float32).reshape(-1, 1)


def _drum_fixture(sample_rate_hz: int) -> np.ndarray:
    samples = np.zeros(int(1.75 * sample_rate_hz), dtype=np.float32)
    _add_tone_burst(
        samples, sample_rate_hz, start_seconds=0.25, frequency_hz=60.0, length_seconds=0.09
    )
    _add_tone_burst(
        samples, sample_rate_hz, start_seconds=0.75, frequency_hz=900.0, length_seconds=0.05
    )
    _add_tone_burst(
        samples,
        sample_rate_hz,
        start_seconds=1.25,
        frequency_hz=6_000.0,
        length_seconds=0.035,
    )
    return samples.reshape(-1, 1)


def _add_tone_burst(
    samples: np.ndarray,
    sample_rate_hz: int,
    *,
    start_seconds: float,
    frequency_hz: float,
    length_seconds: float,
) -> None:
    start = int(round(start_seconds * sample_rate_hz))
    length = int(round(length_seconds * sample_rate_hz))
    t = np.arange(length, dtype=np.float64) / sample_rate_hz
    envelope = np.hanning(length)
    burst = 0.85 * np.sin(2.0 * np.pi * frequency_hz * t) * envelope
    samples[start : start + length] += burst.astype(np.float32)


def _has_onset_near(onsets: tuple[float, ...], expected: float, *, tolerance: float) -> bool:
    return any(abs(onset - expected) <= tolerance for onset in onsets)

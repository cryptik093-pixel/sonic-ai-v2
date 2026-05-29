from __future__ import annotations

from collections.abc import Mapping, Sequence
from collections import Counter
from dataclasses import dataclass, field
from random import Random
from typing import Literal
from app.core.logging import get_logger

logger = get_logger(__name__)

TrackRole = Literal["melody", "bass", "chords", "drums"]
TimeSignature = tuple[int, int]
Seed = int | None
type ScaleMode = Literal[
    "major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"
]
type ScaleSpec = ScaleMode | tuple[str, ScaleMode]

MAJOR_SCALE_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE_INTERVALS = (0, 2, 3, 5, 7, 8, 10)
SCALE_INTERVALS = {
    "major": MAJOR_SCALE_INTERVALS,
    "minor": MINOR_SCALE_INTERVALS,
    "dorian": (0, 2, 3, 5, 7, 9, 10),
    "phrygian": (0, 1, 3, 5, 7, 8, 10),
    "lydian": (0, 2, 4, 6, 7, 9, 11),
    "mixolydian": (0, 2, 4, 5, 7, 9, 10),
    "locrian": (0, 1, 3, 5, 6, 8, 10),
}
DEFAULT_CHORD_DEGREES = (1, 5, 6, 4)
DRUM_PITCHES = {
    "kick": 36,
    "snare": 38,
    "closed_hat": 42,
}


@dataclass(frozen=True)
class Note:
    """A beat-based MIDI note event ready for later DAW export.

    The object is immutable, JSON-serializable through dataclass helpers, and
    validates MIDI-safe pitch, velocity, and channel ranges at construction.
    """

    pitch: int
    velocity: int
    start_time: float
    duration: float
    channel: int = 0

    def __post_init__(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError("Note pitch must be between 0 and 127.")
        if not 0 <= self.velocity <= 127:
            raise ValueError("Note velocity must be between 0 and 127.")
        if self.start_time < 0:
            raise ValueError("Note start_time must be non-negative.")
        if self.duration <= 0:
            raise ValueError("Note duration must be positive.")
        if not 0 <= self.channel <= 15:
            raise ValueError("Note channel must be between 0 and 15.")


@dataclass(frozen=True)
class Pattern:
    """An ordered beat-based note pattern at a fixed tempo.

    Notes are stored in deterministic playback order. Timing uses beats so the
    same data can later be rendered at different tick resolutions or exported
    into DAW-oriented formats without changing musical intent.
    """

    notes: Sequence[Note]
    tempo_bpm: int
    time_signature: TimeSignature = (4, 4)
    length_beats: float | None = None
    _ordered_notes: tuple[Note, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        _validate_tempo(self.tempo_bpm)
        _validate_time_signature(self.time_signature)
        ordered_notes = tuple(sorted(self.notes, key=lambda note: (note.start_time, note.pitch)))
        object.__setattr__(self, "notes", ordered_notes)
        object.__setattr__(self, "_ordered_notes", ordered_notes)
        if self.length_beats is not None and self.length_beats <= 0:
            raise ValueError("Pattern length_beats must be positive when provided.")

    @property
    def ordered_notes(self) -> tuple[Note, ...]:
        return self._ordered_notes

    @property
    def total_beats(self) -> float:
        if self.length_beats is not None:
            return self.length_beats
        return max((note.start_time + note.duration for note in self._ordered_notes), default=0.0)

    @property
    def tempo(self) -> int:
        """Tempo alias for callers that use the product-facing domain term."""

        return self.tempo_bpm


@dataclass(frozen=True)
class Track:
    """A named internal MIDI track grouped by musical role."""

    name: str
    role: TrackRole
    patterns: Sequence[Pattern]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Track name is required.")
        if not self.patterns:
            raise ValueError("Track must include at least one pattern.")
        object.__setattr__(self, "patterns", tuple(self.patterns))


@dataclass(frozen=True)
class MelodyConfig:
    tempo_bpm: int = 120
    bars: int = 2
    root_pitch: int = 60
    scale: ScaleSpec = "minor"
    notes_per_bar: int = 8
    velocity: int = 92
    contour_rule: str = "balanced_stepwise_contour"
    rhythm_grid: str = "straight_eighth_grid"
    channel: int = 0


@dataclass(frozen=True)
class DrumPatternConfig:
    tempo_bpm: int = 120
    bars: int = 1
    velocity: int = 96
    channel: int = 9
    rhythm_grid: str = "basic_four_four_grid"


@dataclass(frozen=True)
class BasslineConfig:
    tempo_bpm: int = 120
    bars: int = 2
    root_pitch: int = 36
    scale: ScaleSpec = "minor"
    notes_per_bar: int = 4
    velocity: int = 96
    channel: int = 1
    rhythm_grid: str = "straight_eighth_grid"


@dataclass(frozen=True)
class ChordProgressionConfig:
    tempo_bpm: int = 120
    bars: int = 4
    root_pitch: int = 48
    scale: ScaleSpec = "minor"
    velocity: int = 84
    channel: int = 2
    degrees: Sequence[int] = DEFAULT_CHORD_DEGREES


@dataclass(frozen=True)
class ArrangementConfig:
    tempo_bpm: int = 120
    bars: int = 4
    root_pitch: int = 60
    scale: ScaleSpec = "minor"
    density: Literal["sparse", "medium", "dense"] = "medium"
    velocity: int = 92
    rhythm_grid: str = "straight_eighth_grid"
    contour_rule: str = "balanced_stepwise_contour"
    chord_degrees: Sequence[int] = DEFAULT_CHORD_DEGREES


class MIDIEngine:
    """Small deterministic MIDI generation core for internal Sonic AI tools.

    Each generator is pure with no global state. Supplying the same config and
    seed returns the same note sequence. When no seed is supplied, generators
    use fixed deterministic movement rules instead of process-level randomness.

    Future phases can replace individual generator strategies or add
    audio-to-MIDI extraction while preserving the Note/Pattern/Track domain
    objects and the render_to_midi adapter.
    """

    def generate_melody(
        self,
        config: MelodyConfig | Mapping[str, object],
        seed: int | None = None,
    ) -> Track:
        cfg = _coerce_config(config, MelodyConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        if cfg.notes_per_bar <= 0:
            raise ValueError("notes_per_bar must be positive.")

        rng = _rng(seed)
        scale = _scale_intervals(cfg.scale)
        root_pitch = _root_pitch_for_scale(cfg.root_pitch, cfg.scale)
        start_times = _melody_start_times(cfg.bars, cfg.notes_per_bar, cfg.rhythm_grid)
        note_duration = _melody_note_duration(start_times, cfg.bars * 4.0)
        degree_index = 0
        notes: list[Note] = []

        for step, start_time in enumerate(start_times):
            if rng is None:
                degree_index += _deterministic_melody_motion(step, cfg.contour_rule)
            else:
                degree_index += rng.choice((-1, 1, 1, 2 if step % 7 == 0 else 1))

            degree_index = max(0, min(len(scale) + 1, degree_index))
            octave, degree = divmod(degree_index, len(scale))
            pitch = root_pitch + (12 * octave) + scale[degree]
            notes.append(
                Note(
                    pitch=_clamp_midi(pitch),
                    velocity=cfg.velocity,
                    start_time=start_time,
                    duration=note_duration,
                    channel=cfg.channel,
                )
            )

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        track = Track(name="Generated Melody", role="melody", patterns=(pattern,))
        try:
            notes_count = len(pattern.ordered_notes)
        except Exception:
            notes_count = None

        try:
            pitch_hist = dict(Counter(n.pitch for n in pattern.ordered_notes))
            vel_hist = dict(Counter(n.velocity for n in pattern.ordered_notes))
        except Exception:
            pitch_hist = None
            vel_hist = None

        logger.info(
            "midi_generation: track summary",
            extra={
                "track_name": track.name,
                "role": "melody",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "root_pitch": cfg.root_pitch,
                "scale": str(cfg.scale),
                "pitch_histogram": pitch_hist,
                "velocity_histogram": vel_hist,
            },
        )

        logger.info(
            "generate_melody complete",
            extra={
                "role": "melody",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "root_pitch": cfg.root_pitch,
                "scale": str(cfg.scale),
            },
        )
        return track

    def generate_drum_pattern(
        self, config: DrumPatternConfig | Mapping[str, object], seed: int | None = None
    ) -> Track:
        cfg = _coerce_config(config, DrumPatternConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        rng = _rng(seed)
        notes: list[Note] = []

        for bar in range(cfg.bars):
            bar_start = bar * 4.0
            for beat in _kick_beats_for_grid(cfg.rhythm_grid):
                notes.append(_drum_note("kick", bar_start + beat, cfg.velocity, cfg.channel))
            for beat in _snare_beats_for_grid(cfg.rhythm_grid):
                notes.append(_drum_note("snare", bar_start + beat, cfg.velocity, cfg.channel))
            hat_grid = _hat_beats_for_grid(cfg.rhythm_grid)
            for step, beat in enumerate(hat_grid):
                velocity = cfg.velocity - 18
                if rng is not None and step % 2 == 1:
                    velocity += rng.choice((0, 4, 8))
                notes.append(_drum_note("closed_hat", bar_start + beat, velocity, cfg.channel))

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        track = Track(name="Generated Drums", role="drums", patterns=(pattern,))
        try:
            notes_count = len(pattern.ordered_notes)
        except Exception:
            notes_count = None

        try:
            pitch_hist = dict(Counter(n.pitch for n in pattern.ordered_notes))
            vel_hist = dict(Counter(n.velocity for n in pattern.ordered_notes))
        except Exception:
            pitch_hist = None
            vel_hist = None

        logger.info(
            "midi_generation: track summary",
            extra={
                "track_name": track.name,
                "role": "drums",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "rhythm_grid": cfg.rhythm_grid,
                "pitch_histogram": pitch_hist,
                "velocity_histogram": vel_hist,
            },
        )

        logger.info(
            "generate_drum_pattern complete",
            extra={
                "role": "drums",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "rhythm_grid": cfg.rhythm_grid,
            },
        )
        return track

    def generate_bassline(
        self,
        config: BasslineConfig | Mapping[str, object],
        seed: int | None = None,
    ) -> Track:
        cfg = _coerce_config(config, BasslineConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        if cfg.notes_per_bar <= 0:
            raise ValueError("notes_per_bar must be positive.")
        rng = _rng(seed)
        scale = _scale_intervals(cfg.scale)
        root_pitch = _root_pitch_for_scale(cfg.root_pitch, cfg.scale)
        notes: list[Note] = []

        for bar in range(cfg.bars):
            bar_start = bar * 4.0
            starts = _bass_starts_for_grid(cfg.rhythm_grid, cfg.notes_per_bar)
            for step, beat in enumerate(starts):
                if step == 0:
                    degree = 0
                elif step == len(starts) - 1:
                    degree = len(scale)
                elif rng is None:
                    degree = 4
                else:
                    degree = rng.choice((0, 2, 4))
                octave, scale_degree = divmod(degree, len(scale))
                pitch = root_pitch + (12 * octave) + scale[scale_degree]
                velocity = cfg.velocity if step == 0 else cfg.velocity - 8
                notes.append(
                    Note(_clamp_midi(pitch), velocity, bar_start + beat, 0.75, cfg.channel)
                )

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        track = Track(name="Generated Bass", role="bass", patterns=(pattern,))
        try:
            notes_count = len(pattern.ordered_notes)
        except Exception:
            notes_count = None

        try:
            pitch_hist = dict(Counter(n.pitch for n in pattern.ordered_notes))
            vel_hist = dict(Counter(n.velocity for n in pattern.ordered_notes))
        except Exception:
            pitch_hist = None
            vel_hist = None

        logger.info(
            "midi_generation: track summary",
            extra={
                "track_name": track.name,
                "role": "bass",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "root_pitch": cfg.root_pitch,
                "pitch_histogram": pitch_hist,
                "velocity_histogram": vel_hist,
            },
        )

        logger.info(
            "generate_bassline complete",
            extra={
                "role": "bass",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "root_pitch": cfg.root_pitch,
            },
        )
        return track

    def generate_chord_progression(
        self, config: ChordProgressionConfig | Mapping[str, object], seed: int | None = None
    ) -> Track:
        cfg = _coerce_config(config, ChordProgressionConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        if not cfg.degrees:
            raise ValueError("degrees must include at least one chord degree.")

        scale = _scale_intervals(cfg.scale)
        root_pitch = _root_pitch_for_scale(cfg.root_pitch, cfg.scale)
        notes: list[Note] = []
        for bar in range(cfg.bars):
            degree = cfg.degrees[bar % len(cfg.degrees)]
            if not 1 <= degree <= 7:
                raise ValueError("Chord degrees must be between 1 and 7.")
            root = root_pitch + scale[degree - 1]
            chord_intervals = _triad_intervals(cfg.scale, degree)
            for interval in chord_intervals:
                notes.append(Note(root + interval, cfg.velocity, bar * 4.0, 3.75, cfg.channel))

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        track = Track(name="Generated Chords", role="chords", patterns=(pattern,))
        try:
            notes_count = len(pattern.ordered_notes)
        except Exception:
            notes_count = None

        try:
            pitch_hist = dict(Counter(n.pitch for n in pattern.ordered_notes))
            vel_hist = dict(Counter(n.velocity for n in pattern.ordered_notes))
        except Exception:
            pitch_hist = None
            vel_hist = None

        logger.info(
            "midi_generation: track summary",
            extra={
                "track_name": track.name,
                "role": "chords",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "degrees": tuple(cfg.degrees),
                "pitch_histogram": pitch_hist,
                "velocity_histogram": vel_hist,
            },
        )

        logger.info(
            "generate_chord_progression complete",
            extra={
                "role": "chords",
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes": notes_count,
                "seed": seed,
                "degrees": tuple(cfg.degrees),
            },
        )
        return track

    def generate_arrangement(
        self,
        config: ArrangementConfig | Mapping[str, object],
        seed: Seed = None,
    ) -> tuple[Track, Track, Track, Track]:
        """Generate a deterministic multi-track musical idea for DAW export.

        This is still rule-based, but it avoids the weak one-lane output that
        makes a MIDI file feel unfinished. Same config plus same seed produces
        the same full arrangement.
        """

        cfg = _coerce_config(config, ArrangementConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        root = _root_pitch_for_scale(cfg.root_pitch, cfg.scale)
        notes_per_bar = _arrangement_notes_per_bar(cfg.density)
        drum_velocity = _clamp_velocity(cfg.velocity + 6)
        bass_velocity = _clamp_velocity(cfg.velocity + 2)
        chord_velocity = _clamp_velocity(cfg.velocity - 10)

        melody = self.generate_melody(
            MelodyConfig(
                tempo_bpm=cfg.tempo_bpm,
                bars=cfg.bars,
                root_pitch=max(48, min(84, root)),
                scale=cfg.scale,
                notes_per_bar=notes_per_bar,
                velocity=_clamp_velocity(cfg.velocity),
                contour_rule=cfg.contour_rule,
                rhythm_grid=cfg.rhythm_grid,
            ),
            seed=_seed_offset(seed, 11),
        )
        bass = self.generate_bassline(
            BasslineConfig(
                tempo_bpm=cfg.tempo_bpm,
                bars=cfg.bars,
                root_pitch=max(24, min(48, root - 24)),
                scale=cfg.scale,
                notes_per_bar=max(3, notes_per_bar // 2),
                velocity=bass_velocity,
                rhythm_grid=cfg.rhythm_grid,
            ),
            seed=_seed_offset(seed, 23),
        )
        chords = self.generate_chord_progression(
            ChordProgressionConfig(
                tempo_bpm=cfg.tempo_bpm,
                bars=cfg.bars,
                root_pitch=max(36, min(60, root - 12)),
                scale=cfg.scale,
                velocity=chord_velocity,
                degrees=cfg.chord_degrees,
            ),
            seed=_seed_offset(seed, 37),
        )
        drums = self.generate_drum_pattern(
            DrumPatternConfig(
                tempo_bpm=cfg.tempo_bpm,
                bars=cfg.bars,
                velocity=drum_velocity,
                rhythm_grid=cfg.rhythm_grid,
            ),
            seed=_seed_offset(seed, 41),
        )
        tracks = (melody, bass, chords, drums)
        try:
            counts = {t.role: sum(len(p.ordered_notes) for p in t.patterns) for t in tracks}
        except Exception:
            counts = None
        total_notes = sum(counts.values()) if counts else 0
        if total_notes == 0:
            # Defensive deterministic fallback: produce a simple 8-step scalar melody
            # so the system never returns a silent MIDI file.
            logger.warning(
                "arrangement produced zero notes, applying deterministic fallback melody",
                extra={"seed": seed, "root": cfg.root_pitch, "scale": str(cfg.scale)},
            )
            fallback = _fallback_melody(
                root_pitch=max(48, min(84, root)),
                scale=cfg.scale,
                bars=cfg.bars,
                seed=_seed_offset(seed, 97),
                tempo_bpm=cfg.tempo_bpm,
            )
            tracks = (fallback, bass, chords, drums)

        # Per-track summaries and histograms
        per_track_hist = {}
        try:
            for idx, t in enumerate(tracks):
                all_notes = [n for p in t.patterns for n in p.ordered_notes]
                pitch_hist = dict(Counter(n.pitch for n in all_notes))
                vel_hist = dict(Counter(n.velocity for n in all_notes))
                per_track_hist[t.role] = {"notes": len(all_notes), "pitch_histogram": pitch_hist, "velocity_histogram": vel_hist}
        except Exception:
            per_track_hist = None

        total_events = sum((v["notes"] for v in per_track_hist.values())) if per_track_hist else total_notes

        logger.info(
            "midi_generation: assembly complete",
            extra={
                "roles": [t.role for t in tracks],
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes_per_track": counts,
                "per_track_histograms": per_track_hist,
                "total_tracks": len(tracks),
                "total_notes": total_notes,
                "total_events": total_events,
                "seed": seed,
            },
        )
        logger.info(
            "generate_arrangement complete",
            extra={
                "roles": [t.role for t in tracks],
                "tempo": cfg.tempo_bpm,
                "bars": cfg.bars,
                "notes_per_track": counts,
                "seed": seed,
            },
        )
        return tracks


def render_to_midi(tracks: Track | Sequence[Track], ticks_per_beat: int = 480) -> bytes:
    """Convert internal tracks to a Standard MIDI File byte stream.

    This is an internal adapter only. It writes a minimal format-1 MIDI file
    with a conductor track plus one note track per Track. No public endpoint
    should call this until the API contract is explicitly extended.
    """

    track_list = (tracks,) if isinstance(tracks, Track) else tuple(tracks)
    if not track_list:
        raise ValueError("At least one track is required for MIDI export.")
    if ticks_per_beat <= 0:
        raise ValueError("ticks_per_beat must be positive.")

    tempo_bpm = track_list[0].patterns[0].tempo_bpm
    time_signature = track_list[0].patterns[0].time_signature
    midi_tracks = [_tempo_track(tempo_bpm, time_signature)]
    midi_tracks.extend(_note_track(track, ticks_per_beat) for track in track_list)

    # Compute lightweight totals for observability before serializing
    try:
        total_events = sum(len([n for p in t.patterns for n in p.ordered_notes]) for t in track_list)
    except Exception:
        total_events = None
    logger.info(
        "midi_generation: serializing",
        extra={"total_tracks": len(track_list), "total_events": total_events, "ticks_per_beat": ticks_per_beat},
    )

    header = b"MThd" + (6).to_bytes(4, "big")
    header += (1).to_bytes(2, "big")
    header += len(midi_tracks).to_bytes(2, "big")
    header += ticks_per_beat.to_bytes(2, "big")
    midi_bytes = header + b"".join(midi_tracks)
    try:
        track_count = max(0, len(midi_tracks) - 1)
    except Exception:
        track_count = None
    logger.info(
        "render_to_midi complete",
        extra={"track_count": track_count, "ticks_per_beat": ticks_per_beat, "byte_length": len(midi_bytes)},
    )
    logger.info(
        "midi_generation: serialization complete",
        extra={"midi_bytes_len": len(midi_bytes), "track_count": track_count, "total_events": total_events},
    )
    return midi_bytes


def tracks_to_midi_bytes(tracks: Track | Sequence[Track], ticks_per_beat: int = 480) -> bytes:
    """Backward-compatible internal alias for render_to_midi."""

    return render_to_midi(tracks, ticks_per_beat=ticks_per_beat)


def _coerce_config[T](config: T | Mapping[str, object], config_type: type[T]) -> T:
    if isinstance(config, config_type):
        return config
    if isinstance(config, Mapping):
        return config_type(**config)
    raise TypeError(f"config must be {config_type.__name__} or a mapping.")


def _rng(seed: int | None) -> Random | None:
    return Random(seed) if seed is not None else None


def _seed_offset(seed: Seed, offset: int) -> Seed:
    return None if seed is None else seed + offset


def _scale_mode(scale: ScaleSpec | str) -> str:
    mode = scale[1] if isinstance(scale, tuple) else scale
    if mode in SCALE_INTERVALS:
        return mode
    raise ValueError("scale must be a supported major, minor, or modal scale.")


def _scale_intervals(scale: ScaleSpec | str) -> tuple[int, ...]:
    return SCALE_INTERVALS[_scale_mode(scale)]


def _root_pitch_for_scale(root_pitch: int, scale: ScaleSpec | str) -> int:
    if not isinstance(scale, tuple):
        return root_pitch
    pitch_class = _key_to_pitch_class(scale[0])
    octave_base = root_pitch - (root_pitch % 12)
    return _clamp_midi(octave_base + pitch_class)


def _key_to_pitch_class(key: str) -> int:
    pitch_classes = {
        "c": 0,
        "c#": 1,
        "db": 1,
        "d": 2,
        "d#": 3,
        "eb": 3,
        "e": 4,
        "f": 5,
        "f#": 6,
        "gb": 6,
        "g": 7,
        "g#": 8,
        "ab": 8,
        "a": 9,
        "a#": 10,
        "bb": 10,
        "b": 11,
    }
    return pitch_classes.get(key.lower(), 0)


def _triad_intervals(scale: ScaleSpec | str, degree: int) -> tuple[int, int, int]:
    intervals = _scale_intervals(scale)
    root_index = degree - 1
    root = intervals[root_index]
    third = intervals[(root_index + 2) % len(intervals)]
    fifth = intervals[(root_index + 4) % len(intervals)]
    if root_index + 2 >= len(intervals):
        third += 12
    if root_index + 4 >= len(intervals):
        fifth += 12
    return (0, third - root, fifth - root)


def _melody_start_times(bars: int, notes_per_bar: int, rhythm_grid: str) -> tuple[float, ...]:
    total_steps = bars * notes_per_bar
    step_beats = 4.0 / notes_per_bar
    starts = []
    for step in range(total_steps):
        start = step * step_beats
        if rhythm_grid in {"offbeat_eighth_grid", "laid_back_eighth_grid"} and step % 2 == 1:
            start += min(0.12, step_beats * 0.25)
        elif rhythm_grid == "eighth_hat_grid" and step % 4 == 3:
            start += min(0.06, step_beats * 0.18)
        elif rhythm_grid == "swing_sixteenth_grid" and step % 2 == 1:
            start += min(0.08, step_beats * 0.2)
        starts.append(round(min(start, bars * 4.0 - 0.01), 6))
    return tuple(starts)


def _melody_note_duration(start_times: tuple[float, ...], total_beats: float) -> float:
    if len(start_times) < 2:
        return round(total_beats * 0.9, 6)
    shortest_gap = min(
        later - earlier for earlier, later in zip(start_times, start_times[1:], strict=False)
    )
    return round(max(0.05, shortest_gap * 0.9), 6)


def _deterministic_melody_motion(step: int, contour_rule: str) -> int:
    if contour_rule == "low_narrow_minor_contour":
        return 0 if step % 4 == 0 else (1 if step % 3 == 0 else -1)
    if contour_rule == "wide_leap_slow_contour":
        return 2 if step % 4 == 0 else (-1 if step % 2 == 0 else 0)
    if contour_rule == "accented_forward_contour":
        return 2 if step % 3 == 0 else 1
    if contour_rule == "slow_sustained_upper_contour":
        return 1 if step % 4 == 0 else 0
    if contour_rule == "offbeat_staccato_contour":
        return 1 if step % 2 == 1 else -1
    if contour_rule == "upper_major_contour":
        return 1 if step % 3 else 2
    if step % 8 == 0:
        return 0
    if step % 7 == 0:
        return 2
    if step % 5 == 0:
        return -1
    return 1 if step % 2 == 0 else -1


def _drum_note(name: str, start_time: float, velocity: int, channel: int) -> Note:
    return Note(
        pitch=DRUM_PITCHES[name],
        velocity=_clamp_velocity(velocity),
        start_time=round(start_time, 6),
        duration=0.25,
        channel=channel,
    )


def _bass_starts_for_grid(rhythm_grid: str, notes_per_bar: int) -> tuple[float, ...]:
    if rhythm_grid == "offbeat_eighth_grid":
        starts = (0.5, 1.5, 2.5, 3.5)
    elif rhythm_grid == "eighth_hat_grid":
        starts = (0.0, 1.5, 2.5, 3.5)
    elif rhythm_grid == "triplet_hat_grid":
        starts = (0.0, 1.333333, 2.5, 3.333333)
    else:
        starts = (0.0, 2.0, 3.0)
    return starts[: max(1, min(notes_per_bar, len(starts)))]


def _kick_beats_for_grid(rhythm_grid: str) -> tuple[float, ...]:
    if rhythm_grid == "quarter_kick_grid":
        return (0.0, 1.0, 2.0, 3.0)
    if rhythm_grid == "eighth_hat_grid":
        return (0.0, 1.5, 2.5, 3.5)
    if rhythm_grid == "triplet_hat_grid":
        return (0.0, 2.5)
    if rhythm_grid == "swing_sixteenth_grid":
        return (0.0, 2.0, 2.75)
    return (0.0, 2.0)


def _snare_beats_for_grid(rhythm_grid: str) -> tuple[float, ...]:
    if rhythm_grid == "triplet_hat_grid":
        return (1.5, 3.0)
    return (1.0, 3.0)


def _hat_beats_for_grid(rhythm_grid: str) -> tuple[float, ...]:
    if rhythm_grid == "eighth_hat_grid":
        return tuple(step * 0.25 for step in range(16))
    if rhythm_grid == "triplet_hat_grid":
        return tuple(round(step / 3, 6) for step in range(12))
    if rhythm_grid == "swing_sixteenth_grid":
        return (0.0, 0.58, 1.0, 1.58, 2.0, 2.58, 3.0, 3.58)
    return tuple(step * 0.5 for step in range(8))


def _validate_common_grid(tempo_bpm: int, bars: int) -> None:
    _validate_tempo(tempo_bpm)
    if bars <= 0:
        raise ValueError("bars must be positive.")


def _validate_tempo(tempo_bpm: int) -> None:
    if tempo_bpm <= 0:
        raise ValueError("tempo_bpm must be positive.")


def _validate_time_signature(time_signature: TimeSignature) -> None:
    numerator, denominator = time_signature
    if numerator <= 0 or denominator <= 0:
        raise ValueError("time_signature values must be positive.")
    if denominator & (denominator - 1):
        raise ValueError("time_signature denominator must be a power of two.")


def _clamp_midi(pitch: int) -> int:
    return max(0, min(127, pitch))


def _clamp_velocity(velocity: int) -> int:
    return max(1, min(127, velocity))


def _arrangement_notes_per_bar(density: str) -> int:
    if density == "sparse":
        return 4
    if density == "dense":
        return 12
    return 8


def _tempo_track(tempo_bpm: int, time_signature: TimeSignature) -> bytes:
    microseconds_per_quarter = round(60_000_000 / tempo_bpm)
    numerator, denominator = time_signature
    denominator_power = denominator.bit_length() - 1
    events = bytearray()
    events.extend(_variable_length_quantity(0))
    events.extend(b"\xff\x51\x03")
    events.extend(microseconds_per_quarter.to_bytes(3, "big"))
    events.extend(_variable_length_quantity(0))
    events.extend(b"\xff\x58\x04")
    events.extend(bytes((numerator, denominator_power, 24, 8)))
    events.extend(_end_of_track())
    return _midi_chunk(events)


def _note_track(track: Track, ticks_per_beat: int) -> bytes:
    events: list[tuple[int, int, bytes]] = []
    absolute_offset = 0.0
    for pattern in track.patterns:
        for note in pattern.ordered_notes:
            start_tick = round((absolute_offset + note.start_time) * ticks_per_beat)
            end_tick = round((absolute_offset + note.start_time + note.duration) * ticks_per_beat)
            events.append((start_tick, 1, bytes((0x90 | note.channel, note.pitch, note.velocity))))
            events.append((end_tick, 0, bytes((0x80 | note.channel, note.pitch, 0))))
        absolute_offset += pattern.total_beats

    events.sort(key=lambda event: (event[0], event[1]))
    payload = bytearray()
    payload.extend(_track_name_event(track.name))
    previous_tick = 0
    for absolute_tick, _kind, event_bytes in events:
        payload.extend(_variable_length_quantity(absolute_tick - previous_tick))
        payload.extend(event_bytes)
        previous_tick = absolute_tick
    payload.extend(_end_of_track())
    return _midi_chunk(payload)


def _track_name_event(name: str) -> bytes:
    encoded = name.encode("ascii", errors="ignore")[:127]
    return b"\x00\xff\x03" + bytes((len(encoded),)) + encoded


def _end_of_track() -> bytes:
    return b"\x00\xff\x2f\x00"


def _midi_chunk(payload: bytes | bytearray) -> bytes:
    return b"MTrk" + len(payload).to_bytes(4, "big") + bytes(payload)


def _variable_length_quantity(value: int) -> bytes:
    if value < 0:
        raise ValueError("MIDI delta time cannot be negative.")
    buffer = value & 0x7F
    value >>= 7
    while value:
        buffer <<= 8
        buffer |= (value & 0x7F) | 0x80
        value >>= 7

    output = bytearray()
    while True:
        output.append(buffer & 0xFF)
        if buffer & 0x80:
            buffer >>= 8
        else:
            break
    return bytes(output)


def _fallback_melody(
    root_pitch: int, scale: ScaleSpec | str, bars: int, seed: Seed = None, tempo_bpm: int = 120
) -> Track:
    """Deterministic 8-step scalar fallback melody used as a last resort.

    The melody is deterministic for the same seed. If seed is None, we use
    a fixed zero seed to ensure reproducible behavior across environments.
    """
    rng = Random(seed if seed is not None else 0)
    intervals = _scale_intervals(scale)
    total_beats = max(1, bars) * 4.0
    steps = 8
    step_beats = total_beats / steps
    notes: list[Note] = []
    for i in range(steps):
        start_time = round(i * step_beats, 6)
        degree = (i * 2) % len(intervals)
        octave = i // len(intervals)
        pitch = root_pitch + (12 * octave) + intervals[degree]
        # small deterministic octave hop occasionally
        if rng.randint(0, 7) == 0:
            pitch += 12
        duration = round(max(0.05, step_beats * 0.9), 6)
        velocity = _clamp_velocity(92 - (i % 3) * 6)
        notes.append(Note(pitch=_clamp_midi(pitch), velocity=velocity, start_time=start_time, duration=duration, channel=0))

    pattern = Pattern(notes=notes, tempo_bpm=tempo_bpm, length_beats=total_beats)
    track = Track(name="Fallback Melody", role="melody", patterns=(pattern,))
    try:
        notes_count = len(pattern.ordered_notes)
    except Exception:
        notes_count = None
    logger.info(
        "fallback_melody generated",
        extra={"notes": notes_count, "bars": bars, "tempo": tempo_bpm, "seed": seed},
    )
    return track

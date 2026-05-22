from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from random import Random
from typing import Literal

TrackRole = Literal["melody", "bass", "chords", "drums"]
TimeSignature = tuple[int, int]
type ScaleSpec = Literal["major", "minor"] | tuple[str, Literal["major", "minor"]]

MAJOR_SCALE_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
MINOR_SCALE_INTERVALS = (0, 2, 3, 5, 7, 8, 10)
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


@dataclass(frozen=True)
class BasslineConfig:
    tempo_bpm: int = 120
    bars: int = 2
    root_pitch: int = 36
    scale: ScaleSpec = "minor"
    notes_per_bar: int = 4
    velocity: int = 96
    channel: int = 1


@dataclass(frozen=True)
class ChordProgressionConfig:
    tempo_bpm: int = 120
    bars: int = 4
    root_pitch: int = 48
    scale: ScaleSpec = "minor"
    velocity: int = 84
    channel: int = 2
    degrees: Sequence[int] = DEFAULT_CHORD_DEGREES


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
        step_beats = 4.0 / cfg.notes_per_bar
        total_steps = cfg.bars * cfg.notes_per_bar
        degree_index = 0
        notes: list[Note] = []

        for step in range(total_steps):
            if rng is None:
                degree_index += _deterministic_melody_motion(step)
            else:
                degree_index += rng.choice((-1, 1, 1, 2 if step % 7 == 0 else 1))

            degree_index = max(0, min(len(scale) + 1, degree_index))
            octave, degree = divmod(degree_index, len(scale))
            pitch = root_pitch + (12 * octave) + scale[degree]
            notes.append(
                Note(
                    pitch=_clamp_midi(pitch),
                    velocity=cfg.velocity,
                    start_time=round(step * step_beats, 6),
                    duration=round(step_beats * 0.9, 6),
                    channel=cfg.channel,
                )
            )

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        return Track(name="Generated Melody", role="melody", patterns=(pattern,))

    def generate_drum_pattern(
        self, config: DrumPatternConfig | Mapping[str, object], seed: int | None = None
    ) -> Track:
        cfg = _coerce_config(config, DrumPatternConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        rng = _rng(seed)
        notes: list[Note] = []

        for bar in range(cfg.bars):
            bar_start = bar * 4.0
            for beat in (0.0, 2.0):
                notes.append(_drum_note("kick", bar_start + beat, cfg.velocity, cfg.channel))
            for beat in (1.0, 3.0):
                notes.append(_drum_note("snare", bar_start + beat, cfg.velocity, cfg.channel))
            for step in range(8):
                velocity = cfg.velocity - 18
                if rng is not None and step in {1, 3, 5, 7}:
                    velocity += rng.choice((0, 4, 8))
                notes.append(
                    _drum_note("closed_hat", bar_start + step * 0.5, velocity, cfg.channel)
                )

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        return Track(name="Generated Drums", role="drums", patterns=(pattern,))

    def generate_bassline(
        self,
        config: BasslineConfig | Mapping[str, object],
        seed: int | None = None,
    ) -> Track:
        cfg = _coerce_config(config, BasslineConfig)
        _validate_common_grid(cfg.tempo_bpm, cfg.bars)
        rng = _rng(seed)
        scale = _scale_intervals(cfg.scale)
        root_pitch = _root_pitch_for_scale(cfg.root_pitch, cfg.scale)
        notes: list[Note] = []

        for bar in range(cfg.bars):
            bar_start = bar * 4.0
            walk_degree = 4 if rng is None else rng.choice((0, 2, 4))
            notes.extend(
                [
                    Note(root_pitch, cfg.velocity, bar_start, 1.5, cfg.channel),
                    Note(
                        root_pitch + scale[walk_degree],
                        cfg.velocity - 8,
                        bar_start + 2.0,
                        0.75,
                        cfg.channel,
                    ),
                    Note(root_pitch + 12, cfg.velocity - 4, bar_start + 3.0, 0.75, cfg.channel),
                ]
            )

        pattern = Pattern(notes=notes, tempo_bpm=cfg.tempo_bpm, length_beats=cfg.bars * 4.0)
        return Track(name="Generated Bass", role="bass", patterns=(pattern,))

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
        return Track(name="Generated Chords", role="chords", patterns=(pattern,))


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

    header = b"MThd" + (6).to_bytes(4, "big")
    header += (1).to_bytes(2, "big")
    header += len(midi_tracks).to_bytes(2, "big")
    header += ticks_per_beat.to_bytes(2, "big")
    return header + b"".join(midi_tracks)


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


def _scale_mode(scale: ScaleSpec | str) -> Literal["major", "minor"]:
    mode = scale[1] if isinstance(scale, tuple) else scale
    if mode == "major":
        return "major"
    if mode == "minor":
        return "minor"
    raise ValueError("scale must be 'major' or 'minor'.")


def _scale_intervals(scale: ScaleSpec | str) -> tuple[int, ...]:
    mode = _scale_mode(scale)
    if mode == "major":
        return MAJOR_SCALE_INTERVALS
    return MINOR_SCALE_INTERVALS


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


def _triad_intervals(scale: str, degree: int) -> tuple[int, int, int]:
    if _scale_mode(scale) == "major":
        minor_degrees = {2, 3, 6}
    else:
        minor_degrees = {1, 4, 5}
    third = 3 if degree in minor_degrees else 4
    fifth = 7
    return (0, third, fifth)


def _deterministic_melody_motion(step: int) -> int:
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
            events.append((start_tick, 0, bytes((0x90 | note.channel, note.pitch, note.velocity))))
            events.append((end_tick, 1, bytes((0x80 | note.channel, note.pitch, 0))))
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

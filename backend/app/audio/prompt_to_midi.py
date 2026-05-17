from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.audio.midi_generation import (
    BasslineConfig,
    ChordProgressionConfig,
    DrumPatternConfig,
    MelodyConfig,
    MIDIEngine,
    Track,
    render_to_midi,
)

PatternType = Literal["melody", "bassline", "chords", "drums"]
Density = Literal["sparse", "medium", "dense"]
Complexity = Literal["simple", "moderate", "complex"]
EngineScale = Literal["major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"]

DEFAULT_TEMPO_BPM = 120
DEFAULT_KEY = "C"
DEFAULT_MODE = "minor"
DEFAULT_PATTERN_TYPE: PatternType = "melody"
DEFAULT_DENSITY: Density = "medium"
DEFAULT_COMPLEXITY: Complexity = "moderate"

KEY_TO_PITCH_CLASS = {
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

CANONICAL_KEYS = {
    "c": "C",
    "c#": "C#",
    "db": "Db",
    "d": "D",
    "d#": "D#",
    "eb": "Eb",
    "e": "E",
    "f": "F",
    "f#": "F#",
    "gb": "Gb",
    "g": "G",
    "g#": "G#",
    "ab": "Ab",
    "a": "A",
    "a#": "A#",
    "bb": "Bb",
    "b": "B",
}

MODE_KEYWORDS = {
    "major": "major",
    "minor": "minor",
    "aeolian": "minor",
    "dorian": "dorian",
    "phrygian": "phrygian",
    "lydian": "lydian",
    "mixolydian": "mixolydian",
    "locrian": "locrian",
}

PATTERN_KEYWORDS: tuple[tuple[PatternType, tuple[str, ...]], ...] = (
    ("drums", ("drum", "drums", "beat", "808 hats", "hi hat", "hi-hat")),
    ("bassline", ("bassline", "bass line", "bass", "808")),
    ("chords", ("chords", "chord", "progression", "pad", "pads")),
    ("melody", ("melody", "lead", "riff", "topline")),
)

DENSITY_KEYWORDS: tuple[tuple[Density, tuple[str, ...]], ...] = (
    ("sparse", ("sparse", "minimal", "simple space", "half time")),
    ("dense", ("dense", "busy", "fast", "rapid", "packed")),
    ("medium", ("medium", "balanced")),
)

COMPLEXITY_KEYWORDS: tuple[tuple[Complexity, tuple[str, ...]], ...] = (
    ("simple", ("simple", "basic", "easy")),
    ("complex", ("complex", "advanced", "intricate")),
    ("moderate", ("moderate", "balanced")),
)

MOOD_PRIORITY = ("dark", "emotional", "aggressive", "dreamy", "bouncy", "happy")
MOOD_KEYWORDS = {
    "dark": ("dark", "menacing", "evil", "moody"),
    "emotional": ("emotional", "sad", "melancholy", "melodic"),
    "aggressive": ("aggressive", "hard", "heavy", "angry"),
    "dreamy": ("dreamy", "ambient", "spacey", "pad", "floaty"),
    "bouncy": ("bouncy", "bounce", "bouncy", "swing"),
    "happy": ("happy", "bright", "uplifting"),
}

RHYTHM_STYLE_KEYWORDS = {
    "trap": ("trap",),
    "drill": ("drill", "uk drill", "ny drill"),
    "house": ("house", "four on the floor", "dance"),
    "boom_bap": ("boom bap", "boom-bap", "boombap"),
    "rnb": ("rnb", "r&b"),
}

STYLE_TEMPO_DEFAULTS = {
    "trap": 140,
    "drill": 142,
    "house": 124,
    "boom_bap": 92,
    "rnb": 90,
}

STYLE_RHYTHM_GRIDS = {
    "trap": "eighth_hat_grid",
    "drill": "triplet_hat_grid",
    "house": "quarter_kick_grid",
    "boom_bap": "swing_sixteenth_grid",
    "rnb": "laid_back_eighth_grid",
}

MOOD_CONTOURS = {
    "dark": "low_narrow_minor_contour",
    "emotional": "wide_leap_slow_contour",
    "aggressive": "accented_forward_contour",
    "dreamy": "slow_sustained_upper_contour",
    "bouncy": "offbeat_staccato_contour",
    "happy": "upper_major_contour",
}


@dataclass(frozen=True)
class ParsedPrompt:
    """Rule-parsed musical intent extracted from a natural-language prompt.

    Parsing is regex and keyword based only. If multiple keywords conflict, the
    first matching category in the fixed dictionaries wins, and mood conflicts
    are ordered by `MOOD_PRIORITY`. Missing fields use stable defaults.
    """

    raw_prompt: str
    tempo_bpm: int
    key: str
    root_pitch_class: int
    mode: str
    engine_scale: EngineScale
    pattern_type: PatternType
    density: Density
    mood_modifiers: tuple[str, ...]
    primary_mood: str | None
    rhythm_style: str
    complexity: Complexity


@dataclass(frozen=True)
class PromptMidiPlan:
    """Internal mapping from parsed prompt intent to MIDIEngine input config.

    `engine_config` is one of the existing MIDIEngine dataclasses. Additional
    fields document deterministic prompt decisions that the current engine core
    does not expose directly, such as drill triplet intent or dark melodic
    contour. No global random state is used.
    """

    parsed: ParsedPrompt
    engine_config: MelodyConfig | BasslineConfig | ChordProgressionConfig | DrumPatternConfig
    rhythm_grid: str
    contour_rule: str
    chord_degrees: tuple[int, ...]

    @property
    def tempo_bpm(self) -> int:
        return self.parsed.tempo_bpm

    @property
    def key(self) -> str:
        return self.parsed.key

    @property
    def mode(self) -> str:
        return self.parsed.mode

    @property
    def pattern_type(self) -> PatternType:
        return self.parsed.pattern_type

    @property
    def density(self) -> Density:
        return self.parsed.density

    @property
    def mood_modifiers(self) -> tuple[str, ...]:
        return self.parsed.mood_modifiers

    @property
    def primary_mood(self) -> str | None:
        return self.parsed.primary_mood

    @property
    def rhythm_style(self) -> str:
        return self.parsed.rhythm_style

    @property
    def complexity(self) -> Complexity:
        return self.parsed.complexity


@dataclass(frozen=True)
class PromptMidiResult:
    """Internal Prompt-to-MIDI result with rendered bytes and source plan."""

    plan: PromptMidiPlan
    tracks: tuple[Track, ...]
    midi_bytes: bytes


def parse_prompt(prompt: str) -> ParsedPrompt:
    """Parse a prompt into deterministic musical intent fields.

    The parser ignores unsupported words safely. It prefers explicit values
    such as "140 bpm" and "D minor"; otherwise it falls back through rhythm
    style defaults and finally global defaults.
    """

    raw_prompt = prompt or ""
    normalized = _normalize(raw_prompt)
    rhythm_style = _find_rhythm_style(normalized)
    tempo_bpm = _parse_tempo(normalized) or STYLE_TEMPO_DEFAULTS.get(
        rhythm_style, _mood_tempo_default(normalized)
    )
    key, root_pitch_class = _parse_key(normalized)
    mode = _parse_mode(normalized)
    mood_modifiers = _parse_moods(normalized)
    if "dark" in mood_modifiers and mode == "major":
        mode = "minor"
    if "happy" in mood_modifiers and "dark" not in mood_modifiers and mode == DEFAULT_MODE:
        mode = "major"

    return ParsedPrompt(
        raw_prompt=raw_prompt,
        tempo_bpm=tempo_bpm,
        key=key,
        root_pitch_class=root_pitch_class,
        mode=mode,
        engine_scale=_engine_scale(mode),
        pattern_type=_find_pattern_type(normalized),
        density=_find_density(normalized),
        mood_modifiers=mood_modifiers,
        primary_mood=mood_modifiers[0] if mood_modifiers else None,
        rhythm_style=rhythm_style,
        complexity=_find_complexity(normalized),
    )


def build_midi_plan(parsed: ParsedPrompt) -> PromptMidiPlan:
    """Map parsed intent to the current deterministic MIDIEngine dataclasses."""

    bars = _bars_for(parsed)
    velocity = _velocity_for(parsed)
    rhythm_grid = _rhythm_grid_for(parsed)
    contour_rule = _contour_rule_for(parsed)
    chord_degrees = _chord_degrees_for(parsed)

    if parsed.pattern_type == "drums":
        engine_config = DrumPatternConfig(
            tempo_bpm=parsed.tempo_bpm,
            bars=max(1, min(4, bars)),
            velocity=velocity,
            rhythm_grid=rhythm_grid,
        )
    elif parsed.pattern_type == "bassline":
        engine_config = BasslineConfig(
            tempo_bpm=parsed.tempo_bpm,
            bars=bars,
            root_pitch=_root_pitch(parsed, base_octave=36),
            scale=parsed.engine_scale,
            notes_per_bar=_notes_per_bar_for(parsed),
            velocity=velocity,
            rhythm_grid=rhythm_grid,
        )
    elif parsed.pattern_type == "chords":
        engine_config = ChordProgressionConfig(
            tempo_bpm=parsed.tempo_bpm,
            bars=max(2, bars * 2),
            root_pitch=_root_pitch(parsed, base_octave=48),
            scale=parsed.engine_scale,
            velocity=velocity,
            degrees=chord_degrees,
        )
    else:
        engine_config = MelodyConfig(
            tempo_bpm=parsed.tempo_bpm,
            bars=bars,
            root_pitch=_root_pitch(parsed, base_octave=60),
            scale=parsed.engine_scale,
            notes_per_bar=_notes_per_bar_for(parsed),
            velocity=velocity,
            contour_rule=contour_rule,
            rhythm_grid=rhythm_grid,
        )

    return PromptMidiPlan(
        parsed=parsed,
        engine_config=engine_config,
        rhythm_grid=rhythm_grid,
        contour_rule=contour_rule,
        chord_degrees=chord_degrees,
    )


def interpret_prompt(parsed: ParsedPrompt) -> PromptMidiPlan:
    """Interpret a parsed prompt into a deterministic MIDI plan."""

    return build_midi_plan(parsed)


def generate_prompt_midi(prompt: str, *, seed: int | None = None) -> PromptMidiResult:
    """Generate internal MIDI bytes from a prompt through the existing MIDIEngine.

    Same prompt plus same explicit seed produces identical bytes. With no seed,
    MIDIEngine's deterministic non-random movement rules are used.
    """

    parsed = parse_prompt(prompt)
    plan = build_midi_plan(parsed)
    engine = MIDIEngine()

    if parsed.pattern_type == "drums":
        track = engine.generate_drum_pattern(plan.engine_config, seed=seed)
    elif parsed.pattern_type == "bassline":
        track = engine.generate_bassline(plan.engine_config, seed=seed)
    elif parsed.pattern_type == "chords":
        track = engine.generate_chord_progression(plan.engine_config, seed=seed)
    else:
        track = engine.generate_melody(plan.engine_config, seed=seed)

    tracks = (track,)
    return PromptMidiResult(plan=plan, tracks=tracks, midi_bytes=render_to_midi(tracks))


def generate_midi_from_prompt(prompt: str, *, seed: int | None = None) -> bytes:
    """Generate deterministic MIDI bytes from a prompt."""

    return generate_prompt_midi(prompt, seed=seed).midi_bytes


def _normalize(prompt: str) -> str:
    text = prompt.lower().translate(
        {
            ord("\u2011"): "-",
            ord("\u2013"): "-",
            ord("\u2014"): "-",
        }
    )
    text = re.sub(r"[^a-z0-9#&+\-\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_tempo(prompt: str) -> int | None:
    tempo_pattern = (
        r"\b([4-9][0-9]|1[0-9]{2}|2[0-4][0-9]|250)\s*"
        r"(?:bpm|beats per minute)\b"
    )
    match = re.search(tempo_pattern, prompt)
    return int(match.group(1)) if match else None


def _parse_key(prompt: str) -> tuple[str, int]:
    mode_pattern = r"(?:major|minor|dorian|phrygian|lydian|mixolydian|locrian)?"
    match = re.search(
        rf"\b(?:in|key of)\s+([a-g](?:#|b)?)\s*{mode_pattern}\b",
        prompt,
    )
    if not match:
        return DEFAULT_KEY, KEY_TO_PITCH_CLASS[DEFAULT_KEY.lower()]
    key = match.group(1)
    return CANONICAL_KEYS[key], KEY_TO_PITCH_CLASS[key]


def _parse_mode(prompt: str) -> str:
    for keyword, mode in MODE_KEYWORDS.items():
        if _contains_keyword(prompt, keyword):
            return mode
    return DEFAULT_MODE


def _parse_moods(prompt: str) -> tuple[str, ...]:
    moods = []
    for mood in MOOD_PRIORITY:
        if any(_contains_keyword(prompt, keyword) for keyword in MOOD_KEYWORDS[mood]):
            moods.append(mood)
    return tuple(moods)


def _find_pattern_type(prompt: str) -> PatternType:
    for pattern_type, keywords in PATTERN_KEYWORDS:
        if any(_contains_keyword(prompt, keyword) for keyword in keywords):
            return pattern_type
    return DEFAULT_PATTERN_TYPE


def _find_density(prompt: str) -> Density:
    for density, keywords in DENSITY_KEYWORDS:
        if any(_contains_keyword(prompt, keyword) for keyword in keywords):
            return density
    return DEFAULT_DENSITY


def _find_complexity(prompt: str) -> Complexity:
    for complexity, keywords in COMPLEXITY_KEYWORDS:
        if any(_contains_keyword(prompt, keyword) for keyword in keywords):
            return complexity
    return DEFAULT_COMPLEXITY


def _find_rhythm_style(prompt: str) -> str:
    for style, keywords in RHYTHM_STYLE_KEYWORDS.items():
        if any(_contains_keyword(prompt, keyword) for keyword in keywords):
            return style
    return "none"


def _contains_keyword(prompt: str, keyword: str) -> bool:
    escaped = re.escape(keyword).replace(r"\ ", r"\s+")
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", prompt))


def _engine_scale(mode: str) -> EngineScale:
    if mode in {"major", "minor", "dorian", "phrygian", "lydian", "mixolydian", "locrian"}:
        return mode
    return "minor"


def _mood_tempo_default(prompt: str) -> int:
    if _contains_keyword(prompt, "dreamy"):
        return 90
    return DEFAULT_TEMPO_BPM


def _bars_for(parsed: ParsedPrompt) -> int:
    if parsed.complexity == "simple":
        return 1
    if parsed.complexity == "complex":
        return 4
    if parsed.pattern_type == "chords":
        return 2
    return 2


def _velocity_for(parsed: ParsedPrompt) -> int:
    velocity = 92
    if parsed.pattern_type == "drums":
        velocity = 100
    elif parsed.pattern_type == "chords":
        velocity = 82
    if "aggressive" in parsed.mood_modifiers:
        velocity += 14
    if "dreamy" in parsed.mood_modifiers:
        velocity -= 12
    if "emotional" in parsed.mood_modifiers:
        velocity -= 4
    if parsed.density == "dense":
        velocity += 4
    if parsed.density == "sparse":
        velocity -= 6
    return max(1, min(127, velocity))


def _notes_per_bar_for(parsed: ParsedPrompt) -> int:
    if parsed.rhythm_style == "drill":
        return 12
    if parsed.density == "sparse":
        return 4
    if parsed.density == "dense":
        return 12
    if "emotional" in parsed.mood_modifiers or "dreamy" in parsed.mood_modifiers:
        return 6
    return 8


def _root_pitch(parsed: ParsedPrompt, *, base_octave: int) -> int:
    root = base_octave + parsed.root_pitch_class
    if "dark" in parsed.mood_modifiers and parsed.pattern_type in {"melody", "bassline"}:
        root -= 12
    if "dreamy" in parsed.mood_modifiers and parsed.pattern_type == "chords":
        root += 12
    return max(0, min(127, root))


def _rhythm_grid_for(parsed: ParsedPrompt) -> str:
    if "bouncy" in parsed.mood_modifiers:
        return "offbeat_eighth_grid"
    return STYLE_RHYTHM_GRIDS.get(parsed.rhythm_style, "straight_eighth_grid")


def _contour_rule_for(parsed: ParsedPrompt) -> str:
    if parsed.primary_mood is None:
        return "balanced_stepwise_contour"
    return MOOD_CONTOURS[parsed.primary_mood]


def _chord_degrees_for(parsed: ParsedPrompt) -> tuple[int, ...]:
    if "emotional" in parsed.mood_modifiers:
        return (1, 6, 4, 5)
    if "dreamy" in parsed.mood_modifiers:
        return (1, 4, 2, 5)
    if "dark" in parsed.mood_modifiers:
        return (1, 6, 7, 5)
    if parsed.rhythm_style == "trap":
        return (1, 5, 6, 4)
    return (1, 5, 6, 4)


PromptSpec = ParsedPrompt
PromptIntent = PromptMidiPlan

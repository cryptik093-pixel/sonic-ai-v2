from __future__ import annotations

import argparse
import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from app.audio.audio_to_midi import extract_audio_to_midi
from app.audio.loader import load_audio_file
from app.audio.prompt_to_midi import generate_prompt_midi
from app.services.analyzer_service import AnalyzerService, analysis_result_to_dict


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="Local Sonic AI V2 analysis and deterministic MIDI tools.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser("analyze", help="Analyze an audio file and print JSON.")
    analyze.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a supported audio file.",
    )
    analyze.add_argument(
        "--profile",
        default="modern_hiphop_master",
        help="Reference profile id, for example modern_hiphop_master or streaming_balanced.",
    )
    analyze.add_argument("--json-out", type=Path, help="Optional path to write the JSON result.")
    analyze.set_defaults(func=_run_analyze)

    prompt_midi = subparsers.add_parser(
        "prompt-midi",
        help="Generate deterministic MIDI bytes from a text prompt.",
    )
    prompt_midi.add_argument("--prompt", required=True, help="Producer prompt to parse.")
    prompt_midi.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination .mid path.",
    )
    prompt_midi.add_argument("--seed", type=int, help="Optional deterministic variation seed.")
    prompt_midi.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to write generation metadata.",
    )
    prompt_midi.set_defaults(func=_run_prompt_midi)

    audio_midi = subparsers.add_parser(
        "audio-to-midi",
        help="Extract deterministic internal MIDI from an audio file.",
    )
    audio_midi.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path to a supported audio file.",
    )
    audio_midi.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Destination .mid path.",
    )
    audio_midi.add_argument("--scale", choices=("major", "minor"), default="minor")
    audio_midi.add_argument(
        "--no-bass",
        action="store_true",
        help="Disable inferred bass track.",
    )
    audio_midi.add_argument(
        "--no-chords",
        action="store_true",
        help="Disable inferred chord track.",
    )
    audio_midi.add_argument(
        "--json-out",
        type=Path,
        help="Optional path to write extraction metadata.",
    )
    audio_midi.set_defaults(func=_run_audio_to_midi)

    test_audio = subparsers.add_parser(
        "make-test-audio",
        help="Create a deterministic WAV file for local smoke tests.",
    )
    test_audio.add_argument("--output", required=True, type=Path, help="Destination .wav path.")
    test_audio.add_argument("--seconds", type=float, default=4.0)
    test_audio.add_argument("--sample-rate", type=int, default=48_000)
    test_audio.set_defaults(func=_run_make_test_audio)

    return parser


def _run_analyze(args: argparse.Namespace) -> None:
    service = AnalyzerService()
    result = service.analyze_file_path(args.input, profile_id=args.profile)
    payload = {"status": "completed", "analysis": analysis_result_to_dict(result)}
    payload["analysis"]["filename"] = args.input.name
    _emit_json(payload, args.json_out)


def _run_prompt_midi(args: argparse.Namespace) -> None:
    result = generate_prompt_midi(args.prompt, seed=args.seed)
    _write_bytes(args.output, result.midi_bytes)
    payload = {
        "status": "completed",
        "output": str(args.output),
        "prompt": args.prompt,
        "seed": args.seed,
        "plan": _to_plain_python(result.plan),
        "tracks": _tracks_summary(result.tracks),
        "midi_bytes": len(result.midi_bytes),
    }
    _emit_json(payload, args.json_out)


def _run_audio_to_midi(args: argparse.Namespace) -> None:
    audio = load_audio_file(str(args.input))
    result = extract_audio_to_midi(
        audio,
        scale=args.scale,
        include_bass=not args.no_bass,
        include_chords=not args.no_chords,
    )
    _write_bytes(args.output, result.midi_bytes)
    payload = {
        "status": "completed",
        "input": str(args.input),
        "output": str(args.output),
        "tempo_grid": _to_plain_python(result.tempo_grid),
        "pitch_event_count": len(result.pitch_events),
        "drum_onsets": _to_plain_python(result.drum_onsets),
        "tracks": _tracks_summary(result.tracks),
        "midi_bytes": len(result.midi_bytes),
    }
    _emit_json(payload, args.json_out)


def _run_make_test_audio(args: argparse.Namespace) -> None:
    if args.seconds <= 0:
        raise ValueError("--seconds must be positive.")
    if args.sample_rate <= 0:
        raise ValueError("--sample-rate must be positive.")

    samples = _test_audio_samples(seconds=args.seconds, sample_rate_hz=args.sample_rate)
    _ensure_parent(args.output)
    sf.write(args.output, samples, args.sample_rate, format="WAV")
    payload = {
        "status": "completed",
        "output": str(args.output),
        "seconds": args.seconds,
        "sample_rate_hz": args.sample_rate,
    }
    _emit_json(payload, None)


def _test_audio_samples(*, seconds: float, sample_rate_hz: int) -> np.ndarray:
    t = np.arange(int(seconds * sample_rate_hz), dtype=np.float64) / sample_rate_hz
    kick = 0.28 * np.sin(2.0 * np.pi * 60.0 * t) * _pulse_envelope(t, interval=0.5, width=0.08)
    tone = 0.18 * np.sin(2.0 * np.pi * 220.0 * t)
    air = 0.04 * np.sin(2.0 * np.pi * 6_000.0 * t)
    left = kick + tone + air
    right = kick + (0.16 * np.sin(2.0 * np.pi * 330.0 * t)) - air
    stereo = np.column_stack((left, right))
    return np.clip(stereo, -0.95, 0.95).astype(np.float32)


def _pulse_envelope(t: np.ndarray, *, interval: float, width: float) -> np.ndarray:
    position = np.mod(t, interval)
    envelope = np.maximum(0.0, 1.0 - (position / width))
    return np.where(position <= width, envelope, 0.0)


def _tracks_summary(tracks: Any) -> list[dict[str, Any]]:
    summary = []
    for track in tracks:
        note_count = sum(len(pattern.ordered_notes) for pattern in track.patterns)
        total_beats = sum(pattern.total_beats for pattern in track.patterns)
        summary.append(
            {
                "name": track.name,
                "role": track.role,
                "pattern_count": len(track.patterns),
                "note_count": note_count,
                "total_beats": round(total_beats, 6),
            }
        )
    return summary


def _emit_json(payload: dict[str, Any], output_path: Path | None) -> None:
    text = json.dumps(_to_plain_python(payload), indent=2, sort_keys=True)
    if output_path is not None:
        _ensure_parent(output_path)
        output_path.write_text(text + "\n", encoding="utf-8")
    print(text)


def _write_bytes(output_path: Path, payload: bytes) -> None:
    _ensure_parent(output_path)
    output_path.write_bytes(payload)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _to_plain_python(value: Any) -> Any:
    if is_dataclass(value):
        return _to_plain_python(asdict(value))
    if isinstance(value, dict):
        return {str(key): _to_plain_python(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_to_plain_python(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.ndarray):
        return _to_plain_python(value.tolist())
    return value


if __name__ == "__main__":
    raise SystemExit(main())

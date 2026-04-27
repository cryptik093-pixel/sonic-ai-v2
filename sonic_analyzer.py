from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from unified_analyzer import SonicAnalyzer


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid float: {value}") from exc

    if parsed <= 0:
        raise argparse.ArgumentTypeError("Duration must be greater than 0.")
    return parsed


def existing_audio_file(value: str) -> Path:
    path = Path(value).expanduser().resolve()

    if not path.exists():
        raise argparse.ArgumentTypeError(f"File not found: {path}")
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Not a file: {path}")

    allowed_suffixes = {".wav", ".mp3", ".flac", ".aiff", ".aif", ".m4a", ".ogg"}
    if path.suffix.lower() not in allowed_suffixes:
        raise argparse.ArgumentTypeError(
            f"Unsupported audio file type: {path.suffix}. "
            f"Allowed: {', '.join(sorted(allowed_suffixes))}"
        )

    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sonic_analyzer",
        description="Analyze audio with Sonic AI.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
        allow_abbrev=False,
        exit_on_error=False,
    )

    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "filepath",
        nargs="?",
        type=existing_audio_file,
        help="Path to an audio file to analyze.",
    )
    input_group.add_argument(
        "--record",
        action="store_true",
        help="Record from an input device instead of loading a file.",
    )

    parser.add_argument(
        "--device-id",
        type=int,
        default=None,
        help="Input device id for recording mode.",
    )
    parser.add_argument(
        "--duration",
        type=positive_float,
        default=5.0,
        help="Recording duration in seconds.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON output.",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Print only JSON output and skip the human-readable report.",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable analyzer caching for this run.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
    except argparse.ArgumentError as exc:
        print(f"Argument error: {exc}", file=sys.stderr)
        return 2

    if args.record and args.device_id is None:
        print(
            "Argument error: --device-id is required when using --record.",
            file=sys.stderr,
        )
        return 2

    try:
        analyzer = SonicAnalyzer(
            duration=args.duration,
            enable_caching=not args.no_cache,
        )

        results = analyzer.analyze(
            device_id=args.device_id,
            record=args.record,
            filepath=str(args.filepath) if args.filepath else None,
        )

        if not args.json_only:
            analyzer.print_report()

        if args.json or args.json_only:
            print(json.dumps(results, indent=2, ensure_ascii=False))

        return 0

    except KeyboardInterrupt:
        print("Interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"Sonic AI analysis failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

"""
Advanced key detector wrapper.

This keeps the historical entry point while delegating to the unified analyzer.
"""

from __future__ import annotations

import argparse
import json

from unified_analyzer import SonicAnalyzer


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run advanced key analysis with Sonic AI.")
    parser.add_argument("filepath", nargs="?", help="Optional WAV file to analyze")
    parser.add_argument("--record", action="store_true", help="Record from an input device instead of loading a file")
    parser.add_argument("--device-id", type=int, default=5, help="Input device id for recording mode")
    parser.add_argument("--duration", type=float, default=5.0, help="Recording duration in seconds")
    parser.add_argument("--json", action="store_true", help="Print full JSON output")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.record and not args.filepath:
        raise SystemExit("Provide a filepath or pass --record.")

    analyzer = SonicAnalyzer(duration=args.duration, enable_caching=True)
    results = analyzer.analyze(device_id=args.device_id, record=args.record, filepath=args.filepath)

    print(f"Detected Key: {results.get('key', 'Unknown')}")
    print(f"Confidence: {results.get('key_confidence', 0):.1%}")
    print(f"Harmonic Complexity: {results.get('harmonic_complexity', 0):.3f}")
    print(f"Melodic Contour: {results.get('melodic_contour', 'unknown')}")

    if args.json:
        print(json.dumps(results, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

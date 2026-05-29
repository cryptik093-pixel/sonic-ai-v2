"""Developer CLI: controlled flagship demo runner for Sonic AI V2.

Produces a reproducible bundle of MIDI files and a manifest using the
deterministic prompt->MIDI engine. Intended as a local "launch" demo to
exercise and validate the flagship MIDI generation capabilities.
"""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
from typing import List, Optional

from app.api.audio.prompt_to_midi import parse_prompt, interpret_prompt, generate_prompt_midi


def run_flagship(prompts: List[str], seeds: Optional[List[Optional[int]]], output_dir: Optional[Path]):
    if seeds is None:
        seeds = [None] * len(prompts)
    if len(seeds) < len(prompts):
        seeds = seeds + [None] * (len(prompts) - len(seeds))

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_base = Path(output_dir) if output_dir else Path("outputs/flagship_demo")
    out_dir = out_base / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    items = []
    for idx, prompt in enumerate(prompts):
        seed = seeds[idx]
        parsed = parse_prompt(prompt)
        result = generate_prompt_midi(prompt, seed=seed)

        safe = parsed.raw_prompt.replace("/", "_").replace('"', "_").replace(" ", "_")
        safe = safe[:120]
        filename = f"sonic_ai_flagship_{idx}_{safe}_{'det' if seed is None else seed}.mid"
        path = out_dir / filename
        path.write_bytes(result.midi_bytes)

        items.append(
            {
                "filename": filename,
                "path": str(path),
                "bytes_length": len(result.midi_bytes),
                "prompt": parsed.raw_prompt,
                "seed": seed,
                "tempo_bpm": parsed.tempo_bpm,
                "key": parsed.key,
                "mode": parsed.mode,
                "pattern_type": parsed.pattern_type,
                "tracks": [t.name for t in result.tracks],
            }
        )

    manifest = {"created_at": ts, "items": items}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"Flagship demo produced {len(items)} files in: {out_dir}")
    print(json.dumps(manifest, indent=2))
    return out_dir


def _parse_seeds(seeds_raw: Optional[str], count: int) -> List[Optional[int]]:
    if not seeds_raw:
        return [None] * count
    parts = [p.strip() for p in seeds_raw.split(",")]
    parsed: List[Optional[int]] = []
    for p in parts:
        if p == "":
            parsed.append(None)
        else:
            try:
                parsed.append(int(p))
            except ValueError:
                parsed.append(None)
    if len(parsed) < count:
        parsed += [None] * (count - len(parsed))
    return parsed[:count]


def main():
    parser = argparse.ArgumentParser(description="Run flagship MIDI demo")
    parser.add_argument("--prompts", "-p", nargs="*", help="One or more prompts to generate.")
    parser.add_argument("--seeds", "-s", help="Comma-separated seeds (use empty for deterministic).")
    parser.add_argument("--output", "-o", help="Output directory (optional).")

    args = parser.parse_args()
    prompts = args.prompts or [
        "dark trap melody at 140 bpm in D minor",
        "emotional chord progression at 92 bpm in F# minor",
    ]
    seeds = _parse_seeds(args.seeds, len(prompts))
    out_dir = Path(args.output) if args.output else None
    run_flagship(prompts, seeds, out_dir)


if __name__ == "__main__":
    main()

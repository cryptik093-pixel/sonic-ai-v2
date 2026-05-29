# Sonic AI V2 — Flagship MIDI Generation Demo

This document describes the controlled, reproducible flagship demo runner used to
exercise the Sonic AI V2 deterministic prompt->MIDI engine. The demo produces
production-ready MIDI files (.mid) and a manifest containing metadata for each
generated file.

Key ideas:

- Configurable: tempo, key, mode, pattern type, density, complexity, and seed.
- Reproducible bundle: all outputs are saved under `outputs/flagship_demo/<timestamp>/`.

Files added in this change:

- `backend/app/api/routes_flagship.py` — API endpoint to produce demo bundles.
- `backend/tools/flagship_demo.py` — CLI to run the demo locally.
- `tests/test_flagship_demo.py` — smoke test validating MIDI bytes are produced.

How it works (parameters you can control):

- prompt: natural language prompt describing musical intent. Example: "dark trap melody at 140 bpm in D minor".
- seed: integer or None. Integer seeds yield repeatable random choices; None uses deterministic movement rules.
- ticks_per_beat: MIDI resolution (default 480). Higher values increase temporal resolution for DAW import.
- pattern_type: inferred from prompt (melody | bassline | chords | drums | arrangement).
- density: sparse | medium | dense — influences notes-per-bar and arrangement fullness.
- complexity: simple | moderate | complex — influences bar length and note material.

Export notes for production use:

- Channels: the engine uses separate channels per role (melody=0, bass=1, chords=2, drums=9).
- Program numbers: MIDI files are format-1 with no program-change events; when importing into a DAW, map channels to desired instruments (e.g., melody -> synth lead, chords -> pads, bass -> 808/synth bass, drums -> drum kit on channel 10).
- Ticks per beat: the API/CLI defaults to 480 which is standard for DAW workflows and preserves groove at export.

Examples

1) Run the CLI locally (developer environment):

```bash
python -m backend.tools.flagship_demo --prompts "dark trap melody at 140 bpm in D minor" "emotional chord progression at 92 bpm in F# minor" --seeds 12,3
```

1) HTTP API (after starting the FastAPI server):

```bash
curl -s -X POST "http://localhost:8000/api/v2/flagship/generate" \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["dark trap melody at 140 bpm in D minor"], "seeds": [42]}' | jq .
```

Next steps (recommended):

- Hook the flagship bundle into a release pipeline to create an official demo artifact.
- Add short exemplar DAW session templates and an example mapping file (channel -> instrument) for quick auditioning.
- Add optional MIDI Program Change events or GM mapping to speed auditioning in synth hosts.
- Iterate on generation strategies (hybrid ML + rules) behind small feature flags to A/B test musical quality.

Keep the Sonic AI V2 non-negotiables in mind: deterministic analysis and explainable outputs are required; no fake AI claims.

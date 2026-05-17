# Sonic AI V2 Music AI Integration Plan

Sonic AI V2 should not install every music AI package into the production backend.
The backend targets Python `>=3.12,<3.14`, deterministic analysis, stable API
contracts, and fast local startup. Heavy or incompatible model stacks belong in
separate research environments until they pass a dedicated runtime proof.

## Integrated Now

- `librosa`: already part of the backend for deterministic audio analysis.
- Sonic AI V2 MIDI engine: local deterministic prompt-to-MIDI and audio-to-MIDI
  modules under `backend/app/audio/`.

## Approved Optional Lab Tools

Install only when doing local music-generation experiments:

```powershell
cd "C:\Users\david someone\Desktop\sonic_ai_v2\sonic_ai_v2\backend"
.\.venv\Scripts\python.exe -m pip install -e ".[music-lab]"
```

The `music-lab` extra includes:

- `muspy`: symbolic music generation/dataset workflows.
- `scamp`: local real-time algorithmic composition experiments.
- `pydub`: simple offline audio editing utilities. Many format conversions
  still require `ffmpeg`.

These tools are optional. They are not imported by the FastAPI request path.

## Deferred Or Blocked

- `Magenta`: sandbox-only. The local `magenta-main.zip` can be extracted under
  `external/` for research, but it must not be imported by the FastAPI runtime
  because its current package pins old dependencies that conflict with Sonic AI
  V2's current Python/librosa stack.
- `Essentia`: deferred until Windows/Python 3.12 wheel and runtime behavior are
  proven in this repo.
- `torch`, `torchaudio`, `tensorflow`: deferred to an isolated model-training
  sandbox. They are too heavy for the default API runtime.
- `Riffusion`: deferred; requires a separate model/server/GPU plan.
- `Jukebox`: blocked from the main app because the legacy raw-audio stack is too
  large and risky for Sonic AI V2 production.
- `MuseNet API`: blocked as a production dependency because it is not a local,
  stable Python package in this backend.

The code-owned catalog lives in `backend/app/audio/ai_tool_integrations.py`.

## Local Magenta Zip

The local zip path inspected for this integration is:

```text
C:\Users\david someone\Downloads\magenta-main.zip
```

The Magenta README inside the zip marks the repository as inactive/read-only.
Its `setup.py` pins runtime dependencies including `tensorflow==2.9.1`,
`numpy==1.21.6`, `scipy==1.7.3`, and `librosa==0.7.2`.

Use the sandbox extractor only when you intentionally want to inspect the source:

```powershell
cd "C:\Users\david someone\Desktop\sonic_ai_v2\sonic_ai_v2"
powershell -ExecutionPolicy Bypass -File .\tools\magenta_sandbox\extract_magenta.ps1
```

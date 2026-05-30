# Sonic AI V2

Sonic AI V2 is a clean rebuild of a professional audio analysis SaaS for music producers, engineers, and artists.

The current backend can run deterministic DSP analysis, expose a prompt-to-MIDI API, and provide local CLI tools for MIDI workflows. The frontend is a Vite/React core product loop for uploading audio and reviewing the deterministic engineering report dashboard.

## Repository Layout

```text
sonic_ai_v2/
  backend/   FastAPI backend and deterministic audio analysis modules
  frontend/  Vite React TypeScript upload/analyze/report dashboard
  docs/      Product, API, and build documentation
```

## Windows PowerShell Setup

From the repository root:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
pytest
```

Python 3.13 also works with the current dependency set, but Python 3.12 is the documented backend target.

## Run The Backend API

```powershell
cd backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Create a deterministic test WAV:

```powershell
python -m app.cli make-test-audio --output .\outputs\test_mix.wav
```

Analyze that WAV through the API:

```powershell
curl.exe -X POST `
  -F "file=@.\outputs\test_mix.wav" `
  -F "target_profile=streaming_balanced" `
  http://127.0.0.1:8000/api/v2/analyze
```

Analyze your own audio file by replacing `.\outputs\test_mix.wav` with a `.wav`, `.flac`, `.aiff`, `.mp3`, or `.ogg` path.

Generate deterministic MIDI through the public API:

```powershell
curl.exe -X POST `
  -H "Content-Type: application/json" `
  -H "Accept: application/json" `
  -d "{\"prompt\":\"dark trap melody at 140 bpm in D minor\",\"seed\":12}" `
  http://127.0.0.1:8000/api/v2/prompt-midi
```

Omit `Accept: application/json` to receive the default `audio/midi` response.

## Run The Frontend

Start the backend first, then run the frontend dev server from a second PowerShell window:

```powershell
cd frontend
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`.

## Production Deployment

Use Railway for the FastAPI backend and Vercel for the static frontend. Keep `api.omega-house.online` on Railway, and alias only `omega-house.online` / `www.omega-house.online` to Vercel. See `DEPLOYMENT.md` and `docs/deploy/RAILWAY_VERCEL.md`.

## Local CLI Workflow

The CLI is the fastest way to test Sonic AI V2 without the frontend.

Analyze an audio file and save the JSON report:

```powershell
python -m app.cli analyze `
  --input ".\outputs\test_mix.wav" `
  --profile streaming_balanced `
  --json-out ".\outputs\analysis_report.json"
```

Generate deterministic prompt MIDI:

```powershell
python -m app.cli prompt-midi `
  --prompt "dark trap melody at 140 bpm in D minor" `
  --seed 7 `
  --output ".\outputs\dark_trap_melody.mid" `
  --json-out ".\outputs\dark_trap_melody.json"
```

Extract MIDI from an audio file:

```powershell
python -m app.cli audio-to-midi `
  --input ".\outputs\test_mix.wav" `
  --output ".\outputs\extracted_from_audio.mid" `
  --json-out ".\outputs\extracted_from_audio.json"
```

Run quality checks:

```powershell
pytest
ruff check app tests
```

Frontend quality checks:

```powershell
cd frontend
npm run test
npm run lint
npm run build
```

## Current Phase

Sonic AI V2 is still engine-first. The public API exposes health, deterministic audio analysis, and the documented prompt-to-MIDI route. The current frontend covers the core upload -> analyze -> engineering report workflow; account, billing, history, and export workflows are intentionally out of scope.

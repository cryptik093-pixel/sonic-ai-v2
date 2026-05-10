# Sonic AI V2 Codex Instructions

Sonic AI V2 is a professional audio AI SaaS foundation for music producers, engineers, and artists. Treat this repository as a clean V2 rebuild. Do not reuse Sonic AI V1 assumptions, files, shortcuts, or broken patterns.

## Required Workflow

1. Read `docs/SONIC_AI_V2_SPEC.md` before coding.
2. Make one focused change at a time.
3. Prefer small, stable, testable files over large files.
4. Run the relevant tests for every code change.
5. Summarize changed files and verification results at the end of each task.

## Engineering Rules

- Backend uses Python 3.12, FastAPI, Uvicorn, Pydantic, NumPy, SciPy, SoundFile, Librosa, and pyloudnorm.
- Frontend uses Vite, React, TypeScript, and a Tailwind-ready structure when initialized.
- Build deterministic DSP analysis first.
- Do not make fake AI claims.
- Do not add placeholder business logic that pretends to analyze audio.
- Every API response must be JSON.
- Every major module must be testable.
- Prioritize producer usefulness, engineering truthfulness, deterministic output quality, DAW readiness, workflow speed, and premium stability.

## API Rules

- Preserve the documented API contract in `docs/API_CONTRACT.md`.
- Version public routes under `/api/v2`.
- Return structured error and status payloads instead of plain text.
- Keep request and response models explicit with Pydantic.

## Testing Rules

- Add or update tests with behavior changes.
- Keep tests deterministic.
- Do not rely on network access in tests.
- Audio analysis tests should use generated signals or committed tiny fixtures only.

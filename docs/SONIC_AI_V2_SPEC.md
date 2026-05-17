# Sonic AI V2 Specification

## Product Intent

Sonic AI V2 helps music producers, engineers, and artists understand audio quality, mix translation, loudness, spectral balance, and delivery readiness with truthful deterministic analysis first.

## Non-Negotiables

- Do not make fake AI claims.
- Do not pretend to analyze audio when no audio analysis has occurred.
- Keep outputs explainable and useful to production workflows.
- Every API response must be JSON unless the endpoint is explicitly documented as a binary media endpoint.
- Major modules must be testable in isolation.
- Prefer stable deterministic DSP metrics before subjective recommendations.

## Backend Foundation

The backend uses:

- Python 3.12
- FastAPI
- Uvicorn
- Pydantic
- NumPy
- SciPy
- SoundFile
- Librosa
- pyloudnorm

Initial backend domains:

- API routing
- configuration
- request and response models
- audio loading
- deterministic metrics
- reference profiles
- analyzer orchestration

## Frontend Foundation

The frontend uses Vite, React, TypeScript, and a Tailwind-ready structure. It should stay aligned with the deterministic backend contract and handle backend errors without inventing analysis data.

## Analysis Principles

Real analysis must be deterministic and derived from audio data. Early metrics should prioritize:

- duration
- sample rate
- channel count
- peak level
- true peak where possible
- integrated loudness
- loudness range where possible
- crest factor
- stereo balance
- spectral centroid
- band energy distribution
- clipping risk

## Roadmap

1. Phase 1: repository foundation, API shell, docs, tests.
2. Phase 2: audio loading and deterministic metrics.
3. Phase 3: analysis reports and reference profile comparison.
4. Phase 4: frontend initialization.
5. Phase 5: premium workflow features and DAW-oriented export formats.

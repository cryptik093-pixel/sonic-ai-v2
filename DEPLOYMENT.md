# Sonic AI V2 Deployment

## Stack Summary

Sonic AI V2 is a full-stack repository:

- Backend: FastAPI ASGI app in `backend/app/main.py`
- Backend entrypoint: `app.main:app`
- Frontend: Vite, React, TypeScript in `frontend/`
- Health check: `GET /health`

## Recommended Deployment Target

Deploy the backend to Render and the frontend to Vercel.

This is the most practical path for the current repo because the backend has Python DSP dependencies and file uploads, while the frontend is a static Vite build. Keep them as two deploys and connect them with `VITE_API_BASE_URL` plus backend CORS.

## Required Environment Variables

Backend:

```bash
SONIC_AI_APP_NAME="Sonic AI V2 API"
SONIC_AI_SERVICE_NAME="sonic-ai-v2-backend"
SONIC_AI_VERSION="0.1.0"
SONIC_AI_ENVIRONMENT="production"
SONIC_AI_CORS_ORIGINS="https://your-frontend.example.com,http://localhost:5173,http://127.0.0.1:5173"
SONIC_AI_MAX_UPLOAD_MB="200"
# Optional exact-byte override:
# SONIC_AI_MAX_UPLOAD_BYTES="209715200"
```

Frontend:

```bash
VITE_API_BASE_URL="https://your-backend.example.com"
```

Do not commit real secrets. This repo does not currently require secrets for the deterministic analysis API.

## Local Development

Backend:

```bash
cd backend
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`.

## Production Build

Backend install:

```bash
cd backend
python -m pip install -e .
```

Frontend build:

```bash
cd frontend
npm ci
npm run build
```

## Production Start Command

Run from `backend/`:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

## Health Check URL

```text
https://your-backend.example.com/health
```

Expected response:

```json
{"status":"ok","service":"sonic-ai-v2-backend","version":"0.1.0"}
```

## Deploy Steps

### Backend on Render

Use `deploy/render.yaml` or configure manually:

- Root directory: `backend`
- Build command: `python -m pip install --upgrade pip && pip install -e .`
- Start command: `python -m uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- Set `SONIC_AI_CORS_ORIGINS` to the deployed frontend origin.
- Set `SONIC_AI_MAX_UPLOAD_MB=200`.

### Frontend on Vercel

Use the root `vercel.json`.

Set:

```bash
VITE_API_BASE_URL=https://your-render-backend.example.com
```

Then deploy from the repository root. The configured build command runs `cd frontend && npm ci && npm run build`, and Vercel serves `frontend/dist`.

### Container Backend

Build from the repository root:

```bash
docker build -t sonic-ai-v2-backend .
docker run --rm -p 8000:8000 --env-file .env sonic-ai-v2-backend
```

## Common Failure Fixes

- `ModuleNotFoundError: app`: run the backend start command from `backend/`, or use the provided Dockerfile.
- `CORS error in browser`: add the deployed frontend origin to `SONIC_AI_CORS_ORIGINS`.
- `413 file_too_large`: increase `SONIC_AI_MAX_UPLOAD_MB` deliberately, or upload a smaller supported audio file.
- Frontend calls the wrong backend: set `VITE_API_BASE_URL` before running `npm run build`.
- Render build cannot find requirements: this repo uses `backend/pyproject.toml`; use `pip install -e .`.

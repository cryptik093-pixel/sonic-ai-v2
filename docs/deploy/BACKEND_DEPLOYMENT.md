# Sonic AI V2 Backend Deployment

The backend deploys from `backend/` as a Python package. Keep `/health` and
`/api/v2/analyze` public, and keep deterministic analysis enabled.

## Production Start Command

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

For hosts that do not provide `PORT`, use `8000` or `8080`.

## Required Runtime

- Python `>=3.12,<3.14`
- Install command from repository root:

```bash
pip install -e ./backend
```

From inside `backend/`:

```bash
pip install -e .
```

## Environment

The backend reads `SONIC_AI_*` settings.

```bash
SONIC_AI_ENVIRONMENT=production
SONIC_AI_MAX_UPLOAD_BYTES=209715200
SONIC_AI_UPLOAD_READ_CHUNK_BYTES=1048576
SONIC_AI_CORS_ORIGINS=https://omega-house.online,https://www.omega-house.online
```

`SONIC_AI_MAX_UPLOAD_BYTES` defaults to `209715200` bytes, which is 200 MB.
Set the hosting platform request body limit to the same size or higher.

## Health Check

Use:

```bash
GET /health
```

Expected JSON:

```json
{"status":"ok","service":"sonic-ai-v2-backend","version":"0.1.0"}
```

## Platform Notes

Render can use `deploy/render.yaml`. It installs `backend` with `pip install -e .`,
starts Uvicorn, and checks `/health`.

Fly.io can use `deploy/fly.toml`, which points at `deploy/fly.Dockerfile`.

Railway and generic container hosts can use the same package install and start
command. Make sure the service runs from `backend/` or that `backend` is
installed before startup.

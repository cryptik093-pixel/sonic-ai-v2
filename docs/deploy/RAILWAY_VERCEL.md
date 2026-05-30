# Railway Backend + Vercel Frontend Deployment

This is the supported production deployment path for Sonic AI V2.

## Service Ownership

- Railway owns the FastAPI backend container and `api.omega-house.online`.
- Vercel owns the Vite frontend and `omega-house.online` / `www.omega-house.online`.
- The Python backend should not be run as a Vercel Serverless Function.

## Backend: Railway

Railway reads `railway.json` from the repository root and builds the root `Dockerfile`.

Required Railway variables:

```bash
SONIC_AI_ENVIRONMENT=production
SONIC_AI_APP_NAME=Sonic AI V2 API
SONIC_AI_SERVICE_NAME=sonic-ai-v2-backend
SONIC_AI_VERSION=0.1.0
SONIC_AI_MAX_UPLOAD_BYTES=209715200
SONIC_AI_CORS_ORIGINS=https://omega-house.online,https://www.omega-house.online,http://localhost:5173,http://127.0.0.1:5173
```

Railway health check path:

```text
/health
```

Production API check:

```bash
curl https://api.omega-house.online/health
```

## Frontend: Vercel

Vercel uses the root `vercel.json`:

- install: `npm --prefix frontend ci`
- build: `npm --prefix frontend run build`
- output: `frontend/dist`

Required Vercel variable:

```bash
VITE_API_BASE_URL=https://api.omega-house.online
```

The config includes proxy rewrites for same-origin `/api/*` and `/health` requests to `https://api.omega-house.online`, followed by the SPA fallback to `/index.html`.

## Alias Commands

Alias only frontend hosts to Vercel:

```bash
vercel alias <frontend-deployment-url> omega-house.online
vercel alias <frontend-deployment-url> www.omega-house.online
```

Configure `api.omega-house.online` in Railway custom domains instead of Vercel aliases.

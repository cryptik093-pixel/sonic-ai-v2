# Vercel (frontend) + Render (backend) deployment

Overview
- Frontend: Vercel serves `omega-house.online` (apex) and `www.omega-house.online`.
- Backend: Render hosts the API at `api.omega-house.online` through a CNAME to the Render service.

Frontend (Vercel) steps
1. Import the repository in Vercel (https://vercel.com/new) and select the deployment branch.
2. Project settings:
   - Framework Preset: Other (Vite)
   - Build Command: `cd frontend && npm ci && npm run build`
   - Output Directory: `frontend/dist`
   - Environment Variable: `VITE_API_BASE_URL=https://api.omega-house.online`
3. Add domain `omega-house.online` in Vercel dashboard. Follow Vercel DNS instructions. For an apex domain, Vercel will show an A record: `76.76.21.21` and/or provide an `ALIAS`/`ANAME` target.

Backend (Render) steps
1. Create a new Render Web Service and connect GitHub to the repository.
2. Runtime: Python 3.12
3. Root Directory: `backend`
4. Build Command: `python -m pip install --upgrade pip && pip install -e .`
5. Start Command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:$PORT`
6. Health Check Path: `/health`
7. Set `SONIC_AI_ENVIRONMENT=production`.
8. Set `SONIC_AI_CORS_ORIGINS` to the deployed frontend origin.
9. Set `SONIC_AI_MAX_UPLOAD_BYTES=209715200` for the current 200 MB upload cap.
10. After the service is created, Render will provide a service hostname like `<service>.onrender.com`. Create DNS CNAME: `api` -> `<service>.onrender.com`.

DNS summary
- `A` (apex): `omega-house.online` -> `76.76.21.21` (Vercel apex IP)
- `CNAME` (www): `www` -> `cname.vercel-dns.com`
- `CNAME` (api): `api` -> `<render-service>.onrender.com`

TLS: Vercel and Render provide automatic Let's Encrypt issuance once DNS is configured.

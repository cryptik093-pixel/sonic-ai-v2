# Vercel (frontend) + Render (backend) deployment

> Deprecated: the supported production target is now Railway for the backend and Vercel for the frontend. Use `docs/deploy/RAILWAY_VERCEL.md` unless you intentionally need the legacy Render path.

Overview
- Frontend: Vercel serves `omega-house.online` (apex) and `www.omega-house.online`.
- Backend: Render hosts the API at `api.omega-house.online` (via CNAME to Render service).

Frontend (Vercel) steps
1. Import the repository in Vercel (https://vercel.com/new) and select the `feat/upload-limit-200mb` branch.
2. Project settings:
   - Framework Preset: Other (Vite)
   - Build Command: `npm run build`
   - Output Directory: `dist`
   - Environment Variable: `VITE_API_BASE_URL=https://api.omega-house.online`
3. Add domain `omega-house.online` in Vercel dashboard. Follow Vercel DNS instructions. For an apex domain, Vercel will show an A record: `76.76.21.21` and/or provide an `ALIAS`/`ANAME` target.

Backend (Render) steps
1. Create a new Render Web Service and connect GitHub to the repository.
2. Use branch `feat/upload-limit-200mb`.
3. Runtime: Python 3.12
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn -k uvicorn.workers.UvicornWorker app.main:app -b 0.0.0.0:$PORT`
6. After the service is created, Render will provide a service hostname like `<service>.onrender.com`. Create DNS CNAME: `api` → `<service>.onrender.com`.

DNS summary (add these records at your DNS provider):
- `A` (apex): `omega-house.online` → `76.76.21.21` (Vercel apex IP)
- `CNAME` (www): `www` → `cname.vercel-dns.com`
- `CNAME` (api): `api` → `<render-service>.onrender.com`

TLS: Vercel and Render provide automatic Let's Encrypt issuance once DNS is configured.

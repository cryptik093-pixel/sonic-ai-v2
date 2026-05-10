# Sonic AI V2 Frontend

Phase 10 initializes the Vite, React, and TypeScript frontend for the core product loop:

```text
Upload audio -> Analyze -> Engineering Report Dashboard
```

## Local Development

Run from this `frontend` directory:

```powershell
npm install
npm run dev
```

The Vite dev server proxies `/api` requests to `http://127.0.0.1:8000`, so run the backend separately before uploading audio through the browser UI.

## Quality Checks

```powershell
npm run test
npm run lint
npm run build
```

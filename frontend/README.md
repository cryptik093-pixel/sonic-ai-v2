# Sonic AI V2 Frontend

Next.js App Router frontend for the core product loop:

```text
Upload audio -> Analyze -> Engineering Report -> Mastering Direction -> MIDI Export
```

## Local Development

Run from this `frontend` directory:

```powershell
npm install
npm run dev
```

Set `NEXT_PUBLIC_API_BASE_URL` in `.env.local` to the FastAPI backend origin before using browser workflows.

## Quality Checks

```powershell
npm run test
npm run lint
npm run build
```

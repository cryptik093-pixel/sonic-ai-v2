# Fly.io deployment (single-provider)

Quick steps
1. Install `flyctl`: https://fly.io/docs/hands-on/install-flyctl/
2. Login: `flyctl auth login`
3. Create app and deploy from project root (run from repo root):

```bash
flyctl launch        # follow prompts, choose app name (e.g. sonic-ai-v2)
flyctl deploy        # uses deploy/fly.Dockerfile by default if configured
```

Notes
- The provided `deploy/fly.Dockerfile` builds the backend; you can either deploy a single combined image (serve frontend as static assets using a minimal webserver) or create two fly apps (frontend + backend).
- For domain mapping, Fly provides a default `*.fly.dev` hostname. To use your domain, create DNS records per `flyctl ips list` output or use Fly's documented ALIAS configuration.

DNS records (example)
- `CNAME` for `api` → `<app>.fly.dev`
- For apex, use ALIAS/ANAME to the Fly-managed IPs (see `flyctl ips allocate` and `flyctl ips list`).

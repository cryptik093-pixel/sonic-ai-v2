# VPS deployment (Nginx + systemd + Certbot)

Summary
- Host both frontend and backend on a single VPS (e.g., DigitalOcean droplet).
- Use Nginx to serve static `dist/` for frontend and reverse-proxy to the backend `gunicorn` running on `127.0.0.1:8000`.

DNS records (set at your registrar/DNS provider):
- `A` (apex): `@` → `<SERVER_PUBLIC_IP>`
- `A` (api): `api` → `<SERVER_PUBLIC_IP>`

Steps (brief)
1. Create an Ubuntu 22.04 droplet and note its public IP.
2. SSH into droplet and run `infra/bootstrap_vps.sh` from repo root (adjust paths and domain in the script).
3. Place the repository at `/var/www/sonic-ai-v2` and ensure `/var/www/sonic-ai-v2/backend/.venv` has dependencies installed.
4. Enable the systemd service:

```bash
sudo cp infra/systemd/sonic-ai-api.service /etc/systemd/system/sonic-ai-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now sonic-ai-api.service
```

5. Verify `nginx -t` and restart: `sudo systemctl restart nginx`.
6. Issue TLS certs via certbot (script already calls certbot):

```bash
sudo certbot --nginx -d omega-house.online -d www.omega-house.online -d api.omega-house.online
```

7. Update backend allowed origins and `VITE_API_BASE_URL` if serving frontend from this domain.

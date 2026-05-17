#!/bin/bash
# Bootstrap for VPS (Ubuntu/Debian) - run as root or with sudo
set -euo pipefail

apt update
apt install -y nginx python3-venv python3-pip git curl

# Create app directory and clone (or copy) source into /var/www/sonic-ai-v2
mkdir -p /var/www/sonic-ai-v2
chown $SUDO_USER:$SUDO_USER /var/www/sonic-ai-v2

# Install virtualenv and dependencies (adjust path if needed)
python3 -m venv /var/www/sonic-ai-v2/backend/.venv
/var/www/sonic-ai-v2/backend/.venv/bin/pip install --upgrade pip
if [ -f /var/www/sonic-ai-v2/backend/requirements.txt ]; then
  /var/www/sonic-ai-v2/backend/.venv/bin/pip install -r /var/www/sonic-ai-v2/backend/requirements.txt
fi

# Copy nginx site configs into sites-available and enable
cp infra/nginx/omega-house.online.conf /etc/nginx/sites-available/omega-house.online
cp infra/nginx/api.omega-house.online.conf /etc/nginx/sites-available/api.omega-house.online
ln -sf /etc/nginx/sites-available/omega-house.online /etc/nginx/sites-enabled/omega-house.online
ln -sf /etc/nginx/sites-available/api.omega-house.online /etc/nginx/sites-enabled/api.omega-house.online
nginx -t
systemctl restart nginx

# Install certbot
apt install -y certbot python3-certbot-nginx
certbot --nginx -d omega-house.online -d www.omega-house.online -d api.omega-house.online --non-interactive --agree-tos -m admin@omega-house.online || true

echo "Bootstrap complete. Place repo in /var/www/sonic-ai-v2 and enable systemd service infra/systemd/sonic-ai-api.service"

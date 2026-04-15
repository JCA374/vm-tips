# Deployment Report — VM Tips

Generated: 2026-04-15

---

## Current State

The application is running live at:
```
https://storahultsvm.se
```

Stack:
- **Flask + Gunicorn** as the WSGI server
- **SQLite** as the database (persistent volume mounted at `/opt/vm-tips/database/`)
- **Docker + docker-compose** for containerisation
- **Nginx** as reverse proxy (port 80/443 → port 5000)
- **Let's Encrypt / Certbot** for HTTPS (auto-renewing)
- **Brevo HTTP API** for magic-link emails (NOT SMTP — see note below)
- **Football-data.org API** for match data
- **DigitalOcean Droplet** (ubuntu-s-1vcpu-1gb-ams3, Amsterdam, ~$6/mo)

---

## Server Details

- **Provider**: DigitalOcean
- **IP**: 178.128.254.166
- **OS**: Ubuntu 24.04 LTS
- **Domain**: storahultsvm.se (registered at Strato)
- **App location**: `/opt/vm-tips/`
- **Database**: `/opt/vm-tips/database/vm_tips.db`

---

## Known Issues Fixed During Deployment

| Fix | File | Detail |
|-----|------|--------|
| `init_db()` not called by gunicorn | `app.py` | Moved out of `__main__` block so tables are created on every startup |
| Gunicorn `app:app` fails | `wsgi.py` | The `app/` package shadows `app.py` in Python's import system. Created `wsgi.py` as the gunicorn entry point using `importlib` to load `app.py` by file path |
| Gunicorn bound to `127.0.0.1` | `Dockerfile` | Changed to `0.0.0.0` — nginx sits in front now |
| SMTP port 587 blocked | `app/auth/service.py` | DigitalOcean blocks outbound SMTP. Switched from Flask-Mail to Brevo HTTP API (port 443) |

---

## Email Setup — Important

DigitalOcean blocks outbound SMTP (port 587). The app uses **Brevo's HTTP API** instead.

Required `.env` key:
```
MAIL_API_KEY=xkeysib-...   # from brevo.com > account > SMTP & API > API Keys
```

This is NOT the same as the SMTP password (`xsmtpsib-...`). Get the API key separately from Brevo's dashboard.

---

## Nginx + HTTPS Setup (one-time)

```bash
ssh root@178.128.254.166

apt install -y nginx certbot python3-certbot-nginx

cat > /etc/nginx/sites-available/storahultsvm.se << 'EOF'
server {
    listen 80;
    server_name storahultsvm.se www.storahultsvm.se;

    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF

ln -s /etc/nginx/sites-available/storahultsvm.se /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

certbot --nginx -d storahultsvm.se -d www.storahultsvm.se
```

---

## Step-by-Step: Redeploy After Code Changes

From your local machine:

```bash
# 1. Upload changed files
rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' \
  /home/jonas/Code/sport/vm/ root@178.128.254.166:/opt/vm-tips/

# 2. Rebuild and restart
ssh root@178.128.254.166 "cd /opt/vm-tips && docker compose down && docker compose up -d --build"

# 3. Check logs
ssh root@178.128.254.166 "docker compose -f /opt/vm-tips/docker-compose.yml logs --tail=20"
```

---

## Admin Setup

First user must be made admin manually:
```bash
sqlite3 /opt/vm-tips/database/vm_tips.db \
  "UPDATE users SET is_admin = 1 WHERE email = 'jonca374@gmail.com';"
```

---

## Ongoing Maintenance

### Backup the database

```bash
ssh root@178.128.254.166 "cp /opt/vm-tips/database/vm_tips.db \
  /opt/vm-tips/database/backup_$(date +%Y%m%d).db"
```

### View live logs

```bash
ssh root@178.128.254.166 "docker compose -f /opt/vm-tips/docker-compose.yml logs -f"
```

### Restart without rebuilding

```bash
ssh root@178.128.254.166 "docker compose -f /opt/vm-tips/docker-compose.yml restart"
```

---

## Credentials Checklist

| Item | Status |
|------|--------|
| SECRET_KEY | Set in .env |
| MAIL_API_KEY (Brevo HTTP API) | Set in .env |
| Football API key | Set in .env |
| APP_URL | https://storahultsvm.se |
| DigitalOcean droplet | Running |
| Domain (storahultsvm.se) | Registered at Strato |
| Nginx + HTTPS | Set up after DNS propagates |

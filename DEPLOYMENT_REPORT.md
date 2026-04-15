# Deployment Report — VM Tips

Generated: 2026-04-09

---

## Current State

The application is a Flask web app using:
- **Gunicorn** as the WSGI server (already in Dockerfile)
- **SQLite** as the database (file-based, needs persistent disk)
- **Docker + docker-compose** for containerization (already configured)
- **Flask-Mail via Brevo** for magic-link emails
- **Football-data.org API** for match data

All credentials are already configured in `.env`:
- SECRET_KEY is set
- Brevo SMTP credentials are set
- Football API key is set

---

## Recommended Deployment: Hetzner VPS + Docker + Nginx

### Why Hetzner VPS

SQLite is a file-based database. Platforms like Railway, Render, and Fly.io use
ephemeral filesystems that wipe files on redeploy — the database would be lost.
A VPS with a persistent mounted volume is the correct fit for this app.

**Hetzner CX22** (~€4/month, located in Germany) is the recommended choice:
- Persistent disk
- Full control over the environment
- Simple Docker-based deploy
- EU-hosted (GDPR friendly)

---

## Step-by-Step Deployment

### 1. Get a domain name

Buy a domain (e.g. via Namecheap or Loopia). You will point it at the server IP.

### 2. Create a Hetzner account and spin up a server

- Go to hetzner.com/cloud
- Create a project, add a CX22 server
- Choose Ubuntu 24.04 LTS
- Add your SSH key during setup
- Note the server's public IP

### 3. Point your domain to the server

In your DNS settings, add an A record:
```
@ -> <your server IP>
www -> <your server IP>
```

DNS changes take up to 1 hour to propagate.

### 4. SSH into the server and install Docker

```bash
ssh root@<your-server-ip>
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
apt install -y docker-compose-plugin
```

### 5. Upload the project

Either push to GitHub and clone, or use rsync:
```bash
# From your local machine:
rsync -avz --exclude='.git' --exclude='venv' --exclude='database/' \
  /home/jonas/Code/sport/vm/ root@<server-ip>:/opt/vm-tips/
```

### 6. Create the .env file on the server

```bash
nano /opt/vm-tips/.env
```

Copy your local `.env` contents and change one line:
```
APP_URL=https://yourdomain.com
```

### 7. Start the app with Docker

```bash
cd /opt/vm-tips
mkdir -p database
docker compose up -d
```

The app is now running on port 5000 (localhost only, not public yet).

### 8. Install Nginx and set up HTTPS

```bash
apt install -y nginx certbot python3-certbot-nginx
```

Create an Nginx config:
```bash
nano /etc/nginx/sites-available/vm-tips
```

```nginx
server {
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

```bash
ln -s /etc/nginx/sites-available/vm-tips /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Get a free HTTPS certificate:
```bash
certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Certbot auto-renews the certificate via a systemd timer — no manual renewal needed.

### 9. Create the admin user

```bash
# On the server, open a shell in the running container:
docker exec -it $(docker ps -q) bash

# Or run sqlite3 directly against the mounted database:
sqlite3 /opt/vm-tips/database/vm_tips.db \
  "UPDATE users SET is_admin = 1 WHERE email = 'jonca374@gmail.com';"
```

First register at /register via the web, then run the command above.

### 10. Verify everything works

- Visit https://yourdomain.com — should load the app
- Visit https://yourdomain.com/health — should return `{"status": "ok"}`
- Register with your email and confirm the magic link arrives
- Log in as admin, go to /admin/status, click "Sync Matches Now"
- Set round deadlines at /admin/deadlines

---

## Ongoing Maintenance

### Update the app after code changes

```bash
cd /opt/vm-tips
git pull          # if using git on server
docker compose up -d --build
```

### Backup the database

```bash
cp /opt/vm-tips/database/vm_tips.db \
   /opt/vm-tips/database/vm_tips_$(date +%Y%m%d).db
```

Set up a daily cron job for automatic backups:
```bash
crontab -e
# Add:
0 2 * * * cp /opt/vm-tips/database/vm_tips.db /opt/vm-tips/database/backup_$(date +\%Y\%m\%d).db
```

---

## Bugs Fixed Before Deploy

| Fix | File | Detail |
|-----|------|--------|
| `init_db()` not called by gunicorn | `app.py` | Moved out of `__main__` block so tables are created on every startup |
| Gunicorn bound to `0.0.0.0` | `Dockerfile` | Changed to `127.0.0.1` — Nginx is now the only public entry point |

---

## Required Credentials Checklist

| Item | Status |
|------|--------|
| SECRET_KEY | Set in .env |
| Brevo SMTP credentials | Set in .env |
| Football API key | Set in .env |
| Domain name | Not yet purchased |
| APP_URL updated to production domain | Not yet done |
| Hetzner server | Not yet created |

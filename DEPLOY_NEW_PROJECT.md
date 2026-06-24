# Deploying a New Project to the Existing DigitalOcean Droplet

This file is for a Claude Code instance helping deploy a NEW project alongside an existing one on the same server.

## What Already Exists on the Server

- **Provider**: DigitalOcean droplet at IP `178.128.254.166`
- **OS**: Ubuntu 24.04 LTS
- **SSH access**: `ssh root@178.128.254.166`
- **Existing app**: Flask app at `/opt/vm-tips/`, running via Docker + Gunicorn + Nginx
- **Nginx**: Already installed and configured as reverse proxy, serving `storahultsvm.se` on port 80/443
- **Certbot**: Already installed for Let's Encrypt HTTPS certs
- **Docker + docker-compose**: Already installed

## Stack Assumptions for New Project

The server can host additional projects. Each project should:
1. Run in its own Docker container on a unique internal port (e.g. 5001, 5002...)
2. Have its own Nginx server block for its domain
3. Have its own app directory under `/opt/` (e.g. `/opt/my-new-app/`)

## Questions to Ask the User Before Starting

Ask the user these questions one by one (you need the answers to proceed):

1. **What is the project directory on this machine?** (local path, e.g. `/home/jonas/Code/myapp/`)
2. **What domain name will this project use?** (e.g. `myapp.se` or `sub.existing-domain.se`)
3. **Has the domain's DNS A-record been pointed to `178.128.254.166` yet?** (required for HTTPS)
4. **What internal port should this app run on?** (must not conflict — existing app uses port 5000; suggest 5001 or higher)
5. **Does this project have a `.env` file for the server?** If not, what environment variables does it need? (ask the user to provide values — never rsync local `.env` to server)
6. **What is the gunicorn entry point?** (e.g. `wsgi:app` or `app:app` — check if there is a `wsgi.py` or a top-level `app.py`)
7. **Does this project use a database?** If SQLite, confirm the path so we can set up a persistent Docker volume.

## Deployment Steps (once you have the answers)

### 1. Push code to server
```bash
rsync -avz --exclude='.git' --exclude='venv' --exclude='__pycache__' --exclude='.env' \
  /local/project/path/ root@178.128.254.166:/opt/new-app-name/
```

### 2. Create `.env` on server
```bash
ssh root@178.128.254.166 "cat > /opt/new-app-name/.env" << 'EOF'
# Paste the server-specific env vars here
EOF
```

### 3. Verify/create `docker-compose.yml` in the project
- Expose app on the chosen internal port (e.g. `5001:5000`)
- Mount any persistent volumes (e.g. database)
- Do NOT include `version:` attribute (deprecated, causes warnings)

### 4. Start the new container
```bash
ssh root@178.128.254.166 "cd /opt/new-app-name && docker compose up -d --build"
```

### 5. Add Nginx server block for the new domain
```bash
ssh root@178.128.254.166 "cat > /etc/nginx/sites-available/new-app-name" << 'EOF'
server {
    listen 80;
    server_name new-domain.se;

    location / {
        proxy_pass http://localhost:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
ssh root@178.128.254.166 "ln -sf /etc/nginx/sites-available/new-app-name /etc/nginx/sites-enabled/ && nginx -t && systemctl reload nginx"
```

### 6. Obtain HTTPS cert (only after DNS has propagated)
```bash
ssh root@178.128.254.166 "certbot --nginx -d new-domain.se"
```

### 7. Update APP_URL in `.env` to use https
```bash
ssh root@178.128.254.166 "sed -i 's|APP_URL=http://...|APP_URL=https://new-domain.se|' /opt/new-app-name/.env && cd /opt/new-app-name && docker compose restart"
```

## Key Gotchas to Watch For

- **Email**: DigitalOcean blocks outbound SMTP port 587. If the new app sends email, use an HTTP API (e.g. Brevo/Sendinblue) instead of SMTP/Flask-Mail.
- **Gunicorn entry point**: If the project has both `app.py` and an `app/` package directory, the package shadows the file. Use a `wsgi.py` as the gunicorn entry point in that case.
- **Database**: Never overwrite a production database with rsync. If the DB already has data, sync code only and skip the DB file.
- **Two .env files**: Always maintain separate local and server `.env` files. Never rsync `.env` to the server.
- **Port conflicts**: Check what ports are already in use on the server before choosing one: `ssh root@178.128.254.166 "ss -tlnp | grep LISTEN"`
- **Nginx config test**: Always run `nginx -t` before reloading nginx to catch syntax errors.

## Useful Diagnostic Commands

```bash
# Check running containers
ssh root@178.128.254.166 "docker ps"

# Check which ports are in use
ssh root@178.128.254.166 "ss -tlnp | grep LISTEN"

# View logs for new app
ssh root@178.128.254.166 "docker compose -f /opt/new-app-name/docker-compose.yml logs --tail=30"

# Check nginx status
ssh root@178.128.254.166 "systemctl status nginx"

# List nginx enabled sites
ssh root@178.128.254.166 "ls /etc/nginx/sites-enabled/"
```

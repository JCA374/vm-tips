# Deployment Guide

## Prerequisites

- Python 3.11+
- Docker (optional, but recommended)
- Football API key from https://www.football-data.org (free tier available)
- Email service credentials (Brevo/Sendinblue recommended for EU)

## Local Development

1. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your actual values
```

4. **Run the application**
```bash
python app.py
```

The app will be available at http://localhost:5000

## Production Deployment

### Option 1: Hetzner VPS (Recommended)

1. **Create a Hetzner VPS** (Germany, ~€5/month)
   - Choose Ubuntu 22.04 LTS
   - Smallest instance is sufficient for <20 users

2. **SSH into server**
```bash
ssh root@your-server-ip
```

3. **Install Docker**
```bash
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
```

4. **Clone repository**
```bash
git clone https://github.com/YOUR_USERNAME/vm-tips.git
cd vm-tips
```

5. **Configure environment**
```bash
cp .env.example .env
nano .env  # Fill in your values
```

6. **Run with Docker**
```bash
docker-compose up -d
```

7. **Set up Nginx reverse proxy** (optional, for HTTPS)
```bash
apt install nginx certbot python3-certbot-nginx
# Configure nginx to proxy to port 5000
certbot --nginx -d yourdomain.com
```

### Option 2: Railway

1. **Install Railway CLI**
```bash
npm install -g @railway/cli
```

2. **Login and deploy**
```bash
railway login
railway init
railway up
```

3. **Set environment variables** via Railway dashboard

### Option 3: Direct VPS (without Docker)

1. **Install Python and dependencies**
```bash
apt update
apt install python3 python3-pip python3-venv
```

2. **Clone and setup**
```bash
git clone https://github.com/YOUR_USERNAME/vm-tips.git
cd vm-tips
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure .env file**

4. **Run with systemd**
```bash
# Create service file
nano /etc/systemd/system/vm-tips.service
```

```ini
[Unit]
Description=VM Tips Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/vm-tips
Environment="PATH=/path/to/vm-tips/venv/bin"
ExecStart=/path/to/vm-tips/venv/bin/gunicorn --bind 0.0.0.0:5000 --workers 2 app:app

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable vm-tips
systemctl start vm-tips
```

## Initial Setup

After deployment:

1. **Create admin user**
   - Register via /register with your email
   - Manually set is_admin=1 in database for first user
   ```bash
   sqlite3 database/vm_tips.db
   UPDATE users SET is_admin = 1 WHERE email = 'your-email@example.com';
   ```

2. **Sync match data**
   - Login as admin
   - Go to /admin/status
   - Click "Sync Matches Now"

3. **Set deadlines**
   - Go to /admin/deadlines
   - Set deadlines for each round

## Email Configuration (Brevo)

1. Sign up at https://www.brevo.com (free tier: 300 emails/day)
2. Get SMTP credentials from Settings > SMTP & API
3. Add to .env:
```
MAIL_SERVER=smtp-relay.brevo.com
MAIL_PORT=587
MAIL_USERNAME=your-username
MAIL_PASSWORD=your-password
MAIL_DEFAULT_SENDER=noreply@yourdomain.com
```

## Football API Setup

1. Sign up at https://www.football-data.org
2. Get free API key (10 calls/minute)
3. Add to .env:
```
FOOTBALL_API_KEY=your-api-key
```

## Maintenance

- **Update match results**: Admin > System Status > Calculate Scores
- **Sync matches**: Admin > System Status > Sync Matches
- **Backup database**: Copy `database/vm_tips.db` file
- **Update code**: `git pull && docker-compose restart` (or restart systemd service)

## Troubleshooting

- **Magic links not sending**: Check email credentials in .env
- **No matches showing**: Sync matches via admin panel
- **Scores not calculating**: Run "Calculate Scores" from admin panel
- **Database errors**: Check file permissions on database directory

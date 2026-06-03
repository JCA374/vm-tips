# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

World Cup Family Competition betting application. Users predict exact scores for knockout round matches, earn points for correct predictions, and compete on a leaderboard.

## Architecture

This codebase follows a **modular architecture** with a clean backend/frontend separation:

- **`backend/`** — All Python business logic (app factory, config, models, blueprints)
- **`frontend/`** — All presentation (Jinja2 templates, static assets, translations)
- **`data/`** — Runtime data (SQLite database)

### Key Modules

1. **Authentication** (`backend/auth/`) - Email-based magic link login + password auth
2. **Match Data** (`backend/match_data/`) - API integration to fetch fixtures and results from football-data.org
3. **Prediction** (`backend/prediction/`) - User score predictions and points calculation logic
4. **Admin** (`backend/admin/`) - User management, deadline management, system status (at /backstage)
5. **Frontend** (`frontend/`) - Templates, static files, Swedish/English translations

### Scoring System

Points awarded for each prediction:
- Correct outcome (win/loss/tie)
- Correct home team goals
- Correct away team goals

### Critical Rules

- Users can only update predictions before round deadline
- Other users' predictions only visible after deadline passes
- Matches and results fetched automatically from external API (not manual admin input)
- All modules must have clear interfaces to allow independent updates

## Development Commands

### Local Development

```bash
# Setup
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run
python run.py  # Runs on http://localhost:5000
```

### Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Database

- SQLite database: `data/vm_tips.db`
- Initialize: Run `python run.py` (auto-creates tables)
- Backup: Copy the .db file

### Admin Setup

First user must be made admin manually:
```bash
sqlite3 data/vm_tips.db
UPDATE users SET is_admin = 1 WHERE email = 'your-email@example.com';
```

## Key Files

- `run.py` - Development entry point
- `wsgi.py` - Production WSGI entry point (gunicorn)
- `backend/__init__.py` - Application factory (`create_app()`)
- `backend/config.py` - Configuration from environment variables
- `backend/models.py` - SQLAlchemy models and database schema
- `backend/extensions.py` - Flask extensions (Mail, Limiter)
- `backend/*/routes.py` - Flask blueprints for each module
- `backend/*/service.py` - Business logic for each module
- `frontend/translations.py` - Swedish/English UI translations
- `frontend/templates/` - Jinja2 HTML templates
- `frontend/static/` - CSS, JS, images

## Development Approach

When building or modifying:
1. Keep modules independent with well-defined interfaces
2. Changes to one module should not require changes to others
3. Use REQUIREMENTS.md as the single source of truth for features
4. Test locally before deploying
5. Always backup database before schema changes

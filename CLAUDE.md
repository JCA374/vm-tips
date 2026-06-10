# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

World Cup 2026 Family Competition betting application. Users predict match outcomes (1X2) and compete on a leaderboard.

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

All rounds use **1X2 prediction** (home win / draw / away win). 1 point per correct prediction.

**Semi-finals and Final:** These matches also require predicting the **number of goals scored in regular time** (90 minutes). The 1X2 outcome is based on the regular-time result, not extra time or penalties. A match that is 1-1 after 90 minutes counts as X (draw), regardless of what happens in extra time.

### Rounds

`group_md1`, `group_md2`, `group_md3`, `round_of_32`, `round_of_16`, `quarter_final`, `semi_final`, `third_place`, `final`

### Critical Rules

- Users can only update predictions before round deadline
- Other users' predictions only visible after deadline passes
- Matches and results fetched automatically from football-data.org API (competition ID 2000)
- Semi-finals and final use regular-time (90 min) scores only — not extra time or penalties
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

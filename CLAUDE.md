# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

World Cup Family Competition betting application. Users predict exact scores for knockout round matches, earn points for correct predictions, and compete on a leaderboard.

## Architecture

This codebase follows a **modular architecture** where components are separated into independent modules that can be updated without breaking each other. See REQUIREMENTS.md for full details.

### Key Modules

1. **Authentication** - Email-based magic link login (no passwords)
2. **Match Data** - API integration to fetch fixtures and results from official football data source
3. **Prediction** - User score predictions and points calculation logic
4. **User Interface** - Forms, leaderboard, and views (public and admin at /admin)
5. **Database/Storage** - Persistence layer for users, predictions, matches, and scores
6. **Admin** - User management, deadline management, system status

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
python app.py  # Runs on http://localhost:5000
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

- SQLite database: `database/vm_tips.db`
- Initialize: Run `python app.py` (auto-creates tables)
- Backup: Copy the .db file

### Admin Setup

First user must be made admin manually:
```bash
sqlite3 database/vm_tips.db
UPDATE users SET is_admin = 1 WHERE email = 'your-email@example.com';
```

## Key Files

- `app.py` - Main Flask application entry point
- `database/models.py` - SQLAlchemy models and database schema
- `config/settings.py` - Configuration from environment variables
- `app/*/routes.py` - Flask blueprints for each module
- `app/*/service.py` - Business logic for each module

## Development Approach

When building or modifying:
1. Keep modules independent with well-defined interfaces
2. Changes to one module should not require changes to others
3. Use REQUIREMENTS.md as the single source of truth for features
4. Test locally before deploying
5. Always backup database before schema changes

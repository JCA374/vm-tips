# VM Tips - World Cup Family Competition

A web application for family members to predict World Cup knockout round scores and compete on a leaderboard.

## Features

- **Score Predictions**: Predict exact scores (home/away goals) for knockout matches
- **Points System**:
  - 3 points for correct outcome (win/draw/loss)
  - 2 points for correct home team goals
  - 2 points for correct away team goals
- **Magic Link Authentication**: Passwordless email login
- **Leaderboard**: Track rankings and total points
- **Round Deadlines**: Predictions locked after each round's deadline
- **Admin Panel**: Manage users, deadlines, and sync match data
- **Automatic Match Data**: Fetches fixtures and results from football-data.org

## Tech Stack

- **Backend**: Python with Flask
- **Database**: SQLite (perfect for <20 users)
- **Frontend**: HTML templates with minimal JavaScript
- **Email**: Flask-Mail (configured for Brevo/Sendinblue)
- **Deployment**: Docker, Gunicorn

## Quick Start

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

```bash
# Clone repository
git clone https://github.com/YOUR_USERNAME/vm-tips.git
cd vm-tips

# Setup environment
cp .env.example .env
# Edit .env with your credentials

# Run with Docker
docker-compose up -d

# Or run locally
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Project Structure

```
vm-tips/
├── app/
│   ├── auth/           # Authentication module
│   ├── match_data/     # Match API integration
│   ├── prediction/     # Prediction & scoring logic
│   ├── admin/          # Admin functionality
│   └── ui/             # Templates & static files
├── database/           # SQLite database & models
├── config/             # Application settings
├── app.py             # Main application
├── requirements.txt   # Python dependencies
├── Dockerfile         # Docker configuration
└── DEPLOYMENT.md      # Deployment guide
```

## Architecture

The application follows a **modular architecture** where each component is independent:

- **Authentication**: Magic link email system
- **Match Data**: API integration for fixtures/results
- **Predictions**: User predictions and scoring
- **Admin**: Management interface
- **Database**: SQLite with SQLAlchemy

Each module can be updated independently without breaking others.

## License

MIT License - feel free to use for your family competition!

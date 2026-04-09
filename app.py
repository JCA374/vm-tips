"""Main Flask application entry point"""
from flask import Flask, render_template, redirect, url_for
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import timedelta
import os
import logging
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import settings

# Warn loudly if the secret key is still the insecure default
_DEFAULT_KEY = 'dev-secret-key-change-in-production'
if settings.SECRET_KEY == _DEFAULT_KEY:
    if os.getenv('FLASK_ENV') == 'production':
        raise RuntimeError('SECRET_KEY must be changed in production. Set the SECRET_KEY environment variable.')
    else:
        logging.warning('WARNING: Using default SECRET_KEY. Set SECRET_KEY in your .env file before deploying.')

# Create Flask app
app = Flask(__name__,
            template_folder='app/ui/templates',
            static_folder='app/ui/static')

# Load configuration
app.config.from_object(settings)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=settings.PERMANENT_SESSION_LIFETIME_DAYS)

# Initialize extensions
mail = Mail(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    storage_uri=settings.RATELIMIT_STORAGE_URI,
    default_limits=[settings.RATELIMIT_DEFAULT],
)

# Import and register blueprints
from app.auth.routes import auth_bp
from app.prediction.routes import prediction_bp
from app.admin.routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(prediction_bp)
app.register_blueprint(admin_bp, url_prefix='/backstage')

# Apply rate limits to auth endpoints after blueprint registration
# POST /login  — 3 per email is enforced in service; 10 per IP here
# GET  /auth/verify — 20 per IP per hour (brute-force protection)
limiter.limit('10 per hour')(app.view_functions['auth.login'])
limiter.limit('20 per hour')(app.view_functions['auth.verify'])
limiter.limit('10 per hour')(app.view_functions['auth.invite'])


@app.route('/')
def index():
    """Home page - redirect to leaderboard or login"""
    # TODO: Check if user is logged in
    # For now, show a simple home page
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok'}, 200


if __name__ == '__main__':
    # Initialize database on first run
    from database.models import init_db
    init_db()

    # Run the app
    app.run(host='0.0.0.0', port=5000, debug=True)

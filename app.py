"""Main Flask application entry point"""
from flask import Flask, render_template, redirect, url_for, session, request
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

# Initialize database (safe to call on every startup — creates tables if missing)
from database.models import init_db
init_db()

# Apply rate limits to auth endpoints after blueprint registration
# POST /login  — 3 per email is enforced in service; 10 per IP here
# GET  /auth/verify — 20 per IP per hour (brute-force protection)
limiter.limit('10 per hour')(app.view_functions['auth.login'])
limiter.limit('20 per hour')(app.view_functions['auth.verify'])
limiter.limit('10 per hour')(app.view_functions['auth.invite'])
limiter.limit('20 per hour')(app.view_functions['auth.check_email'])


@app.context_processor
def inject_translations():
    from app.ui.translations import TRANSLATIONS
    lang = session.get('lang', 'sv')
    t = TRANSLATIONS[lang]
    return {'t': t, 'lang': lang}


@app.template_filter('country')
def country_filter(name):
    """Translate a country name to the current UI language."""
    from app.ui.translations import TRANSLATIONS
    lang = session.get('lang', 'sv')
    return TRANSLATIONS[lang]['countries'].get(name, name)


@app.route('/lang/<code>')
def set_language(code):
    if code in ('sv', 'en'):
        session['lang'] = code
        session.modified = True
    return redirect(request.referrer or url_for('index'))


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/health')
def health():
    """Health check endpoint"""
    return {'status': 'ok'}, 200


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

"""Application factory for VM Tips."""
from flask import Flask, render_template, redirect, url_for, session
from datetime import timedelta
import os
import logging
from dotenv import load_dotenv


def create_app(config_override=None):
    load_dotenv()

    from backend import config

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'templates'),
        static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend', 'static'),
    )

    # Warn loudly if the secret key is still the insecure default
    _DEFAULT_KEY = 'dev-secret-key-change-in-production'
    if config.SECRET_KEY == _DEFAULT_KEY:
        if os.getenv('FLASK_ENV') == 'production':
            raise RuntimeError('SECRET_KEY must be changed in production. Set the SECRET_KEY environment variable.')
        else:
            logging.warning('WARNING: Using default SECRET_KEY. Set SECRET_KEY in your .env file before deploying.')

    app.config.from_object(config)
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=config.PERMANENT_SESSION_LIFETIME_DAYS)
    if config_override:
        app.config.update(config_override)

    # Initialize extensions
    from backend.extensions import mail, limiter
    mail.init_app(app)
    app.config['RATELIMIT_STORAGE_URI'] = config.RATELIMIT_STORAGE_URI
    app.config['RATELIMIT_DEFAULT'] = config.RATELIMIT_DEFAULT
    limiter.init_app(app)

    # Register blueprints
    from backend.auth.routes import auth_bp
    from backend.prediction.routes import prediction_bp
    from backend.admin.routes import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(prediction_bp)
    app.register_blueprint(admin_bp, url_prefix='/backstage')

    # Initialize database
    from backend.models import init_db
    init_db()

    # Apply rate limits to auth endpoints after blueprint registration
    limiter.limit('10 per hour')(app.view_functions['auth.login'])
    limiter.limit('20 per hour')(app.view_functions['auth.verify'])
    limiter.limit('10 per hour')(app.view_functions['auth.invite'])

    @app.context_processor
    def inject_translations():
        from frontend.translations import TRANSLATIONS
        lang = session.get('lang', 'sv')
        t = TRANSLATIONS[lang]
        return {'t': t, 'lang': lang}

    @app.template_filter('country')
    def country_filter(name):
        """Translate a country name to the current UI language."""
        from frontend.translations import TRANSLATIONS
        lang = session.get('lang', 'sv')
        return TRANSLATIONS[lang]['countries'].get(name, name)

    @app.route('/lang/<code>')
    def set_language(code):
        if code in ('sv', 'en'):
            session['lang'] = code
            session.modified = True
        # Never redirect to request.referrer — it's attacker-controlled (open redirect risk)
        return redirect(url_for('index'))

    @app.route('/')
    def index():
        if not session.get('user_id'):
            return redirect(url_for('auth.login'))
        return render_template('index.html')

    @app.route('/health')
    def health():
        """Health check endpoint"""
        return {'status': 'ok'}, 200

    return app

"""Application factory for VM Tips."""
from flask import Flask, render_template, redirect, url_for, session, request, g
from datetime import datetime, timedelta
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

    COUNTRY_FLAGS = {
        'Algeria': '\U0001F1E9\U0001F1FF', 'Argentina': '\U0001F1E6\U0001F1F7',
        'Australia': '\U0001F1E6\U0001F1FA', 'Austria': '\U0001F1E6\U0001F1F9',
        'Belgium': '\U0001F1E7\U0001F1EA', 'Bosnia-Herzegovina': '\U0001F1E7\U0001F1E6',
        'Brazil': '\U0001F1E7\U0001F1F7', 'Canada': '\U0001F1E8\U0001F1E6',
        'Cape Verde Islands': '\U0001F1E8\U0001F1FB', 'Colombia': '\U0001F1E8\U0001F1F4',
        'Congo DR': '\U0001F1E8\U0001F1E9', 'Croatia': '\U0001F1ED\U0001F1F7',
        'Curaçao': '\U0001F1E8\U0001F1FC', 'Czechia': '\U0001F1E8\U0001F1FF',
        'Ecuador': '\U0001F1EA\U0001F1E8', 'Egypt': '\U0001F1EA\U0001F1EC',
        'England': '\U0001F3F4\U000E0067\U000E0062\U000E0065\U000E006E\U000E0067\U000E007F',
        'France': '\U0001F1EB\U0001F1F7', 'Germany': '\U0001F1E9\U0001F1EA',
        'Ghana': '\U0001F1EC\U0001F1ED', 'Haiti': '\U0001F1ED\U0001F1F9',
        'Iran': '\U0001F1EE\U0001F1F7', 'Iraq': '\U0001F1EE\U0001F1F6',
        'Ivory Coast': '\U0001F1E8\U0001F1EE', 'Japan': '\U0001F1EF\U0001F1F5',
        'Jordan': '\U0001F1EF\U0001F1F4', 'Mexico': '\U0001F1F2\U0001F1FD',
        'Morocco': '\U0001F1F2\U0001F1E6', 'Netherlands': '\U0001F1F3\U0001F1F1',
        'New Zealand': '\U0001F1F3\U0001F1FF', 'Norway': '\U0001F1F3\U0001F1F4',
        'Panama': '\U0001F1F5\U0001F1E6', 'Paraguay': '\U0001F1F5\U0001F1FE',
        'Portugal': '\U0001F1F5\U0001F1F9', 'Qatar': '\U0001F1F6\U0001F1E6',
        'Saudi Arabia': '\U0001F1F8\U0001F1E6', 'Scotland': '\U0001F3F4\U000E0067\U000E0062\U000E0073\U000E0063\U000E0074\U000E007F',
        'Senegal': '\U0001F1F8\U0001F1F3', 'South Africa': '\U0001F1FF\U0001F1E6',
        'South Korea': '\U0001F1F0\U0001F1F7', 'Spain': '\U0001F1EA\U0001F1F8',
        'Sweden': '\U0001F1F8\U0001F1EA', 'Switzerland': '\U0001F1E8\U0001F1ED',
        'Tunisia': '\U0001F1F9\U0001F1F3', 'Turkey': '\U0001F1F9\U0001F1F7',
        'United States': '\U0001F1FA\U0001F1F8', 'Uruguay': '\U0001F1FA\U0001F1FE',
        'Uzbekistan': '\U0001F1FA\U0001F1FF',
    }

    @app.template_filter('flag')
    def flag_filter(name):
        """Return flag emoji for a country name."""
        return COUNTRY_FLAGS.get(name, '')

    # --- Activity tracking ---
    SKIP_PATHS = {'/static', '/health', '/favicon.ico'}

    @app.before_request
    def track_activity():
        """Update last_active_at and log the request"""
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return
        g.track_user_id = session.get('user_id')

    @app.after_request
    def log_activity(response):
        """Write activity log entry after the response is ready"""
        if any(request.path.startswith(p) for p in SKIP_PATHS):
            return response
        user_id = getattr(g, 'track_user_id', None)
        try:
            from backend.models import ActivityLog, User, SessionLocal
            db = SessionLocal()
            # Log the page view
            entry = ActivityLog(
                user_id=user_id,
                path=request.path,
                method=request.method,
                status_code=response.status_code,
                ip_address=request.remote_addr,
                user_agent=str(request.user_agent)[:500] if request.user_agent else None,
            )
            db.add(entry)
            # Update last_active_at (throttle: only if >60s since last update)
            if user_id:
                user = db.query(User).get(user_id)
                if user:
                    now = datetime.utcnow()
                    if not user.last_active_at or (now - user.last_active_at).total_seconds() > 60:
                        user.last_active_at = now
            db.commit()
            db.close()
        except Exception:
            logging.exception('Failed to log activity')
        return response

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

"""Application configuration settings"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_PATH = os.getenv('DATABASE_PATH', BASE_DIR / 'data' / 'vm_tips.db')
SQLALCHEMY_DATABASE_URI = f'sqlite:///{DATABASE_PATH}'
SQLALCHEMY_TRACK_MODIFICATIONS = False

# Secret key for sessions
SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

# Email configuration
MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp-relay.brevo.com')
MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
MAIL_USE_TLS = True
MAIL_USERNAME = os.getenv('MAIL_USERNAME')
MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
MAIL_API_KEY = os.getenv('MAIL_API_KEY')
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@vm-tips.com')

# Football API
FOOTBALL_API_URL = os.getenv('FOOTBALL_API_URL', 'https://api.football-data.org/v4')
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')

# Admin — must be set via env var in production, no default to avoid leaking identity
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', '')

# Application settings
APP_URL = os.getenv('APP_URL', 'http://localhost:5000')

# Sessions
SESSION_PERMANENT = False  # controlled per-login via "remember me"
PERMANENT_SESSION_LIFETIME_DAYS = int(os.getenv('PERMANENT_SESSION_LIFETIME_DAYS', 180))

# Session cookie security
# SECURE=True sends the cookie over HTTPS only — enable in production, disable for local HTTP dev
SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
SESSION_COOKIE_HTTPONLY = True   # block JavaScript access to the session cookie
SESSION_COOKIE_SAMESITE = 'Lax' # blocks cross-origin form submissions (CSRF mitigation)

# Security
MAX_USERS = int(os.getenv('MAX_USERS', 50))
MAGIC_LINK_EXPIRY_HOURS = int(os.getenv('MAGIC_LINK_EXPIRY_HOURS', 24))
INVITE_LIMIT_PER_USER = 10         # Hidden from UI — do not expose in templates
INVITE_EXPIRY_DAYS = 7
# Use memory:// for local dev; set RATELIMIT_STORAGE_URI=redis://... in production
# to share limits across gunicorn workers and survive restarts.
RATELIMIT_STORAGE_URI = os.getenv('RATELIMIT_STORAGE_URI', 'memory://')
RATELIMIT_DEFAULT = '200 per day'

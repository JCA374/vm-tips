"""Application configuration settings"""
import os
from pathlib import Path

# Base directory
BASE_DIR = Path(__file__).parent.parent

# Database
DATABASE_PATH = os.getenv('DATABASE_PATH', BASE_DIR / 'database' / 'vm_tips.db')
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
MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@vm-tips.com')

# Football API
FOOTBALL_API_URL = os.getenv('FOOTBALL_API_URL', 'https://api.football-data.org/v4')
FOOTBALL_API_KEY = os.getenv('FOOTBALL_API_KEY')

# Admin credentials
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@example.com')
ADMIN_PASSWORD_HASH = os.getenv('ADMIN_PASSWORD_HASH')

# Application settings
MAGIC_LINK_EXPIRY_MINUTES = int(os.getenv('MAGIC_LINK_EXPIRY_MINUTES', 30))
APP_URL = os.getenv('APP_URL', 'http://localhost:5000')

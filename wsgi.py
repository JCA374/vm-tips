"""WSGI entry point for gunicorn."""
from backend import create_app

app = create_app()

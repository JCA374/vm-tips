"""WSGI entry point for gunicorn.

app.py cannot be imported directly as 'app' because the app/ package
directory takes precedence over app.py in Python's import system.
This file loads app.py by file path to work around that conflict.
"""
import importlib.util
import pathlib

_spec = importlib.util.spec_from_file_location(
    "_flask_app",
    pathlib.Path(__file__).parent / "app.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
app = _mod.app

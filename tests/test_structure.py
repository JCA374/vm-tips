"""Tests for project structure, backend/frontend separation, and app factory."""
import os
import sys
import importlib

# Project root
ROOT = os.path.dirname(os.path.dirname(__file__))


# ── Directory structure ──────────────────────────────────────────────────────

class TestDirectoryStructure:
    """Verify the backend/frontend directory layout exists and old paths are gone."""

    def test_backend_package_exists(self):
        assert os.path.isdir(os.path.join(ROOT, 'backend'))
        assert os.path.isfile(os.path.join(ROOT, 'backend', '__init__.py'))

    def test_frontend_package_exists(self):
        assert os.path.isdir(os.path.join(ROOT, 'frontend'))
        assert os.path.isfile(os.path.join(ROOT, 'frontend', '__init__.py'))

    def test_data_directory_exists(self):
        assert os.path.isdir(os.path.join(ROOT, 'data'))

    def test_run_py_exists(self):
        assert os.path.isfile(os.path.join(ROOT, 'run.py'))

    def test_wsgi_py_exists(self):
        assert os.path.isfile(os.path.join(ROOT, 'wsgi.py'))

    def test_old_app_py_removed(self):
        assert not os.path.isfile(os.path.join(ROOT, 'app.py'))

    def test_old_app_package_removed(self):
        assert not os.path.isdir(os.path.join(ROOT, 'app', 'auth'))

    def test_old_config_package_removed(self):
        assert not os.path.isfile(os.path.join(ROOT, 'config', 'settings.py'))

    def test_old_database_models_removed(self):
        assert not os.path.isfile(os.path.join(ROOT, 'database', 'models.py'))


# ── Backend modules ──────────────────────────────────────────────────────────

class TestBackendModules:
    """Verify all backend modules are importable and have expected contents."""

    def test_import_backend_config(self):
        from backend import config
        assert hasattr(config, 'SECRET_KEY')
        assert hasattr(config, 'SQLALCHEMY_DATABASE_URI')
        assert hasattr(config, 'FOOTBALL_API_KEY')

    def test_import_backend_models(self):
        from backend.models import User, Match, Prediction, RoundDeadline, Invite, MagicLink
        from backend.models import SCORE_ROUNDS, SessionLocal, init_db

    def test_import_backend_extensions(self):
        from backend.extensions import mail, limiter
        assert mail is not None
        assert limiter is not None

    def test_import_auth_routes(self):
        from backend.auth.routes import auth_bp
        assert auth_bp.name == 'auth'

    def test_import_auth_service(self):
        from backend.auth.service import (
            send_magic_link, verify_magic_link, peek_magic_link,
            login_with_password, set_password, user_has_password,
            send_invite, accept_invite, mark_invite_used, change_name,
        )

    def test_import_prediction_routes(self):
        from backend.prediction.routes import prediction_bp
        assert prediction_bp.name == 'prediction'

    def test_import_prediction_service(self):
        from backend.prediction.service import (
            submit_prediction, get_user_predictions, get_leaderboard,
            calculate_all_scores, check_deadline_passed,
        )

    def test_import_match_data_service(self):
        from backend.match_data.service import (
            FootballAPIClient, sync_matches, update_match_results,
            get_upcoming_matches, get_finished_matches, map_stage_to_round,
        )

    def test_import_admin_routes(self):
        from backend.admin.routes import admin_bp
        assert admin_bp.name == 'admin'


# ── Frontend modules ─────────────────────────────────────────────────────────

class TestFrontendModules:
    """Verify frontend assets are in place."""

    def test_import_translations(self):
        from frontend.translations import TRANSLATIONS
        assert 'sv' in TRANSLATIONS
        assert 'en' in TRANSLATIONS
        assert 'app_name' in TRANSLATIONS['sv']
        assert 'countries' in TRANSLATIONS['sv']

    def test_templates_directory_exists(self):
        templates = os.path.join(ROOT, 'frontend', 'templates')
        assert os.path.isdir(templates)

    def test_base_template_exists(self):
        assert os.path.isfile(os.path.join(ROOT, 'frontend', 'templates', 'base.html'))

    def test_auth_templates_exist(self):
        auth_dir = os.path.join(ROOT, 'frontend', 'templates', 'auth')
        assert os.path.isfile(os.path.join(auth_dir, 'login.html'))
        assert os.path.isfile(os.path.join(auth_dir, 'verify.html'))
        assert os.path.isfile(os.path.join(auth_dir, 'set_password.html'))
        assert os.path.isfile(os.path.join(auth_dir, 'join.html'))

    def test_prediction_templates_exist(self):
        pred_dir = os.path.join(ROOT, 'frontend', 'templates', 'prediction')
        assert os.path.isfile(os.path.join(pred_dir, 'predict.html'))
        assert os.path.isfile(os.path.join(pred_dir, 'leaderboard.html'))
        assert os.path.isfile(os.path.join(pred_dir, 'results.html'))

    def test_admin_templates_exist(self):
        admin_dir = os.path.join(ROOT, 'frontend', 'templates', 'admin')
        assert os.path.isfile(os.path.join(admin_dir, 'dashboard.html'))
        assert os.path.isfile(os.path.join(admin_dir, 'users.html'))
        assert os.path.isfile(os.path.join(admin_dir, 'deadlines.html'))
        assert os.path.isfile(os.path.join(admin_dir, 'status.html'))
        assert os.path.isfile(os.path.join(admin_dir, 'backup.html'))

    def test_static_directory_exists(self):
        static = os.path.join(ROOT, 'frontend', 'static')
        assert os.path.isdir(static)
        assert os.path.isdir(os.path.join(static, 'css'))
        assert os.path.isdir(os.path.join(static, 'js'))


# ── Application factory ─────────────────────────────────────────────────────

class TestAppFactory:
    """Verify the Flask application factory works correctly."""

    def test_create_app_returns_flask_instance(self):
        from backend import create_app
        app = create_app()
        from flask import Flask
        assert isinstance(app, Flask)

    def test_create_app_registers_blueprints(self):
        from backend import create_app
        app = create_app()
        blueprint_names = list(app.blueprints.keys())
        assert 'auth' in blueprint_names
        assert 'prediction' in blueprint_names
        assert 'admin' in blueprint_names

    def test_create_app_has_core_routes(self):
        from backend import create_app
        app = create_app()
        rules = [r.rule for r in app.url_map.iter_rules()]
        assert '/' in rules
        assert '/health' in rules
        assert '/login' in rules
        assert '/leaderboard' in rules
        assert '/predict' in rules

    def test_create_app_template_folder_points_to_frontend(self):
        from backend import create_app
        app = create_app()
        assert 'frontend' in app.template_folder
        assert app.template_folder.endswith(os.path.join('frontend', 'templates'))

    def test_create_app_static_folder_points_to_frontend(self):
        from backend import create_app
        app = create_app()
        assert 'frontend' in app.static_folder
        assert app.static_folder.endswith(os.path.join('frontend', 'static'))

    def test_health_endpoint(self):
        from backend import create_app
        app = create_app()
        with app.test_client() as client:
            resp = client.get('/health')
            assert resp.status_code == 200
            assert resp.get_json() == {'status': 'ok'}

    def test_index_redirects_to_login_when_not_authenticated(self):
        from backend import create_app
        app = create_app()
        with app.test_client() as client:
            resp = client.get('/', follow_redirects=False)
            assert resp.status_code == 302
            assert '/login' in resp.headers['Location']

    def test_translations_injected_into_templates(self):
        from backend import create_app
        app = create_app()
        with app.test_client() as client:
            resp = client.get('/login')
            assert resp.status_code == 200
            # Default language is Swedish
            html = resp.data.decode()
            assert 'Stora Hults VM Tips' in html

    def test_language_toggle(self):
        from backend import create_app
        app = create_app()
        with app.test_client() as client:
            # Switch to English
            resp = client.get('/lang/en', follow_redirects=False)
            assert resp.status_code == 302
            # Verify cookie/session persists (follow the redirect)
            resp = client.get('/login')
            html = resp.data.decode()
            # English translation should be present
            assert 'Log in' in html or 'Login' in html


# ── Config ───────────────────────────────────────────────────────────────────

class TestConfig:
    """Verify config defaults point to the new data/ directory."""

    def test_default_database_path_uses_data_dir(self):
        """Check the source code default, not the runtime value (overridden by conftest)."""
        config_path = os.path.join(ROOT, 'backend', 'config.py')
        with open(config_path) as f:
            source = f.read()
        assert "'data'" in source or '"data"' in source
        assert "'database'" not in source

    def test_wsgi_module_creates_app(self):
        """wsgi.py should export an 'app' attribute without importlib hacks."""
        wsgi_path = os.path.join(ROOT, 'wsgi.py')
        with open(wsgi_path) as f:
            content = f.read()
        assert 'importlib' not in content
        assert 'create_app' in content


# ── No old imports leak ──────────────────────────────────────────────────────

class TestNoOldImports:
    """Ensure no Python files still reference the old import paths."""

    def _scan_py_files(self, directory):
        """Yield (filepath, content) for all .py files under directory (excluding this file)."""
        for dirpath, _, filenames in os.walk(directory):
            if '__pycache__' in dirpath or '.git' in dirpath:
                continue
            for f in filenames:
                if f.endswith('.py') and f != 'test_structure.py':
                    path = os.path.join(dirpath, f)
                    with open(path) as fh:
                        yield path, fh.read()

    def test_no_old_config_imports(self):
        for path, content in self._scan_py_files(os.path.join(ROOT, 'backend')):
            assert 'from config import settings' not in content, f'Old import in {path}'
            assert 'from config.settings' not in content, f'Old import in {path}'

    def test_no_old_database_imports(self):
        for path, content in self._scan_py_files(os.path.join(ROOT, 'backend')):
            assert 'from database.models' not in content, f'Old import in {path}'
            assert 'from database import' not in content, f'Old import in {path}'

    def test_no_old_app_imports(self):
        dirs_to_check = [
            os.path.join(ROOT, 'backend'),
            os.path.join(ROOT, 'tests'),
            os.path.join(ROOT, 'scripts'),
        ]
        for d in dirs_to_check:
            for path, content in self._scan_py_files(d):
                assert 'from app.auth' not in content, f'Old import in {path}'
                assert 'from app.prediction' not in content, f'Old import in {path}'
                assert 'from app.match_data' not in content, f'Old import in {path}'
                assert 'from app.admin' not in content, f'Old import in {path}'
                assert 'from app.ui' not in content, f'Old import in {path}'

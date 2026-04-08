"""Main Flask application entry point"""
from flask import Flask, render_template, redirect, url_for
from flask_mail import Mail
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import configuration
from config import settings

# Create Flask app
app = Flask(__name__,
            template_folder='app/ui/templates',
            static_folder='app/ui/static')

# Load configuration
app.config.from_object(settings)

# Initialize extensions
mail = Mail(app)

# Import and register blueprints
from app.auth.routes import auth_bp
from app.prediction.routes import prediction_bp
from app.admin.routes import admin_bp

app.register_blueprint(auth_bp)
app.register_blueprint(prediction_bp)
app.register_blueprint(admin_bp, url_prefix='/admin')


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

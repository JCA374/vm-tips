"""Authentication routes - Login, logout, magic links"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.auth.service import send_magic_link, verify_magic_link

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Login page - send magic link"""
    if request.method == 'POST':
        email = request.form.get('email')
        if email:
            send_magic_link(email)
            flash('Magic link sent! Check your email.')
            return redirect(url_for('auth.login'))

    return render_template('auth/login.html')


@auth_bp.route('/auth/verify')
def verify():
    """Verify magic link token"""
    token = request.args.get('token')
    user = verify_magic_link(token)

    if user:
        session['user_id'] = user.id
        session['user_email'] = user.email
        session['is_admin'] = user.is_admin
        flash('Login successful!')
        return redirect(url_for('index'))
    else:
        flash('Invalid or expired link.')
        return redirect(url_for('auth.login'))


@auth_bp.route('/logout')
def logout():
    """Logout user"""
    session.clear()
    flash('Logged out successfully.')
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Register new user"""
    if request.method == 'POST':
        email = request.form.get('email')
        name = request.form.get('name')

        from app.auth.service import create_user
        result = create_user(email, name)

        if result['status'] == 'success':
            # Send magic link for login
            send_magic_link(email)
            flash('Registration successful! Check your email for login link.')
        else:
            flash(f"Error: {result['message']}", 'error')

        return redirect(url_for('auth.login'))

    return render_template('auth/register.html')

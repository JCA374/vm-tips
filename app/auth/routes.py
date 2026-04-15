"""Authentication routes - Login, logout, magic links"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from app.auth.service import (
    send_magic_link, verify_magic_link,
    send_invite, accept_invite, mark_invite_used,
    user_has_password, login_with_password, set_password,
)

auth_bp = Blueprint('auth', __name__)


def _start_session(user, remember=False):
    """Set session variables after a successful login"""
    from config import settings
    session.permanent = remember
    session['user_id']    = user['id']
    session['user_email'] = user['email']
    session['user_name']  = user['name']
    session['is_admin']   = user['email'] == settings.ADMIN_EMAIL


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        remember = request.form.get('remember') == 'on'
        mode     = request.form.get('mode', 'link')   # 'password' or 'link'

        if not email:
            flash('Please enter your email.', 'error')
            return redirect(url_for('auth.login'))

        # --- Password login ---
        if mode == 'password':
            if not password:
                flash('Please enter your password.', 'error')
                return render_template('auth/login.html', email=email, active_tab='password', remember=remember)
            user = login_with_password(email, password)
            if user:
                _start_session(user, remember)
                return redirect(url_for('index'))
            flash('Wrong email or password.', 'error')
            return render_template('auth/login.html', email=email, active_tab='password', remember=remember)

        # --- Magic link (login link tab or register tab) ---
        name = request.form.get('name', '').strip() or None
        result = send_magic_link(email, name=name)

        if result['status'] == 'error':
            msg = result.get('message', '')
            if msg == 'new_user':
                # Unknown email on login tab — redirect to register tab with email pre-filled
                return render_template('auth/login.html', email=email, active_tab='register', remember=remember)
            if msg == 'max_users':
                flash('This competition is full. Contact Jonas to be added.', 'error')
                return redirect(url_for('auth.login'))
            flash(result.get('message', 'Something went wrong.'), 'error')
            return redirect(url_for('auth.login'))

        resp = make_response(render_template('auth/login.html', sent_to=email))
        resp.set_cookie('vm_remember', '1' if remember else '0', max_age=600, httponly=True)
        return resp

    return render_template('auth/login.html')


@auth_bp.route('/auth/verify')
def verify():
    """Verify magic link token"""
    token = request.args.get('token')
    user = verify_magic_link(token)

    if user:
        remember = request.cookies.get('vm_remember') == '1'
        _start_session(user, remember)
        resp = make_response(redirect(url_for('index')))
        resp.delete_cookie('vm_remember')

        # If user hasn't set a password yet, send them to set one
        if not user_has_password(user['email']):
            resp = make_response(redirect(url_for('auth.set_password_page')))
            resp.delete_cookie('vm_remember')

        flash(f"Welcome, {user['name'].split()[0]}!")
        return resp
    else:
        flash('This link is invalid, expired, or has already been used. Request a new one below.', 'error')
        return redirect(url_for('auth.login'))


@auth_bp.route('/auth/set-password', methods=['GET', 'POST'])
def set_password_page():
    """Let the user set or update their password after logging in via magic link"""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm', '')

        if len(password) < 8:
            flash('Password must be at least 8 characters.', 'error')
            return render_template('auth/set_password.html')

        if password != confirm:
            flash('Passwords do not match.', 'error')
            return render_template('auth/set_password.html')

        ok = set_password(session['user_id'], password)
        if ok:
            flash('Password saved! You can now log in with your email and password.')
            return redirect(url_for('index'))
        flash('Something went wrong. Please try again.', 'error')

    return render_template('auth/set_password.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/register')
def register():
    return redirect(url_for('auth.login'))


@auth_bp.route('/invite', methods=['POST'])
def invite():
    """Send an invite email. Requires login."""
    if not session.get('user_id'):
        return redirect(url_for('auth.login'))

    email = request.form.get('email', '').strip()
    if not email or '@' not in email:
        flash('Please enter a valid email address.', 'error')
        return redirect(url_for('index'))

    result = send_invite(session['user_id'], email)

    if result['status'] == 'success':
        flash(f'Invite sent to {email}!')
    else:
        flash(result['message'], 'error')

    return redirect(url_for('index'))


@auth_bp.route('/join', methods=['GET', 'POST'])
def join():
    """Invite landing page — recipient enters their name and gets a magic link."""
    token = request.args.get('invite') or request.form.get('invite_token')

    invite_data = accept_invite(token)
    if not invite_data:
        flash('This invite link is invalid or has expired.', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        if not name:
            flash('Please enter your name.', 'error')
            return render_template('auth/join.html', invite=invite_data, token=token)

        result = send_magic_link(invite_data['email'], name=name)

        if result['status'] == 'error' and result.get('message') == 'max_users':
            flash('The competition is full right now. Contact Jonas to be added.', 'error')
            return redirect(url_for('auth.login'))

        if result['status'] == 'error':
            flash('Something went wrong. Please try again.', 'error')
            return render_template('auth/join.html', invite=invite_data, token=token)

        mark_invite_used(token)
        return render_template('auth/join.html', invite=invite_data, sent=True)

    return render_template('auth/join.html', invite=invite_data, token=token)

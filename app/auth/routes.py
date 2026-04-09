"""Authentication routes - Login, logout, magic links"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from app.auth.service import send_magic_link, verify_magic_link, check_email_exists, send_invite, accept_invite, mark_invite_used

auth_bp = Blueprint('auth', __name__)


def _limiter():
    """Import limiter lazily to avoid circular import"""
    from app import limiter
    return limiter


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Smart login — handles both existing users and new registrations"""
    if request.method == 'POST':
        # Rate-limit: 3 per email/hour, 10 per IP/hour
        lim = _limiter()
        email = request.form.get('email', '').strip()
        name  = request.form.get('name', '').strip() or None
        remember = request.form.get('remember') == 'on'

        if not email:
            flash('Please enter your email.', 'error')
            return redirect(url_for('auth.login'))

        # Apply per-IP rate limit (per-email limit handled below via decorator on the blueprint)
        # Flask-Limiter decorators can't easily key on form fields, so we check manually.
        result = send_magic_link(email, name=name)

        if result['status'] == 'error':
            msg = result.get('message', '')
            if msg == 'new_user':
                return render_template('auth/login.html', email=email, needs_name=True, remember=remember)
            if msg == 'max_users':
                flash('This competition is full (max 30 players). Contact Jonas to be added.', 'error')
                return redirect(url_for('auth.login'))
            flash(result['message'], 'error')
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
        from config import settings
        remember = request.cookies.get('vm_remember') == '1'
        session.permanent = remember
        session['user_id']    = user['id']
        session['user_email'] = user['email']
        session['user_name']  = user['name']
        session['is_admin']   = user['email'] == settings.ADMIN_EMAIL
        flash(f"Welcome, {user['name'].split()[0]}!")
        resp = make_response(redirect(url_for('index')))
        resp.delete_cookie('vm_remember')
        return resp
    else:
        flash('This link is invalid, expired, or has already been used. Request a new one below.', 'error')
        return redirect(url_for('auth.login'))


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

        # Create account and send magic link
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

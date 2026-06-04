"""Authentication service - Magic link generation and verification"""
import secrets
import requests as http_requests
from datetime import datetime, timedelta
from flask import current_app
from werkzeug.security import generate_password_hash, check_password_hash
from backend.models import User, MagicLink, SessionLocal
from backend import config


def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def check_email_exists(email):
    """Return user's name if email is registered, else None"""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email.lower().strip()).first()
        return user.name if user else None
    finally:
        db.close()


def user_has_password(email):
    """Return True if the user exists and has a password set"""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email.lower().strip()).first()
        return bool(user and user.password_hash)
    finally:
        db.close()


def change_name(user_id, new_name):
    """Update the display name for a user. Returns True on success."""
    db = SessionLocal()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return False
        user.name = new_name.strip()
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def set_password(user_id, password):
    """Hash and save a password for the user. Returns True on success."""
    db = SessionLocal()
    try:
        user = db.query(User).get(user_id)
        if not user:
            return False
        user.password_hash = generate_password_hash(password)
        db.commit()
        return True
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def login_with_password(email, password):
    """
    Verify email + password.
    Returns user dict on success, None on failure.
    """
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(email=email.lower().strip()).first()
        if not user or not user.password_hash:
            return None
        if not check_password_hash(user.password_hash, password):
            return None
        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_admin': user.is_admin,
        }
    finally:
        db.close()


def send_magic_link(email, name=None):
    """
    Send a magic link to the user's email.
    - If the user doesn't exist and name is provided, creates the account.
    - Invalidates any previous unused links for the user before creating a new one.
    Returns {'status': 'success'|'error', 'message': str}
    """
    db = SessionLocal()
    try:
        email = email.lower().strip()
        user = db.query(User).filter_by(email=email).first()

        if not user:
            if not name:
                return {'status': 'error', 'message': 'new_user'}
            # Enforce user cap
            user_count = db.query(User).count()
            if user_count >= config.MAX_USERS:
                return {'status': 'error', 'message': 'max_users'}
            user = User(email=email, name=name.strip())
            db.add(user)
            db.flush()

        # Invalidate all previous unused links for this user
        db.query(MagicLink).filter_by(user_id=user.id, used=False).update({'used': True})

        # Create new link — expires after MAGIC_LINK_EXPIRY_HOURS
        token = generate_token()
        magic_link = MagicLink(
            user_id=user.id,
            token=token,
            expires_at=datetime.utcnow() + timedelta(hours=config.MAGIC_LINK_EXPIRY_HOURS),
        )
        db.add(magic_link)
        db.commit()

        _send_email(email, user.name, token)
        return {'status': 'success'}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def _send_email(email, name, token):
    """Send magic link email via Brevo HTTP API (port 443, not blocked by hosting)"""
    link = f"{config.APP_URL}/auth/verify?token={token}"
    first_name = name.split()[0] if name else 'there'

    _brevo_send(
        to_email=email,
        to_name=name or email,
        subject='Your VM Tips login link',
        html=f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; color: #333;">
  <div style="background: #4CAF50; padding: 24px 32px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">VM Tips</h1>
  </div>
  <div style="background: white; padding: 32px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
    <p style="font-size: 16px;">Hi {first_name}!</p>
    <p style="font-size: 15px; color: #555;">Click the button below to log in to VM Tips:</p>
    <p style="margin: 28px 0; text-align: center;">
      <a href="{link}"
         style="background:#4CAF50; color:white; padding:14px 32px; text-decoration:none;
                border-radius:6px; font-size:16px; font-weight:bold; display:inline-block;">
        Log in to VM Tips
      </a>
    </p>
    <p style="color:#999; font-size:13px; border-top:1px solid #f0f0f0; padding-top:16px; margin-bottom:0;">
      This link expires in {config.MAGIC_LINK_EXPIRY_HOURS} hours.<br>
      If you didn't request this, you can safely ignore this email.
    </p>
  </div>
</body>
</html>
""",
    )


def peek_magic_link(token):
    """
    Check if a token is valid without consuming it.
    Returns user dict if valid, None otherwise.
    Used on GET /auth/verify so email scanners don't burn the token.
    """
    db = SessionLocal()
    try:
        magic_link = (
            db.query(MagicLink)
            .filter_by(token=token, used=False)
            .filter(MagicLink.expires_at > datetime.utcnow())
            .first()
        )
        if not magic_link:
            return None
        user = db.query(User).filter_by(id=magic_link.user_id).first()
        if not user:
            return None
        return {'id': user.id, 'email': user.email, 'name': user.name, 'is_admin': user.is_admin}
    finally:
        db.close()


def verify_magic_link(token):
    """
    Verify and consume a magic link token.
    Returns user dict if valid, None if invalid, expired, or already used.
    Token is marked used on success so it cannot be replayed.
    """
    db = SessionLocal()
    try:
        magic_link = (
            db.query(MagicLink)
            .filter_by(token=token, used=False)
            .filter(MagicLink.expires_at > datetime.utcnow())
            .first()
        )
        if not magic_link:
            return None

        user = db.query(User).filter_by(id=magic_link.user_id).first()
        if not user:
            return None

        # Consume the token — one-time use
        magic_link.used = True
        db.commit()

        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_admin': user.is_admin,
        }

    except Exception as e:
        db.rollback()
        print(f"Error verifying magic link: {e}")
        return None
    finally:
        db.close()


def send_invite(sender_user_id, recipient_email):
    """
    Send an invite to recipient_email on behalf of sender_user_id.
    Silently enforces the per-user invite limit (INVITE_LIMIT_PER_USER).
    Returns {'status': 'success'} or {'status': 'error', 'message': str}.
    The message is intentionally vague — never reveal the limit to callers.
    """
    from backend.models import Invite
    db = SessionLocal()
    try:
        recipient_email = recipient_email.lower().strip()

        sender = db.query(User).filter_by(id=sender_user_id).first()
        if not sender:
            return {'status': 'error', 'message': 'Unable to send invite right now.'}

        # Hidden limit check — count valid (unused + not expired) invites
        used_count = db.query(Invite).filter_by(sender_id=sender_user_id).count()
        if used_count >= config.INVITE_LIMIT_PER_USER:
            return {'status': 'error', 'message': 'Unable to send invite right now.'}

        # If email already registered, send them a regular login link instead
        existing_user = db.query(User).filter_by(email=recipient_email).first()
        if existing_user:
            db.close()
            send_magic_link(recipient_email)
            return {'status': 'success'}

        # Create invite token (expires in INVITE_EXPIRY_DAYS)
        token = generate_token()
        invite = Invite(
            sender_id=sender_user_id,
            recipient_email=recipient_email,
            token=token,
            expires_at=datetime.utcnow() + timedelta(days=config.INVITE_EXPIRY_DAYS),
        )
        db.add(invite)
        db.commit()

        _send_invite_email(recipient_email, sender.name, token)
        return {'status': 'success'}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': 'Unable to send invite right now.'}
    finally:
        db.close()


def accept_invite(token):
    """
    Validate an invite token.
    Returns {'email': str, 'sender_name': str} if valid, None otherwise.
    Does NOT mark as used — call mark_invite_used() after account creation.
    """
    from backend.models import Invite
    db = SessionLocal()
    try:
        invite = db.query(Invite).filter_by(token=token, used=False).first()
        if not invite or not invite.is_valid():
            return None
        return {
            'email': invite.recipient_email,
            'sender_name': invite.sender.name,
        }
    finally:
        db.close()


def mark_invite_used(token):
    from backend.models import Invite
    db = SessionLocal()
    try:
        invite = db.query(Invite).filter_by(token=token).first()
        if invite:
            invite.used = True
            db.commit()
    finally:
        db.close()


def _send_invite_email(recipient_email, sender_name, token):
    """Send invite email via Brevo HTTP API"""
    link = f"{config.APP_URL}/join?invite={token}"
    sender_first = sender_name.split()[0] if sender_name else 'Someone'

    _brevo_send(
        to_email=recipient_email,
        to_name=recipient_email,
        subject=f'{sender_first} invited you to VM Tips!',
        html=f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; color: #333;">
  <div style="background: #4CAF50; padding: 24px 32px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">VM Tips</h1>
  </div>
  <div style="background: white; padding: 32px; border: 1px solid #e0e0e0; border-top: none; border-radius: 0 0 8px 8px;">
    <p style="font-size: 16px;"><strong>{sender_first}</strong> has invited you to join <strong>VM Tips</strong> — a World Cup prediction competition.</p>
    <p style="font-size: 15px; color: #555;">Predict match scores, earn points, and compete on the leaderboard!</p>
    <p style="margin: 28px 0; text-align: center;">
      <a href="{link}"
         style="background:#4CAF50; color:white; padding:14px 32px; text-decoration:none;
                border-radius:6px; font-size:16px; font-weight:bold; display:inline-block;">
        Accept invite
      </a>
    </p>
    <p style="color:#999; font-size:13px; border-top:1px solid #f0f0f0; padding-top:16px; margin-bottom:0;">
      This invite expires in {config.INVITE_EXPIRY_DAYS} days.<br>
      If you weren't expecting this, you can safely ignore it.
    </p>
  </div>
</body>
</html>
""",
    )


def _brevo_send(to_email, to_name, subject, html):
    """Send an email via Brevo's HTTP API (avoids SMTP port blocking)."""
    response = http_requests.post(
        'https://api.brevo.com/v3/smtp/email',
        headers={
            'api-key': config.MAIL_API_KEY,
            'Content-Type': 'application/json',
        },
        json={
            'sender': {'name': 'VM Tips', 'email': config.MAIL_DEFAULT_SENDER},
            'to': [{'email': to_email, 'name': to_name}],
            'subject': subject,
            'htmlContent': html,
        },
        timeout=15,
    )
    if not response.ok:
        raise RuntimeError(f'Brevo API error {response.status_code}: {response.text}')


def create_user_with_password(email, name, password):
    """
    Create a new user with a password already set.
    Returns user dict on success, or {'status': 'error', 'message': str}.
    """
    db = SessionLocal()
    try:
        email = email.lower().strip()
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            return {'status': 'error', 'message': 'User already exists'}
        user_count = db.query(User).count()
        if user_count >= config.MAX_USERS:
            return {'status': 'error', 'message': 'max_users'}
        user = User(
            email=email,
            name=name.strip(),
            password_hash=generate_password_hash(password),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            'status': 'success',
            'user': {
                'id': user.id,
                'email': user.email,
                'name': user.name,
                'is_admin': user.is_admin,
            },
        }
    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def get_user_by_id(user_id):
    db = SessionLocal()
    try:
        return db.query(User).filter_by(id=user_id).first()
    finally:
        db.close()


def get_user_by_email(email):
    db = SessionLocal()
    try:
        return db.query(User).filter_by(email=email).first()
    finally:
        db.close()

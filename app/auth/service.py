"""Authentication service - Magic link generation and verification"""
import secrets
from datetime import datetime, timedelta
from flask_mail import Message
from flask import current_app
from database.models import User, MagicLink, SessionLocal
from config import settings


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
            if user_count >= settings.MAX_USERS:
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
            expires_at=datetime.utcnow() + timedelta(hours=settings.MAGIC_LINK_EXPIRY_HOURS),
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
    """Send magic link email using Flask-Mail"""
    mail = current_app.extensions['mail']
    link = f"{settings.APP_URL}/auth/verify?token={token}"
    first_name = name.split()[0] if name else 'there'

    msg = Message(
        subject='Your VM Tips login link',
        recipients=[email],
        body=f"""Hi {first_name}!

Here is your login link for VM Tips:

{link}

The link is valid until you request a new one.

If you didn't request this, you can safely ignore this email.

Cheers,
VM Tips
""",
        html=f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; color: #333;">
  <div style="background: #4CAF50; padding: 24px 32px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">VM Tips ⚽</h1>
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
      This link stays valid until you request a new one.<br>
      If you didn't request this, you can safely ignore this email.
    </p>
  </div>
</body>
</html>
"""
    )
    mail.send(msg)


def verify_magic_link(token):
    """
    Verify magic link token.
    Returns user dict if valid, None if invalid or already used.
    """
    db = SessionLocal()
    try:
        magic_link = db.query(MagicLink).filter_by(token=token, used=False).first()
        if not magic_link:
            return None
        if magic_link.expires_at < datetime.utcnow():
            magic_link.used = True
            db.commit()
            return None

        magic_link.used = True
        db.commit()

        user = db.query(User).filter_by(id=magic_link.user_id).first()
        if not user:
            return None

        return {
            'id': user.id,
            'email': user.email,
            'name': user.name,
            'is_admin': user.is_admin,
        }

    except Exception as e:
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
    from database.models import Invite
    db = SessionLocal()
    try:
        recipient_email = recipient_email.lower().strip()

        sender = db.query(User).filter_by(id=sender_user_id).first()
        if not sender:
            return {'status': 'error', 'message': 'Unable to send invite right now.'}

        # Hidden limit check — count valid (unused + not expired) invites
        used_count = db.query(Invite).filter_by(sender_id=sender_user_id).count()
        if used_count >= settings.INVITE_LIMIT_PER_USER:
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
            expires_at=datetime.utcnow() + timedelta(days=settings.INVITE_EXPIRY_DAYS),
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
    from database.models import Invite
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
    from database.models import Invite
    db = SessionLocal()
    try:
        invite = db.query(Invite).filter_by(token=token).first()
        if invite:
            invite.used = True
            db.commit()
    finally:
        db.close()


def _send_invite_email(recipient_email, sender_name, token):
    """Send invite email"""
    mail = current_app.extensions['mail']
    link = f"{settings.APP_URL}/join?invite={token}"
    sender_first = sender_name.split()[0] if sender_name else 'Someone'

    msg = Message(
        subject=f'{sender_first} invited you to VM Tips!',
        recipients=[recipient_email],
        body=f"""Hi!

{sender_first} has invited you to join VM Tips — a World Cup prediction competition.

Click the link below to create your account:

{link}

This invite link expires in {settings.INVITE_EXPIRY_DAYS} days.

See you on the leaderboard!
VM Tips
""",
        html=f"""
<html>
<body style="font-family: Arial, sans-serif; max-width: 580px; margin: 0 auto; color: #333;">
  <div style="background: #4CAF50; padding: 24px 32px; border-radius: 8px 8px 0 0;">
    <h1 style="color: white; margin: 0; font-size: 22px;">VM Tips ⚽</h1>
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
      This invite expires in {settings.INVITE_EXPIRY_DAYS} days.<br>
      If you weren't expecting this, you can safely ignore it.
    </p>
  </div>
</body>
</html>
"""
    )
    mail.send(msg)


def create_user(email, name):
    """Create a new user (kept for compatibility)"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter_by(email=email).first()
        if existing:
            return {'status': 'error', 'message': 'User already exists'}
        user = User(email=email, name=name)
        db.add(user)
        db.commit()
        return {'status': 'success', 'user': user}
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

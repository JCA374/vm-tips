"""Authentication service - Magic link generation and verification"""
import secrets
from datetime import datetime
from flask_mail import Message
from flask import current_app
from database.models import User, MagicLink, SessionLocal
from config import settings


def generate_token():
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def send_magic_link(email):
    """
    Send magic link to user's email
    Creates user if doesn't exist
    """
    db = SessionLocal()

    try:
        # Find or create user
        user = db.query(User).filter_by(email=email).first()

        if not user:
            # Create new user with email as name (can be updated later)
            user = User(
                email=email,
                name=email.split('@')[0]  # Use email prefix as default name
            )
            db.add(user)
            db.flush()  # Get user.id

        # Generate magic link token (no expiry)
        token = generate_token()

        magic_link = MagicLink(
            user_id=user.id,
            token=token,
            expires_at=datetime(9999, 12, 31)  # effectively never expires
        )
        db.add(magic_link)
        db.commit()

        # Send email
        _send_email(email, token)

        return {'status': 'success', 'message': 'Magic link sent'}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def _send_email(email, token):
    """Send magic link email using Flask-Mail"""
    mail = current_app.extensions['mail']

    link = f"{settings.APP_URL}/auth/verify?token={token}"

    msg = Message(
        subject='Your VM Tips Login Link',
        recipients=[email],
        body=f"""
Hello!

Click the link below to login to VM Tips:

{link}

This link will expire in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.

If you didn't request this, you can safely ignore this email.

Cheers,
VM Tips Team
        """,
        html=f"""
        <html>
            <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2>VM Tips Login</h2>
                <p>Hello!</p>
                <p>Click the button below to login to VM Tips:</p>
                <p style="margin: 30px 0;">
                    <a href="{link}"
                       style="background-color: #4CAF50; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Login to VM Tips
                    </a>
                </p>
                <p style="color: #666; font-size: 14px;">
                    This link will expire in {settings.MAGIC_LINK_EXPIRY_MINUTES} minutes.
                </p>
                <p style="color: #666; font-size: 14px;">
                    If you didn't request this, you can safely ignore this email.
                </p>
            </body>
        </html>
        """
    )

    mail.send(msg)


def verify_magic_link(token):
    """
    Verify magic link token
    Returns dict with user data if valid, None if invalid/already used
    """
    db = SessionLocal()

    try:
        magic_link = db.query(MagicLink).filter_by(token=token, used=False).first()

        if not magic_link:
            return None

        # Mark as used
        magic_link.used = True
        db.commit()

        user = db.query(User).filter_by(id=magic_link.user_id).first()
        if not user:
            return None

        # Return plain dict — avoids DetachedInstanceError after session closes
        return {
            'id': user.id,
            'email': user.email,
            'is_admin': user.is_admin,
        }

    except Exception as e:
        print(f"Error verifying magic link: {e}")
        return None
    finally:
        db.close()


def create_user(email, name):
    """Create a new user"""
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
    """Get user by ID"""
    db = SessionLocal()
    try:
        return db.query(User).filter_by(id=user_id).first()
    finally:
        db.close()


def get_user_by_email(email):
    """Get user by email"""
    db = SessionLocal()
    try:
        return db.query(User).filter_by(email=email).first()
    finally:
        db.close()

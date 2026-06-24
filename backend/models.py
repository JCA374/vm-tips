"""Database models for VM Tips application"""
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime
from backend import config

# All rounds use 1X2 betting. 1 point per correct prediction.
SCORE_ROUNDS = set()  # Legacy — no rounds use exact-score betting anymore

Base = declarative_base()
engine = create_engine(config.SQLALCHEMY_DATABASE_URI)
SessionLocal = sessionmaker(bind=engine)


class User(Base):
    """User model"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)
    last_active_at = Column(DateTime, nullable=True)

    # Relationships
    predictions = relationship('Prediction', back_populates='user', cascade='all, delete-orphan')
    magic_links = relationship('MagicLink', back_populates='user', cascade='all, delete-orphan')
    sent_invites = relationship('Invite', back_populates='sender', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email}>'


class MagicLink(Base):
    """Magic link tokens for passwordless authentication"""
    __tablename__ = 'magic_links'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used = Column(Boolean, default=False)

    # Relationships
    user = relationship('User', back_populates='magic_links')

    def __repr__(self):
        return f'<MagicLink {self.token[:8]}... for user {self.user_id}>'


class Match(Base):
    """Match model - knockout round matches"""
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True)
    external_id = Column(Integer, unique=True, index=True)  # ID from football API
    round = Column(String(50), nullable=False)
    group = Column(String(20), nullable=True)   # e.g. 'GROUP_A' — group stage only
    home_team = Column(String(100), nullable=False)
    away_team = Column(String(100), nullable=False)
    match_date = Column(DateTime, nullable=False)

    # Results (null until match is played)
    home_goals = Column(Integer, nullable=True)
    away_goals = Column(Integer, nullable=True)
    finished = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    predictions = relationship('Prediction', back_populates='match', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Match {self.home_team} vs {self.away_team} ({self.round})>'


class Prediction(Base):
    """User predictions for matches"""
    __tablename__ = 'predictions'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)

    # 1X2: '1' (home win), 'X' (draw), or '2' (away win)
    predicted_outcome = Column(String(1), nullable=True)

    # Legacy exact-score fields (no longer used)
    predicted_home_goals = Column(Integer, nullable=True)
    predicted_away_goals = Column(Integer, nullable=True)

    # Calculated points (null until match is finished)
    points = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship('User', back_populates='predictions')
    match = relationship('Match', back_populates='predictions')

    def calculate_points(self):
        """Calculate points: 1 point for correct 1X2 prediction."""
        if not self.match.finished:
            return None

        if not self.predicted_outcome:
            return 0

        actual_home = self.match.home_goals
        actual_away = self.match.away_goals
        actual_outcome = 'X' if actual_home == actual_away else ('1' if actual_home > actual_away else '2')
        return 1 if self.predicted_outcome == actual_outcome else 0

    def __repr__(self):
        return f'<Prediction user={self.user_id} match={self.match_id} {self.predicted_home_goals}-{self.predicted_away_goals}>'


class Invite(Base):
    """Invite tokens — each user can send a limited number"""
    __tablename__ = 'invites'

    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    recipient_email = Column(String(255), nullable=False)
    token = Column(String(255), unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    sender = relationship('User', back_populates='sent_invites')

    def is_valid(self):
        return not self.used and datetime.utcnow() < self.expires_at

    def __repr__(self):
        return f'<Invite from={self.sender_id} to={self.recipient_email}>'


class ActivityLog(Base):
    """Tracks page views per user for monitoring app usage"""
    __tablename__ = 'activity_log'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    path = Column(String(500), nullable=False)
    method = Column(String(10), nullable=False, default='GET')
    status_code = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)

    def __repr__(self):
        return f'<ActivityLog user={self.user_id} {self.method} {self.path}>'


class RoundDeadline(Base):
    """Deadlines for each round"""
    __tablename__ = 'round_deadlines'

    id = Column(Integer, primary_key=True)
    round = Column(String(50), unique=True, nullable=False)  # 'round_of_16', etc.
    deadline = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def is_past(self):
        """Check if deadline has passed"""
        return datetime.utcnow() > self.deadline

    def __repr__(self):
        return f'<RoundDeadline {self.round} at {self.deadline}>'


def init_db():
    """Initialize the database - create all tables and run migrations"""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    try:
        Base.metadata.create_all(engine)
    except OperationalError:
        pass  # Race between gunicorn workers — table already created
    with engine.connect() as conn:
        # Migration: add columns if they don't exist yet
        user_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(users)"))]
        if 'password_hash' not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
            conn.commit()
        if 'last_login_at' not in user_cols:
            try:
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at DATETIME"))
                conn.execute(text("ALTER TABLE users ADD COLUMN last_active_at DATETIME"))
                conn.commit()
            except OperationalError:
                pass  # Already added by another worker


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        return db
    finally:
        pass  # Session will be closed by caller


def drop_db():
    """Drop all tables - USE WITH CAUTION"""
    Base.metadata.drop_all(engine)

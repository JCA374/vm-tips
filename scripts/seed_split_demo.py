"""Seed the LOCAL demo DB for the two-deadline (split) demo.

Fills round_of_32 with real team names, sets a password for the demo login,
and gives the demo user a few saved predictions so the predict page looks alive.

Run:
  DATABASE_PATH=data/vm_tips_local.db venv/bin/python scripts/seed_split_demo.py
"""
import os

os.environ.setdefault('DATABASE_PATH', os.path.join('data', 'vm_tips_local.db'))

from backend.models import SessionLocal, Match, Prediction, User, init_db
from backend.auth.service import set_password

init_db()  # ensure migrated columns (password_hash, last_login_at, ...) exist

DEMO_EMAIL = 'jonca374@gmail.com'
DEMO_PASSWORD = 'demo1234'

# 16 round_of_32 matchups (home, away) in match-date order
R32_TEAMS = [
    ('Argentina', 'Norway'),
    ('Spain', 'Japan'),
    ('France', 'Senegal'),
    ('England', 'Ecuador'),
    ('Brazil', 'South Korea'),
    ('Portugal', 'Mexico'),
    ('Netherlands', 'Croatia'),
    ('Germany', 'Switzerland'),
    ('Belgium', 'Morocco'),
    ('Uruguay', 'United States'),
    ('Colombia', 'Australia'),
    ('Italy', 'Nigeria'),
    ('Denmark', 'Canada'),
    ('Sweden', 'Poland'),
    ('Austria', 'Egypt'),
    ('Norway', 'Ghana'),
]


def main():
    db = SessionLocal()
    try:
        r32 = (db.query(Match)
               .filter(Match.round == 'round_of_32')
               .order_by(Match.match_date)
               .all())
        print(f'round_of_32 matches: {len(r32)}')

        for m, (home, away) in zip(r32, R32_TEAMS):
            m.home_team = home
            m.away_team = away
        db.commit()
        print('  filled team names')

        # Saved predictions for the demo user across the round
        user = db.query(User).filter_by(email=DEMO_EMAIL).first()
        outcomes = ['1', '1', 'X', '2', '1', 'X', '1', '2', '1', '1', 'X', '2', '1', '1', '2', 'X']
        n = 0
        for m, out in zip(r32, outcomes):
            pred = db.query(Prediction).filter_by(user_id=user.id, match_id=m.id).first()
            if pred:
                pred.predicted_outcome = out
            else:
                db.add(Prediction(user_id=user.id, match_id=m.id, predicted_outcome=out))
            n += 1
        db.commit()
        print(f'  set {n} predictions for {user.name}')

        set_password(user.id, DEMO_PASSWORD)
        print(f'  password for {DEMO_EMAIL} set to: {DEMO_PASSWORD}')
    finally:
        db.close()
    print('Done.')


if __name__ == '__main__':
    main()

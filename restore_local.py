"""Restore a JSON backup into the local dev database (data/vm_tips_local.db).

Usage:
    source venv/bin/activate
    python restore_local.py vm_backup_20260612_081813.json

Assumes vm_tips_local.db already exists (copied from live) with matches.
Restores users and predictions from the backup on top of it.
"""
import json
import sys
import os
from datetime import datetime
from pathlib import Path

# Point to local dev database BEFORE importing models
os.environ['DATABASE_PATH'] = str(Path(__file__).parent / 'data' / 'vm_tips_local.db')

from backend.models import (
    SessionLocal, User, Match, Prediction, RoundDeadline
)


def parse_dt(s):
    if not s:
        return None
    for fmt in ('%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M'):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def restore(backup_path):
    with open(backup_path) as f:
        data = json.load(f)

    db = SessionLocal()

    # Restore users (upsert)
    user_count = 0
    for u in data.get('users', []):
        existing = db.query(User).filter_by(email=u['email']).first()
        if existing:
            existing.name = u['name']
            existing.is_admin = u.get('is_admin', False)
        else:
            user = User(
                email=u['email'],
                name=u['name'],
                is_admin=u.get('is_admin', False),
                created_at=parse_dt(u.get('created_at')),
            )
            db.add(user)
        user_count += 1
    db.flush()
    print(f"Upserted {user_count} users")

    # Restore predictions
    pred_count = 0
    skipped = 0
    for p in data.get('predictions', []):
        user = db.query(User).filter_by(email=p['user_email']).first()
        match = db.query(Match).filter_by(external_id=p['match_external_id']).first()
        if not user or not match:
            skipped += 1
            continue

        existing = db.query(Prediction).filter_by(user_id=user.id, match_id=match.id).first()
        if existing:
            existing.predicted_outcome = p.get('predicted_outcome')
            existing.predicted_home_goals = p.get('predicted_home_goals')
            existing.predicted_away_goals = p.get('predicted_away_goals')
            existing.points = p.get('points')
            existing.updated_at = parse_dt(p.get('updated_at'))
        else:
            pred = Prediction(
                user_id=user.id,
                match_id=match.id,
                predicted_outcome=p.get('predicted_outcome'),
                predicted_home_goals=p.get('predicted_home_goals'),
                predicted_away_goals=p.get('predicted_away_goals'),
                points=p.get('points'),
                created_at=parse_dt(p.get('created_at')),
                updated_at=parse_dt(p.get('updated_at')),
            )
            db.add(pred)
        pred_count += 1
    print(f"Restored {pred_count} predictions (skipped {skipped})")

    db.commit()
    db.close()
    print(f"\nDone! Run local server:")
    print(f"  DATABASE_PATH=data/vm_tips_local.db python run.py")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <backup.json>")
        sys.exit(1)
    restore(sys.argv[1])

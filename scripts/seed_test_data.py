"""
Seed script — test users, random group stage predictions & results.

Usage:
    python scripts/seed_test_data.py seed     # Add test data
    python scripts/seed_test_data.py clean    # Remove all test data and reset match results
"""

import sys
import random
from datetime import datetime

sys.path.insert(0, '.')

from database.models import SessionLocal, User, Match, Prediction, RoundDeadline, init_db

# ── Config ────────────────────────────────────────────────────────────────────

TEST_USER_MARKER = '[test]'   # All test user emails contain this — used for cleanup

TEST_USERS = [
    {'name': 'Alice Test',   'email': 'alice[test]@vm-tips.dev'},
    {'name': 'Bob Test',     'email': 'bob[test]@vm-tips.dev'},
    {'name': 'Charlie Test', 'email': 'charlie[test]@vm-tips.dev'},
    {'name': 'Diana Test',   'email': 'diana[test]@vm-tips.dev'},
    {'name': 'Erik Test',    'email': 'erik[test]@vm-tips.dev'},
]

GROUP_ROUNDS = {'group_md1', 'group_md2', 'group_md3'}
OUTCOMES = ['1', 'X', '2']

random.seed()   # Fresh randomness each run


# ── Helpers ───────────────────────────────────────────────────────────────────

def random_score():
    """Realistic-ish football score: weighted toward low-scoring games"""
    goals = [0, 1, 1, 1, 2, 2, 2, 3, 3, 4]
    return random.choice(goals), random.choice(goals)


def outcome_from_score(home, away):
    if home > away:
        return '1'
    if away > home:
        return '2'
    return 'X'


# ── Seed ──────────────────────────────────────────────────────────────────────

def seed():
    db = SessionLocal()
    try:
        # 1. Create test users (skip if already exists)
        users = []
        for u in TEST_USERS:
            existing = db.query(User).filter_by(email=u['email']).first()
            if existing:
                print(f"  Skipping existing user: {u['name']}")
                users.append(existing)
            else:
                user = User(email=u['email'], name=u['name'])
                db.add(user)
                db.flush()
                users.append(user)
                print(f"  Created user: {u['name']}")

        # 2. Set random results on all group stage matches
        group_matches = db.query(Match).filter(Match.round.in_(GROUP_ROUNDS)).all()
        print(f"\n  Setting results for {len(group_matches)} group stage matches...")
        for match in group_matches:
            home, away = random_score()
            match.home_goals = home
            match.away_goals = away
            match.finished = True

        db.flush()

        # 3. Create random predictions for each test user
        print(f"\n  Generating predictions for {len(users)} test users...")
        for user in users:
            count = 0
            for match in group_matches:
                # Skip if prediction already exists
                existing = db.query(Prediction).filter_by(
                    user_id=user.id, match_id=match.id
                ).first()
                if existing:
                    continue

                # Random 1X2 outcome, slightly biased toward the actual result
                actual = outcome_from_score(match.home_goals, match.away_goals)
                # 50% chance of getting it right, 50% random
                if random.random() < 0.5:
                    pick = actual
                else:
                    pick = random.choice(OUTCOMES)

                pred = Prediction(
                    user_id=user.id,
                    match_id=match.id,
                    predicted_outcome=pick,
                )
                db.add(pred)
                count += 1
            print(f"    {user.name}: {count} predictions")

        # 3b. Set group stage deadlines to the past so results are visible
        print("\n  Setting group stage deadlines to the past...")
        for round_key in GROUP_ROUNDS:
            dl = db.query(RoundDeadline).filter_by(round=round_key).first()
            past = datetime(2020, 1, 1)
            if dl:
                dl.deadline = past
            else:
                db.add(RoundDeadline(round=round_key, deadline=past))
        print("  Deadlines set — results page will now show group stage predictions")

        db.commit()

        # 4. Calculate scores
        print("\n  Calculating scores...")
        from app.prediction.service import calculate_all_scores
        result = calculate_all_scores()
        print(f"  Updated {result.get('updated', 0)} predictions")

        # 5. Print leaderboard preview
        from app.prediction.service import get_leaderboard
        board = get_leaderboard()
        print("\n  ── Leaderboard preview ──────────────────")
        for i, entry in enumerate(board, 1):
            print(f"  {i:2}. {entry['name']:<20} {entry['total_points']:>3} pts")
        print()

    finally:
        db.close()


# ── Clean ─────────────────────────────────────────────────────────────────────

def clean():
    db = SessionLocal()
    try:
        # Find all test users
        test_users = db.query(User).filter(User.email.like(f'%{TEST_USER_MARKER}%')).all()

        if not test_users:
            print("  No test users found.")
        else:
            for user in test_users:
                db.delete(user)   # cascade deletes their predictions
                print(f"  Removed user: {user.name}")

        # Reset all group stage match results
        group_matches = db.query(Match).filter(Match.round.in_(GROUP_ROUNDS)).all()
        for match in group_matches:
            match.home_goals = None
            match.away_goals = None
            match.finished = False
        print(f"  Reset {len(group_matches)} group stage matches")

        # Restore real deadlines (first kick-off of each round)
        real_deadlines = {
            'group_md1': datetime(2026, 6, 11, 19, 0),
            'group_md2': datetime(2026, 6, 18, 16, 0),
            'group_md3': datetime(2026, 6, 24, 19, 0),
        }
        for round_key, dt in real_deadlines.items():
            dl = db.query(RoundDeadline).filter_by(round=round_key).first()
            if dl:
                dl.deadline = dt
        print("  Restored real group stage deadlines")

        db.commit()
        print("  Done.")
    finally:
        db.close()


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == '__main__':
    init_db()

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'seed'

    if cmd == 'seed':
        print("Seeding test data...\n")
        seed()
    elif cmd == 'clean':
        print("Cleaning up test data...\n")
        clean()
    else:
        print(__doc__)
        sys.exit(1)

"""Prediction service - Manage predictions and calculate scores"""
from datetime import datetime
from backend.models import Prediction, Match, User, RoundDeadline, SessionLocal


# ── Split deadline ────────────────────────────────────────────────────────────
# round_of_32 uses TWO deadlines: one for the matches on the earliest date, and
# one for all the rest. The earliest-date deadline is the stored 'round_of_32'
# RoundDeadline row; the 'rest' deadline is derived as the first kickoff among
# round_of_32 matches that are NOT on the earliest date.
SPLIT_ROUND = 'round_of_32'
REST_KEY = 'round_of_32_rest'


def r32_early_date(db):
    """Date of the earliest round_of_32 match (None if none exist)."""
    first = (db.query(Match)
             .filter(Match.round == SPLIT_ROUND)
             .order_by(Match.match_date)
             .first())
    return first.match_date.date() if first else None


def effective_deadlines(db):
    """{key: deadline_datetime} for all rounds, plus the derived REST_KEY."""
    out = {d.round: d.deadline for d in db.query(RoundDeadline).all()}
    early = r32_early_date(db)
    if early:
        later = [m.match_date for m in db.query(Match).filter(Match.round == SPLIT_ROUND).all()
                 if m.match_date.date() != early]
        if later:
            out[REST_KEY] = min(later)
    return out


def deadline_key_for_match(match, early_date):
    """Which deadline key governs a given match."""
    if match.round == SPLIT_ROUND and early_date and match.match_date.date() != early_date:
        return REST_KEY
    return match.round


def match_deadline_passed(match, deadlines, early_date):
    """True if the deadline governing this match has passed."""
    dl = deadlines.get(deadline_key_for_match(match, early_date))
    return bool(dl and datetime.utcnow() > dl)


def submit_prediction(user_id, match_id, outcome=None, home_goals=None, away_goals=None):
    """
    Submit or update a prediction for a match.
    - 1X2 rounds: pass outcome='1'/'X'/'2'
    - Exact-score rounds: pass home_goals and away_goals
    Returns error if deadline has passed.
    """
    db = SessionLocal()

    try:
        match = db.query(Match).filter_by(id=match_id).first()
        if not match:
            return {'status': 'error', 'message': 'Match not found'}

        if match.finished:
            return {'status': 'error', 'message': 'Match already finished'}

        if match_deadline_passed(match, effective_deadlines(db), r32_early_date(db)):
            return {'status': 'error', 'message': 'Deadline has passed'}

        existing = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()

        if existing:
            if existing.predicted_outcome == outcome:
                return {'status': 'success', 'message': 'Prediction unchanged'}
            existing.predicted_outcome = outcome
            existing.updated_at = datetime.utcnow()
            message = 'Prediction updated'
        else:
            prediction = Prediction(
                user_id=user_id,
                match_id=match_id,
                predicted_outcome=outcome,
            )
            db.add(prediction)
            message = 'Prediction submitted'

        db.commit()
        return {'status': 'success', 'message': message}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def admin_set_prediction(user_id, match_id, outcome):
    """
    Admin override: set a user's 1X2 prediction WITHOUT the deadline check.
    For helping players who missed the deadline. Works on finished matches too —
    points are recalculated immediately so the leaderboard stays correct.
    """
    db = SessionLocal()
    try:
        match = db.query(Match).filter_by(id=match_id).first()
        if not match:
            return {'status': 'error', 'message': 'Match not found'}

        if outcome not in ('1', 'X', '2'):
            return {'status': 'error', 'message': 'Invalid outcome'}

        existing = db.query(Prediction).filter_by(user_id=user_id, match_id=match_id).first()
        if existing:
            existing.predicted_outcome = outcome
            existing.updated_at = datetime.utcnow()
            pred = existing
            message = 'Prediction updated'
        else:
            pred = Prediction(user_id=user_id, match_id=match_id, predicted_outcome=outcome)
            db.add(pred)
            message = 'Prediction set'

        # If the match is already played, recompute points for this prediction
        if match.finished:
            pred.points = pred.calculate_points()

        db.commit()
        return {'status': 'success', 'message': message}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


# ── Test page: goal-based betting on the final ─────────────────────────────────
# Experimental scoring for the final only: 1 point for the correct number of home
# goals, 1 point for the correct number of away goals, and 1 point for the
# resulting 1X2 outcome (max 3). Goals are stored in the legacy
# predicted_home_goals / predicted_away_goals columns so this stays fully isolated
# from the live 1X2 competition (which only ever reads predicted_outcome/points).

def get_final_match(db):
    """The final match, or None if it isn't in the schedule yet."""
    return (db.query(Match)
            .filter(Match.round == 'final')
            .order_by(Match.match_date)
            .first())


def _outcome(home, away):
    """1X2 label from a goal pair."""
    return 'X' if home == away else ('1' if home > away else '2')


def score_final_goals(match, pred_home, pred_away):
    """(home_pt, away_pt, outcome_pt) for a goals prediction vs a finished final."""
    if not match.finished or pred_home is None or pred_away is None:
        return (0, 0, 0)
    home_pt = 1 if pred_home == match.home_goals else 0
    away_pt = 1 if pred_away == match.away_goals else 0
    outcome_pt = 1 if _outcome(pred_home, pred_away) == _outcome(match.home_goals, match.away_goals) else 0
    return (home_pt, away_pt, outcome_pt)


def submit_final_goals(user_id, home_goals, away_goals):
    """Store/update a goals prediction for the final (test page). No deadline check."""
    db = SessionLocal()
    try:
        match = get_final_match(db)
        if not match:
            return {'status': 'error', 'message': 'No final scheduled yet'}
        if match.finished:
            return {'status': 'error', 'message': 'Final already finished'}
        try:
            home_goals = int(home_goals)
            away_goals = int(away_goals)
        except (TypeError, ValueError):
            return {'status': 'error', 'message': 'Please enter whole numbers'}
        if not (0 <= home_goals <= 99 and 0 <= away_goals <= 99):
            return {'status': 'error', 'message': 'Goals must be between 0 and 99'}

        pred = db.query(Prediction).filter_by(user_id=user_id, match_id=match.id).first()
        if pred:
            pred.predicted_home_goals = home_goals
            pred.predicted_away_goals = away_goals
            pred.updated_at = datetime.utcnow()
        else:
            db.add(Prediction(
                user_id=user_id, match_id=match.id,
                predicted_home_goals=home_goals, predicted_away_goals=away_goals,
            ))
        db.commit()
        return {'status': 'success', 'message': 'Prediction saved'}
    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def get_final_test_data():
    """Final match + every user's goal prediction with computed test points."""
    from sqlalchemy.orm import joinedload
    db = SessionLocal()
    try:
        match = get_final_match(db)
        if not match:
            return {'match': None, 'rows': []}
        preds = (db.query(Prediction)
                 .options(joinedload(Prediction.user))
                 .filter(Prediction.match_id == match.id)
                 .all())
        rows = []
        for p in preds:
            if p.predicted_home_goals is None or p.predicted_away_goals is None:
                continue
            home_pt, away_pt, outcome_pt = score_final_goals(
                match, p.predicted_home_goals, p.predicted_away_goals)
            rows.append({
                'user': p.user,
                'home': p.predicted_home_goals,
                'away': p.predicted_away_goals,
                'home_pt': home_pt,
                'away_pt': away_pt,
                'outcome_pt': outcome_pt,
                'total': home_pt + away_pt + outcome_pt,
            })
        rows.sort(key=lambda r: (-r['total'], r['user'].name))
        return {'match': match, 'rows': rows}
    finally:
        db.close()


def get_user_predictions(user_id, round_name=None):
    """Get all predictions for a user, optionally filtered by round"""
    db = SessionLocal()
    try:
        query = db.query(Prediction).filter_by(user_id=user_id)

        if round_name:
            query = query.join(Match).filter(Match.round == round_name)

        return query.all()
    finally:
        db.close()


def get_match_predictions(match_id):
    """Get all predictions for a specific match"""
    from sqlalchemy.orm import joinedload
    db = SessionLocal()
    try:
        return (
            db.query(Prediction)
            .options(joinedload(Prediction.user))
            .filter_by(match_id=match_id)
            .all()
        )
    finally:
        db.close()


def calculate_all_scores():
    """
    Calculate points for all predictions on finished matches
    Should be run after match results are updated
    """
    db = SessionLocal()

    try:
        # Get all predictions for finished matches
        predictions = db.query(Prediction).join(Match).filter(
            Match.finished == True
        ).all()

        updated = 0
        for prediction in predictions:
            points = prediction.calculate_points()
            if points is not None and prediction.points != points:
                prediction.points = points
                updated += 1

        db.commit()
        return {'status': 'success', 'updated': updated}

    except Exception as e:
        db.rollback()
        return {'status': 'error', 'message': str(e)}
    finally:
        db.close()


def get_leaderboard():
    """
    Get leaderboard with total points for each user
    Returns list of dicts with user info and points
    """
    db = SessionLocal()

    try:
        # Query to sum points for each user
        from sqlalchemy import func

        results = db.query(
            User.id,
            User.name,
            User.email,
            func.sum(Prediction.points).label('total_points')
        ).join(Prediction, User.id == Prediction.user_id, isouter=True)\
         .group_by(User.id, User.name, User.email)\
         .order_by(func.sum(Prediction.points).desc(), User.name)\
         .all()

        leaderboard = []
        for result in results:
            pts = result.total_points or 0
            leaderboard.append({
                'user_id': result.id,
                'name': result.name,
                'email': result.email,
                'total_points': pts
            })

        return leaderboard

    finally:
        db.close()


def get_round_leaderboard(round_name):
    """Get leaderboard for a specific round"""
    db = SessionLocal()

    try:
        from sqlalchemy import func

        results = db.query(
            User.id,
            User.name,
            User.email,
            func.sum(Prediction.points).label('round_points')
        ).join(Prediction, User.id == Prediction.user_id)\
         .join(Match, Prediction.match_id == Match.id)\
         .filter(Match.round == round_name)\
         .group_by(User.id, User.name, User.email)\
         .order_by(func.sum(Prediction.points).desc(), User.name)\
         .all()

        leaderboard = []
        for result in results:
            leaderboard.append({
                'user_id': result.id,
                'name': result.name,
                'email': result.email,
                'round_points': result.round_points or 0
            })

        return leaderboard

    finally:
        db.close()


def get_all_predictions_for_round(round_name):
    """
    Get all users' predictions for a round
    Only use after deadline has passed
    """
    db = SessionLocal()

    try:
        predictions = db.query(Prediction)\
            .join(Match)\
            .filter(Match.round == round_name)\
            .all()

        # Group by match
        result = {}
        for pred in predictions:
            match_id = pred.match_id
            if match_id not in result:
                result[match_id] = {
                    'match': pred.match,
                    'predictions': []
                }

            result[match_id]['predictions'].append({
                'user': pred.user,
                'predicted_home': pred.predicted_home_goals,
                'predicted_away': pred.predicted_away_goals,
                'points': pred.points
            })

        return result

    finally:
        db.close()


def check_deadline_passed(round_name):
    """Check if deadline for a round has passed"""
    db = SessionLocal()
    try:
        deadline = db.query(RoundDeadline).filter_by(round=round_name).first()
        return deadline.is_past() if deadline else False
    finally:
        db.close()

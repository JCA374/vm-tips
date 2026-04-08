"""Prediction service - Manage predictions and calculate scores"""
from datetime import datetime
from database.models import Prediction, Match, User, RoundDeadline, SessionLocal


def submit_prediction(user_id, match_id, home_goals, away_goals):
    """
    Submit or update a prediction for a match
    Returns error if deadline has passed
    """
    db = SessionLocal()

    try:
        # Get match
        match = db.query(Match).filter_by(id=match_id).first()
        if not match:
            return {'status': 'error', 'message': 'Match not found'}

        # Check if match already finished
        if match.finished:
            return {'status': 'error', 'message': 'Match already finished'}

        # Check deadline
        deadline = db.query(RoundDeadline).filter_by(round=match.round).first()
        if deadline and deadline.is_past():
            return {'status': 'error', 'message': 'Deadline has passed'}

        # Find existing prediction
        existing = db.query(Prediction).filter_by(
            user_id=user_id,
            match_id=match_id
        ).first()

        if existing:
            # Update existing
            existing.predicted_home_goals = home_goals
            existing.predicted_away_goals = away_goals
            existing.updated_at = datetime.utcnow()
            message = 'Prediction updated'
        else:
            # Create new
            prediction = Prediction(
                user_id=user_id,
                match_id=match_id,
                predicted_home_goals=home_goals,
                predicted_away_goals=away_goals
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
         .order_by(func.sum(Prediction.points).desc())\
         .all()

        leaderboard = []
        for result in results:
            leaderboard.append({
                'user_id': result.id,
                'name': result.name,
                'email': result.email,
                'total_points': result.total_points or 0
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
         .order_by(func.sum(Prediction.points).desc())\
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

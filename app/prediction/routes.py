"""Prediction routes - Betting form, leaderboard, results"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.prediction.service import (
    get_leaderboard, submit_prediction, get_user_predictions,
    get_all_predictions_for_round, check_deadline_passed
)
from app.match_data.service import get_upcoming_matches
from database.models import SessionLocal, RoundDeadline

prediction_bp = Blueprint('prediction', __name__)


@prediction_bp.route('/leaderboard')
def leaderboard():
    """Show leaderboard with scores"""
    leaderboard_data = get_leaderboard()
    return render_template('prediction/leaderboard.html', leaderboard=leaderboard_data)


@prediction_bp.route('/predict', methods=['GET', 'POST'])
def predict():
    """Prediction form for current round"""
    if not session.get('user_id'):
        flash('Please login first.')
        return redirect(url_for('auth.login'))

    # Get current round - for now, show all upcoming matches
    matches = get_upcoming_matches()

    if request.method == 'POST':
        user_id = session['user_id']

        # Process each match prediction
        for match in matches:
            home_key = f'home_{match.id}'
            away_key = f'away_{match.id}'

            if home_key in request.form and away_key in request.form:
                home_goals = int(request.form[home_key])
                away_goals = int(request.form[away_key])

                result = submit_prediction(user_id, match.id, home_goals, away_goals)
                if result['status'] == 'error':
                    flash(f"Error for {match.home_team} vs {match.away_team}: {result['message']}")

        flash('Predictions saved!')
        return redirect(url_for('prediction.predict'))

    # Get user's existing predictions
    user_id = session['user_id']
    user_preds = get_user_predictions(user_id)
    predictions_dict = {p.match_id: p for p in user_preds}

    # Get deadline for first match (simplified - could be per round)
    deadline = None
    if matches:
        db = SessionLocal()
        deadline = db.query(RoundDeadline).filter_by(round=matches[0].round).first()
        db.close()

    return render_template('prediction/predict.html',
                          matches=matches,
                          predictions=predictions_dict,
                          deadline=deadline)


@prediction_bp.route('/results')
def results():
    """View all predictions (after deadline)"""
    # For now, show all rounds - could filter by round
    # Get all predictions grouped by match
    db = SessionLocal()
    from database.models import Match

    all_matches = db.query(Match).all()
    predictions_by_match = {}

    for match in all_matches:
        # Only show if deadline passed
        deadline = db.query(RoundDeadline).filter_by(round=match.round).first()
        if deadline and deadline.is_past():
            from app.prediction.service import get_match_predictions
            preds = get_match_predictions(match.id)

            predictions_by_match[match.id] = {
                'match': match,
                'predictions': [
                    {
                        'user': p.user,
                        'predicted_home': p.predicted_home_goals,
                        'predicted_away': p.predicted_away_goals,
                        'points': p.points
                    }
                    for p in preds
                ]
            }

    db.close()

    return render_template('prediction/results.html',
                          predictions_by_match=predictions_by_match)

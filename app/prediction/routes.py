"""Prediction routes - Betting form, leaderboard, results"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.prediction.service import (
    get_leaderboard, submit_prediction, get_user_predictions,
    get_all_predictions_for_round, check_deadline_passed
)
from database.models import SessionLocal, RoundDeadline, Match

prediction_bp = Blueprint('prediction', __name__)

ROUNDS = [
    ('group_md1',   'Groups — Matchday 1'),
    ('group_md2',   'Groups — Matchday 2'),
    ('group_md3',   'Groups — Matchday 3'),
    ('round_of_32', 'Round of 32'),
    ('round_of_16', 'Round of 16'),
    ('quarter_final', 'Quarter Finals'),
    ('semi_final',  'Semi Finals'),
    ('final',       'Final'),
]


@prediction_bp.route('/leaderboard')
def leaderboard():
    """Show leaderboard with scores"""
    leaderboard_data = get_leaderboard()
    return render_template('prediction/leaderboard.html', leaderboard=leaderboard_data)


@prediction_bp.route('/predict', methods=['GET', 'POST'])
def predict():
    """Prediction form — all rounds grouped"""
    if not session.get('user_id'):
        flash('Please login first.')
        return redirect(url_for('auth.login'))

    db = SessionLocal()
    all_matches = db.query(Match).order_by(Match.match_date).all()
    deadlines = {d.round: d for d in db.query(RoundDeadline).all()}
    db.close()

    if request.method == 'POST':
        user_id = session['user_id']
        for match in all_matches:
            home_key = f'home_{match.id}'
            away_key = f'away_{match.id}'
            if home_key in request.form and away_key in request.form:
                try:
                    home_goals = int(request.form[home_key])
                    away_goals = int(request.form[away_key])
                    result = submit_prediction(user_id, match.id, home_goals, away_goals)
                    if result['status'] == 'error':
                        flash(f"{match.home_team} vs {match.away_team}: {result['message']}", 'error')
                except ValueError:
                    pass
        flash('Predictions saved!')
        return redirect(url_for('prediction.predict'))

    user_id = session['user_id']
    user_preds = get_user_predictions(user_id)
    predictions_dict = {p.match_id: p for p in user_preds}

    # Group matches by round
    rounds_data = []
    for round_key, round_label in ROUNDS:
        round_matches = [m for m in all_matches if m.round == round_key]
        # For group stage: sort by group then date so group headers render correctly
        if round_key.startswith('group_'):
            round_matches.sort(key=lambda m: (m.group or '', m.match_date))
        deadline = deadlines.get(round_key)
        rounds_data.append({
            'key': round_key,
            'label': round_label,
            'matches': round_matches,
            'deadline': deadline,
            'locked': deadline.is_past() if deadline else False,
        })

    return render_template('prediction/predict.html',
                           rounds_data=rounds_data,
                           predictions=predictions_dict)


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

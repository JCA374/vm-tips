"""Prediction routes - Betting form, leaderboard, results"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.prediction.service import (
    get_leaderboard, submit_prediction, get_user_predictions,
    get_all_predictions_for_round, check_deadline_passed
)
from database.models import SessionLocal, RoundDeadline, Match, SCORE_ROUNDS

prediction_bp = Blueprint('prediction', __name__)

ROUNDS = [
    ('group_md1',   'Round 1'),
    ('group_md2',   'Round 2'),
    ('group_md3',   'Round 3'),
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
            if match.round in SCORE_ROUNDS:
                home_key = f'home_{match.id}'
                away_key = f'away_{match.id}'
                if home_key in request.form and away_key in request.form:
                    try:
                        home_goals = int(request.form[home_key])
                        away_goals = int(request.form[away_key])
                        result = submit_prediction(user_id, match.id, home_goals=home_goals, away_goals=away_goals)
                        if result['status'] == 'error':
                            flash(f"{match.home_team} vs {match.away_team}: {result['message']}", 'error')
                    except ValueError:
                        pass
            else:
                outcome_key = f'outcome_{match.id}'
                outcome = request.form.get(outcome_key)
                if outcome in ('1', 'X', '2'):
                    result = submit_prediction(user_id, match.id, outcome=outcome)
                    if result['status'] == 'error':
                        flash(f"{match.home_team} vs {match.away_team}: {result['message']}", 'error')
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
            'is_score_round': round_key in SCORE_ROUNDS,
        })

    return render_template('prediction/predict.html',
                           rounds_data=rounds_data,
                           predictions=predictions_dict)


@prediction_bp.route('/results')
def results():
    if not session.get('user_id'):
        flash('Please login to view results.')
        return redirect(url_for('auth.login'))

    db = SessionLocal()
    from database.models import Match, Prediction, User
    from sqlalchemy.orm import joinedload

    # Only include matches whose round deadline has passed
    deadlines = {d.round: d for d in db.query(RoundDeadline).all()}
    open_rounds = {r for r, d in deadlines.items() if d.is_past()}

    visible_matches = (
        db.query(Match)
        .filter(Match.round.in_(open_rounds))
        .order_by(Match.match_date)
        .all()
    ) if open_rounds else []

    # All predictions for visible matches, with user + match loaded
    all_preds = (
        db.query(Prediction)
        .options(joinedload(Prediction.user), joinedload(Prediction.match))
        .filter(Prediction.match_id.in_([m.id for m in visible_matches]))
        .all()
    ) if visible_matches else []

    # ── Per-game structure ────────────────────────────────────────────────────
    predictions_by_match = {}
    for match in visible_matches:
        predictions_by_match[match.id] = {'match': match, 'predictions': []}

    for p in all_preds:
        predictions_by_match[p.match_id]['predictions'].append({
            'user':              p.user,
            'predicted_outcome': p.predicted_outcome,
            'predicted_home':    p.predicted_home_goals,
            'predicted_away':    p.predicted_away_goals,
            'points':            p.points,
        })

    # ── Per-user structure ────────────────────────────────────────────────────
    predictions_by_user = {}
    for p in all_preds:
        uid = p.user_id
        if uid not in predictions_by_user:
            predictions_by_user[uid] = {
                'user':         p.user,
                'predictions':  [],
                'total_points': 0,
            }
        predictions_by_user[uid]['predictions'].append({
            'match':             p.match,
            'predicted_outcome': p.predicted_outcome,
            'predicted_home':    p.predicted_home_goals,
            'predicted_away':    p.predicted_away_goals,
            'points':            p.points,
        })
        predictions_by_user[uid]['total_points'] += (p.points or 0)

    # Sort each user's predictions by match date
    for uid in predictions_by_user:
        predictions_by_user[uid]['predictions'].sort(
            key=lambda x: x['match'].match_date
        )

    # Sorted user list for the dropdown
    users = sorted(predictions_by_user.values(), key=lambda u: u['total_points'], reverse=True)

    # All team names that appear in visible matches (for the team filter)
    teams = sorted({
        t for m in visible_matches
        for t in (m.home_team, m.away_team)
        if t != 'TBD'
    })

    db.close()

    return render_template('prediction/results.html',
                           predictions_by_match=predictions_by_match,
                           predictions_by_user=predictions_by_user,
                           users=users,
                           teams=teams)

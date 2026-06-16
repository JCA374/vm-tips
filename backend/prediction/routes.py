"""Prediction routes - Betting form, leaderboard, results"""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from sqlalchemy.orm import joinedload
from backend.prediction.service import (
    get_leaderboard, submit_prediction, get_user_predictions,
    get_all_predictions_for_round, check_deadline_passed,
    calculate_all_scores,
)
from backend.models import SessionLocal, RoundDeadline, Match, Prediction, User

prediction_bp = Blueprint('prediction', __name__)

ROUNDS = [
    ('group_md1',   'Round 1'),
    ('group_md2',   'Round 2'),
    ('group_md3',   'Round 3'),
    ('round_of_32', 'Round of 32'),
    ('round_of_16', 'Round of 16'),
    ('quarter_final', 'Quarter Finals'),
    ('semi_final',  'Semi Finals'),
    ('third_place', 'Third Place'),
    ('final',       'Final'),
]


@prediction_bp.route('/today')
def today():
    """Today's matches with everyone's predictions."""
    if not session.get('user_id'):
        flash('Please login first.')
        return redirect(url_for('auth.login'))

    calculate_all_scores()
    db = SessionLocal()

    # "Today" in North America (UTC-5 / CDT) to match the match-day grouping
    venue_now = datetime.now(timezone.utc) + timedelta(hours=-5)
    venue_today = venue_now.date()

    # Allow navigating to other dates via ?date=YYYY-MM-DD
    date_str = request.args.get('date')
    from datetime import date as date_type
    if date_str:
        try:
            venue_today = date_type.fromisoformat(date_str)
        except ValueError:
            pass

    # Matches whose venue-local date == selected day: UTC range is [day+05:00, next+05:00)
    day_start_utc = datetime(venue_today.year, venue_today.month, venue_today.day, 5, 0, tzinfo=timezone.utc)
    day_end_utc = day_start_utc + timedelta(days=1)

    # Deadlines to check visibility — only show matches whose round deadline has passed
    deadlines = {d.round: d for d in db.query(RoundDeadline).all()}
    locked_rounds = {r for r, d in deadlines.items() if d.is_past()}

    # Find all match days for navigation — only days with locked-round matches
    all_match_dates_raw = [
        m[0] for m in db.query(Match.match_date)
        .filter(Match.round.in_(locked_rounds)).all()
    ] if locked_rounds else []
    match_days = sorted({(d + timedelta(hours=-5)).date() for d in all_match_dates_raw})

    # Previous and next match day relative to selected date
    prev_day = None
    next_day = None
    for d in match_days:
        if d < venue_today:
            prev_day = d
    for d in match_days:
        if d > venue_today:
            next_day = d
            break

    actual_today = (datetime.now(timezone.utc) + timedelta(hours=-5)).date()
    is_today = venue_today == actual_today

    matches = (
        db.query(Match)
        .filter(Match.match_date >= day_start_utc, Match.match_date < day_end_utc,
                Match.round.in_(locked_rounds))
        .order_by(Match.match_date)
        .all()
    ) if locked_rounds else []

    # All predictions for today's matches
    match_ids = [m.id for m in matches]
    all_preds = (
        db.query(Prediction)
        .options(joinedload(Prediction.user))
        .filter(Prediction.match_id.in_(match_ids))
        .all()
    ) if match_ids else []

    # All users (for column headers)
    users = db.query(User).order_by(User.name).all()

    # Build structure: match -> {user_id: prediction}
    matches_data = []
    for match in matches:
        preds_for_match = {p.user_id: p for p in all_preds if p.match_id == match.id}

        matches_data.append({
            'match': match,
            'predictions': preds_for_match,
            'round_locked': True,  # all shown matches are past deadline
        })

    # Sum points per user for today's finished matches
    day_points = {}
    for md in matches_data:
        if md['match'].finished:
            for uid, pred in md['predictions'].items():
                day_points[uid] = day_points.get(uid, 0) + (pred.points or 0)

    # Group users by identical tip pattern for color-coding
    tip_groups = {}  # user_id -> group index (0-based), only for groups with 2+ members
    if matches_data:
        sig_map = {}  # signature -> [user_ids]
        for user in users:
            sig = tuple(
                (md['predictions'].get(user.id).predicted_outcome
                 if md['predictions'].get(user.id) else None)
                for md in matches_data
            )
            sig_map.setdefault(sig, []).append(user.id)
        color_idx = 0
        for sig, uids in sig_map.items():
            if len(uids) >= 2:
                for uid in uids:
                    tip_groups[uid] = color_idx
                color_idx += 1

    db.close()

    return render_template('prediction/today.html',
                           matches_data=matches_data,
                           users=users,
                           venue_date=venue_today,
                           day_points=day_points,
                           tip_groups=tip_groups,
                           prev_day=prev_day,
                           next_day=next_day,
                           is_today=is_today,
                           actual_today=actual_today)


@prediction_bp.route('/leaderboard')
def leaderboard():
    """Show leaderboard with scores"""
    calculate_all_scores()
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
        active_round = request.form.get('active_round', '')

        # Only process matches from the active round to avoid
        # re-submitting unchanged predictions from other tabs
        round_matches = [m for m in all_matches if m.round == active_round] if active_round else all_matches

        for match in round_matches:
            outcome_key = f'outcome_{match.id}'
            outcome = request.form.get(outcome_key)
            if outcome in ('1', 'X', '2'):
                result = submit_prediction(user_id, match.id, outcome=outcome)
                if result['status'] == 'error':
                    flash(f"{match.home_team} vs {match.away_team}: {result['message']}", 'error')

        flash('Predictions saved!')

        # Warn about any open-round matches that still have no bet
        user_preds_after = get_user_predictions(user_id)
        pred_map = {p.match_id: p for p in user_preds_after}

        for round_key, round_label in ROUNDS:
            if active_round and round_key != active_round:
                continue  # only warn about the round being saved
            deadline = deadlines.get(round_key)
            if deadline and deadline.is_past():
                continue  # locked — not the user's fault
            round_matches = [
                m for m in all_matches
                if m.round == round_key and not m.finished and m.home_team != 'TBD'
            ]
            missing = []
            for m in round_matches:
                pred = pred_map.get(m.id)
                if not pred or not pred.predicted_outcome:
                    missing.append(m)
            if missing:
                if len(missing) <= 3:
                    names = ', '.join(f"{m.home_team} vs {m.away_team}" for m in missing)
                    flash(f"Missing bet in {round_label}: {names}", 'warning')
                else:
                    flash(f"Missing bet in {round_label}: {len(missing)} matches not predicted", 'warning')

        redirect_url = url_for('prediction.predict')
        if active_round:
            redirect_url += f'?tab={active_round}'
        return redirect(redirect_url)

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
            'is_knockout': False,
        })

    # Default to the round with the closest upcoming deadline
    default_tab = None
    soonest_deadline = None
    for rd in rounds_data:
        if rd['deadline'] and not rd['locked']:
            dl = rd['deadline'].deadline
            if soonest_deadline is None or dl < soonest_deadline:
                soonest_deadline = dl
                default_tab = rd['key']

    return render_template('prediction/predict.html',
                           rounds_data=rounds_data,
                           predictions=predictions_dict,
                           default_tab=default_tab)


@prediction_bp.route('/results')
def results():
    if not session.get('user_id'):
        flash('Please login to view results.')
        return redirect(url_for('auth.login'))

    calculate_all_scores()
    db = SessionLocal()
    from backend.models import Match, Prediction, User
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

"""Prediction routes - Betting form, leaderboard, results"""
from datetime import datetime, timezone, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify
from sqlalchemy.orm import joinedload
from backend.prediction.service import (
    get_leaderboard, submit_prediction, get_user_predictions,
    get_all_predictions_for_round, check_deadline_passed,
    calculate_all_scores, effective_deadlines, match_deadline_passed,
    r32_early_date, SPLIT_ROUND, REST_KEY,
    submit_final_goals, get_final_test_data,
)
from backend.match_data.service import sync_matches
from backend.models import SessionLocal, RoundDeadline, Match, Prediction, User

prediction_bp = Blueprint('prediction', __name__)

# Global cooldown for user-triggered refresh (shared across all users)
_last_refresh = {'time': None}
REFRESH_COOLDOWN = 300  # 5 minutes

# Knockout bracket display order (top-to-bottom).
# Sorting a knockout round by external_id yields official match-number order.
# For most rounds that already matches the bracket tree, but the 2026 round of
# 16 joins the two sub-brackets non-sequentially: quarter-final "Match 98" is
# fed by R16 matches 93 & 94 (not 91 & 92), so the middle two R16 pairs must be
# swapped for each match to sit above the next-round match it actually feeds.
# Values are index positions into the external_id-sorted round.
BRACKET_ORDER = {
    'round_of_16': [0, 1, 4, 5, 2, 3, 6, 7],
}

def order_bracket(round_key, matches):
    """Return a knockout round's matches in top-to-bottom bracket order.

    Matches are first sorted by external_id (official match-number order);
    rounds listed in BRACKET_ORDER are then reordered so consecutive pairs feed
    the correct next-round match and the left/right halves stay consistent.
    """
    ordered = sorted(matches, key=lambda m: m.external_id)
    perm = BRACKET_ORDER.get(round_key)
    if perm and len(ordered) == len(perm):
        ordered = [ordered[i] for i in perm]
    return ordered

ROUNDS = [
    ('group_md1',   'Omgång 1'),
    ('group_md2',   'Omgång 2'),
    ('group_md3',   'Omgång 3'),
    ('round_of_32', 'Sextondelsfinal'),
    ('round_of_16', 'Åttondelsfinal'),
    ('quarter_final', 'Kvartsfinal'),
    ('semi_final',  'Semifinal'),
    ('third_place', 'Bronsmatch'),
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

    # Visibility — only reveal matches whose governing deadline has passed
    # (round_of_32 has a per-date split deadline, so check per match, not per round)
    eff_deadlines = effective_deadlines(db)
    early_date = r32_early_date(db)
    revealed_ids = {
        m.id for m in db.query(Match).all()
        if match_deadline_passed(m, eff_deadlines, early_date)
    }

    # Find all match days for navigation — only days with revealed matches
    all_match_dates_raw = [
        m.match_date for m in db.query(Match).filter(Match.id.in_(revealed_ids)).all()
    ] if revealed_ids else []
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

    day_matches = (
        db.query(Match)
        .filter(Match.match_date >= day_start_utc, Match.match_date < day_end_utc)
        .order_by(Match.match_date)
        .all()
    )
    matches = [m for m in day_matches if m.id in revealed_ids]
    # Matches today whose deadline hasn't passed yet (show without predictions)
    unlocked_matches = [m for m in day_matches if m.id not in revealed_ids]

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

    # Check if all today's matches (locked + unlocked) have finished
    all_day_matches = matches + unlocked_matches
    all_finished = len(all_day_matches) > 0 and all(m.finished for m in all_day_matches)

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
                           actual_today=actual_today,
                           unlocked_matches=unlocked_matches,
                           all_finished=all_finished)


@prediction_bp.route('/today/refresh', methods=['POST'])
def today_refresh():
    """User-triggered sync: fetch latest results from API and recalculate scores."""
    if not session.get('user_id'):
        return jsonify({'ok': False, 'msg': 'Not logged in'}), 401

    # Check if all today's matches are already finished — no need to call API
    db = SessionLocal()
    venue_now = datetime.now(timezone.utc) + timedelta(hours=-5)
    venue_today = venue_now.date()
    day_start_utc = datetime(venue_today.year, venue_today.month, venue_today.day, 5, 0, tzinfo=timezone.utc)
    day_end_utc = day_start_utc + timedelta(days=1)
    today_matches = db.query(Match).filter(
        Match.match_date >= day_start_utc, Match.match_date < day_end_utc
    ).all()
    db.close()
    if today_matches and all(m.finished for m in today_matches):
        return jsonify({'ok': True, 'msg': 'Alla matcher är redan klara!'})

    now = datetime.now(timezone.utc)

    # Global cooldown — one API call per 5 min across all users
    if _last_refresh['time']:
        elapsed = (now - _last_refresh['time']).total_seconds()
        if elapsed < REFRESH_COOLDOWN:
            remaining = int(REFRESH_COOLDOWN - elapsed)
            mins, secs = divmod(remaining, 60)
            wait = f'{mins}:{secs:02d}'
            return jsonify({'ok': True, 'msg': f'Uppdaterades nyligen. Försök igen om {wait}.'})

    _last_refresh['time'] = now
    result = sync_matches()
    if result.get('status') == 'success':
        calculate_all_scores()
        return jsonify({'ok': True, 'msg': 'Resultat uppdaterade!'})
    else:
        # Don't burn the cooldown on a failed call
        _last_refresh['time'] = None
        return jsonify({'ok': False, 'msg': 'Kunde inte hämta data. Försök igen senare.'})


@prediction_bp.route('/bracket')
def bracket():
    """Tournament bracket view for knockout stages"""
    db = SessionLocal()
    knockout_rounds = ['round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final']
    matches = (db.query(Match)
               .filter(Match.round.in_(knockout_rounds))
               .order_by(Match.external_id)
               .all())
    db.close()

    # Group matches by round, then sort each half by date
    BRACKET_HALF_SIZES = {
        'round_of_32': 8, 'round_of_16': 4,
        'quarter_final': 2, 'semi_final': 1,
    }
    by_round = {}
    for m in matches:
        by_round.setdefault(m.round, []).append(m)
    for rnd in list(by_round):
        # Order each round to match the bracket tree structure
        by_round[rnd] = order_bracket(rnd, by_round[rnd])

    return render_template('prediction/bracket.html', by_round=by_round)


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

    # Bracket half sizes: how many matches belong to the left side
    BRACKET_HALF = {
        'round_of_32': 8,
        'round_of_16': 4,
        'quarter_final': 2,
        'semi_final': 1,
    }

    # round_of_32 split deadline: earliest match date vs the rest
    r32_dates = sorted(m.match_date for m in all_matches if m.round == SPLIT_ROUND)
    r32_early_date = r32_dates[0].date() if r32_dates else None
    r32_early_dl_obj = deadlines.get(SPLIT_ROUND)
    r32_early_dl = r32_early_dl_obj.deadline if r32_early_dl_obj else (r32_dates[0] if r32_dates else None)
    r32_rest_dates = [d for d in r32_dates if d.date() != r32_early_date]
    r32_rest_dl = r32_rest_dates[0] if r32_rest_dates else None

    # Group matches by round
    rounds_data = []
    for round_key, round_label in ROUNDS:
        round_matches = [m for m in all_matches if m.round == round_key]
        # For group stage: sort by group then date so group headers render correctly
        if round_key.startswith('group_'):
            round_matches.sort(key=lambda m: (m.group or '', m.match_date))
        is_knockout = round_key in BRACKET_HALF
        if is_knockout:
            # Order to match the bracket tree so each pair feeds the next round
            # (R32[0,1]→R16[0], R32[2,3]→R16[1], etc.)
            round_matches = order_bracket(round_key, round_matches)
            half = BRACKET_HALF[round_key]
            # Tag each match with its bracket side
            for i, m in enumerate(round_matches):
                m._bracket_side = 'left' if i < half else 'right'
        deadline = deadlines.get(round_key)

        # round_of_32: two deadlines — earliest date vs the rest
        splits = None
        if round_key == SPLIT_ROUND and r32_early_date:
            now = datetime.utcnow()
            early_matches = sorted((m for m in round_matches if m.match_date.date() == r32_early_date),
                                   key=lambda m: m.match_date)
            rest_matches = sorted((m for m in round_matches if m.match_date.date() != r32_early_date),
                                  key=lambda m: m.match_date)
            splits = [
                {'label': 'Första dagen', 'deadline_dt': r32_early_dl,
                 'locked': bool(r32_early_dl and now > r32_early_dl), 'matches': early_matches},
            ]
            if rest_matches:
                splits.append(
                    {'label': 'Övriga matcher', 'deadline_dt': r32_rest_dl,
                     'locked': bool(r32_rest_dl and now > r32_rest_dl), 'matches': rest_matches})

        round_locked = (all(s['locked'] for s in splits) if splits
                        else (deadline.is_past() if deadline else False))
        rounds_data.append({
            'key': round_key,
            'label': round_label,
            'matches': round_matches,
            'deadline': deadline,
            'locked': round_locked,
            'is_knockout': is_knockout,
            'splits': splits,
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


@prediction_bp.route('/test-final', methods=['GET', 'POST'])
def test_final():
    """Test page: bet on the final by exact goals.

    Experimental scoring — 1 point for the correct number of home goals, 1 for the
    correct number of away goals, and 1 for the resulting 1X2 (max 3). Isolated
    from the live 1X2 competition and its leaderboard.
    """
    if not session.get('user_id'):
        flash('Please login first.')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        result = submit_final_goals(
            session['user_id'],
            request.form.get('home_goals'),
            request.form.get('away_goals'),
        )
        flash(result['message'], 'error' if result['status'] == 'error' else 'success')
        return redirect(url_for('prediction.test_final'))

    calculate_all_scores()
    data = get_final_test_data()

    # This user's current goal prediction (to prefill the form)
    my_row = next((r for r in data['rows'] if r['user'].id == session['user_id']), None)

    return render_template('prediction/test_final.html',
                           match=data['match'],
                           rows=data['rows'],
                           my_row=my_row)


@prediction_bp.route('/results')
def results():
    if not session.get('user_id'):
        flash('Please login to view results.')
        return redirect(url_for('auth.login'))

    calculate_all_scores()
    db = SessionLocal()
    from backend.models import Match, Prediction, User
    from sqlalchemy.orm import joinedload

    # Only include matches whose governing deadline has passed
    # (round_of_32 uses a per-date split deadline — check per match, not per round)
    eff_deadlines = effective_deadlines(db)
    early_date = r32_early_date(db)
    visible_matches = [
        m for m in db.query(Match).order_by(Match.match_date).all()
        if match_deadline_passed(m, eff_deadlines, early_date)
    ]

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

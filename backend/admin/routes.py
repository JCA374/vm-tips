"""Admin routes - User management, deadlines, system status, backups"""
import json
import os
import shutil
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, abort, jsonify, send_file
from functools import wraps
from datetime import datetime
from backend.models import User, Match, Prediction, RoundDeadline, Invite, ActivityLog, SessionLocal
from backend.match_data.service import sync_matches, update_match_results
from backend.prediction.service import calculate_all_scores
from backend import config

admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    """Decorator to require admin access — returns 404 to non-admins so the page appears not to exist"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('user_email') != config.ADMIN_EMAIL:
            abort(404)
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@require_admin
def index():
    """Admin dashboard with live stats"""
    db = SessionLocal()

    user_count = db.query(User).count()
    match_count = db.query(Match).count()
    finished_count = db.query(Match).filter_by(finished=True).count()
    prediction_count = db.query(Prediction).count()

    # Points awarded so far
    from sqlalchemy import func
    total_points = db.query(func.sum(Prediction.points)).scalar() or 0

    # Users who haven't made any predictions
    users_with_preds = db.query(Prediction.user_id).distinct().subquery()
    from sqlalchemy import not_
    silent_users = db.query(User).filter(not_(User.id.in_(users_with_preds))).all()

    # Recent predictions (last 10)
    recent = (db.query(Prediction, User, Match)
              .join(User, Prediction.user_id == User.id)
              .join(Match, Prediction.match_id == Match.id)
              .order_by(Prediction.updated_at.desc())
              .limit(10)
              .all())

    db.close()

    stats = {
        'users': user_count,
        'matches': match_count,
        'finished': finished_count,
        'predictions': prediction_count,
        'total_points': total_points,
    }

    return render_template('admin/dashboard.html',
                           stats=stats,
                           silent_users=silent_users,
                           recent=recent)


@admin_bp.route('/users')
@require_admin
def users():
    """User management with prediction counts and scores"""
    db = SessionLocal()

    from sqlalchemy import func
    # Join prediction counts and total points per user
    rows = (db.query(
                User,
                func.count(Prediction.id).label('pred_count'),
                func.sum(Prediction.points).label('total_points')
            )
            .outerjoin(Prediction, Prediction.user_id == User.id)
            .group_by(User.id)
            .order_by(func.sum(Prediction.points).desc().nullslast())
            .all())

    db.close()
    return render_template('admin/users.html', rows=rows)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@require_admin
def delete_user(user_id):
    db = SessionLocal()
    user = db.query(User).get(user_id)
    if not user:
        db.close()
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))
    if user.email == config.ADMIN_EMAIL:
        db.close()
        flash('Cannot delete the admin account.', 'error')
        return redirect(url_for('admin.users'))
    db.delete(user)
    db.commit()
    db.close()
    flash(f'Deleted user {user.name} ({user.email}).')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/toggle-admin', methods=['POST'])
@require_admin
def toggle_admin(user_id):
    db = SessionLocal()
    user = db.query(User).get(user_id)
    if not user:
        db.close()
        flash('User not found.', 'error')
        return redirect(url_for('admin.users'))
    user.is_admin = not user.is_admin
    db.commit()
    db.close()
    flash(f'{"Granted" if user.is_admin else "Removed"} admin for {user.name}.')
    return redirect(url_for('admin.users'))


@admin_bp.route('/deadlines', methods=['GET', 'POST'])
@require_admin
def deadlines():
    """Manage round deadlines"""
    db = SessionLocal()

    if request.method == 'POST':
        rounds = ['group_md1', 'group_md2', 'group_md3', 'round_of_32', 'round_of_16', 'quarter_final', 'semi_final', 'third_place', 'final']

        for round_name in rounds:
            deadline_str = request.form.get(round_name)
            if deadline_str:
                deadline_dt = datetime.fromisoformat(deadline_str)
                existing = db.query(RoundDeadline).filter_by(round=round_name).first()
                if existing:
                    existing.deadline = deadline_dt
                    existing.updated_at = datetime.utcnow()
                else:
                    db.add(RoundDeadline(round=round_name, deadline=deadline_dt))

        db.commit()
        flash('Deadlines updated!')
        db.close()
        return redirect(url_for('admin.deadlines'))

    existing_deadlines = db.query(RoundDeadline).all()
    deadline_dict = {d.round: d.deadline.strftime('%Y-%m-%dT%H:%M') for d in existing_deadlines}
    db.close()

    return render_template('admin/deadlines.html',
                           deadlines=deadline_dict,
                           existing_deadlines=existing_deadlines)


@admin_bp.route('/status')
@require_admin
def status():
    """System status — matches, sync, score calculation"""
    db = SessionLocal()

    from sqlalchemy import func
    stats = {
        'users': db.query(User).count(),
        'matches': db.query(Match).count(),
        'finished': db.query(Match).filter_by(finished=True).count(),
        'predictions': db.query(Prediction).count(),
    }

    matches = (db.query(Match)
               .order_by(Match.match_date.asc())
               .all())

    # Prediction count per match
    pred_counts = dict(
        db.query(Prediction.match_id, func.count(Prediction.id))
        .group_by(Prediction.match_id)
        .all()
    )

    db.close()
    return render_template('admin/status.html', stats=stats, matches=matches, pred_counts=pred_counts)


@admin_bp.route('/activity')
@require_admin
def activity():
    """Activity log — who is viewing what and when"""
    from sqlalchemy import func, desc

    db = SessionLocal()

    # Recent page views (last 100, skip bot/static noise and login redirects)
    recent_views = (db.query(ActivityLog, User)
                    .outerjoin(User, ActivityLog.user_id == User.id)
                    .filter(ActivityLog.method == 'GET')
                    .filter(ActivityLog.status_code < 400)
                    .filter(ActivityLog.user_id.isnot(None))
                    .order_by(ActivityLog.timestamp.desc())
                    .limit(100)
                    .all())

    # Active users today
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    active_today = (db.query(User)
                    .filter(User.last_active_at >= today_start)
                    .order_by(User.last_active_at.desc())
                    .all())

    # Most visited pages (last 24h)
    from datetime import timedelta as td
    since_24h = datetime.utcnow() - td(hours=24)
    popular_pages = (db.query(ActivityLog.path, func.count(ActivityLog.id).label('hits'))
                     .filter(ActivityLog.timestamp >= since_24h)
                     .filter(ActivityLog.method == 'GET')
                     .filter(ActivityLog.user_id.isnot(None))
                     .group_by(ActivityLog.path)
                     .order_by(desc('hits'))
                     .limit(15)
                     .all())

    # Activity per user (last 24h)
    user_activity = (db.query(User.name, func.count(ActivityLog.id).label('views'))
                     .join(ActivityLog, ActivityLog.user_id == User.id)
                     .filter(ActivityLog.timestamp >= since_24h)
                     .filter(ActivityLog.method == 'GET')
                     .group_by(User.id)
                     .order_by(desc('views'))
                     .all())

    db.close()
    return render_template('admin/activity.html',
                           recent_views=recent_views,
                           active_today=active_today,
                           popular_pages=popular_pages,
                           user_activity=user_activity)


@admin_bp.route('/reminders')
@require_admin
def reminders():
    """Log of all reminder emails sent"""
    from pathlib import Path
    history_path = Path(__file__).parent.parent.parent / 'data' / 'reminder_history.json'
    entries = []
    if history_path.exists():
        try:
            entries = json.loads(history_path.read_text())
        except Exception:
            pass
    # Show newest first
    entries.reverse()
    return render_template('admin/reminders.html', entries=entries)


@admin_bp.route('/sync-matches', methods=['POST'])
@require_admin
def sync_matches_route():
    result = sync_matches()
    if result['status'] == 'success':
        scores = calculate_all_scores()
        flash(f"Synced {result['synced']} new, updated {result['updated']} matches. Scores: {scores.get('updated', 0)} predictions recalculated.")
    else:
        flash(f"Error syncing matches: {result.get('message', 'Unknown error')}", 'error')
    return redirect(url_for('admin.status'))


@admin_bp.route('/calculate-scores', methods=['POST'])
@require_admin
def calculate_scores_route():
    update_match_results()
    result = calculate_all_scores()
    if result['status'] == 'success':
        flash(f"Calculated scores for {result['updated']} predictions.")
    else:
        flash(f"Error calculating scores: {result.get('message', 'Unknown error')}", 'error')
    return redirect(url_for('admin.status'))


# ---------------------------------------------------------------------------
# Backup / Restore
# ---------------------------------------------------------------------------

@admin_bp.route('/backup')
@require_admin
def backup():
    """Backup overview page"""
    db = SessionLocal()
    prediction_count = db.query(Prediction).count()
    user_count = db.query(User).count()
    db.close()

    db_path = config.DATABASE_PATH
    db_size_kb = round(os.path.getsize(str(db_path)) / 1024, 1) if os.path.exists(str(db_path)) else 0

    return render_template('admin/backup.html',
                           prediction_count=prediction_count,
                           user_count=user_count,
                           db_size_kb=db_size_kb)


@admin_bp.route('/backup/export-json')
@require_admin
def export_json():
    """Export all predictions + users as a downloadable JSON file"""
    db = SessionLocal()

    users = db.query(User).all()
    predictions = (db.query(Prediction, Match)
                   .join(Match, Prediction.match_id == Match.id)
                   .all())

    data = {
        'exported_at': datetime.utcnow().isoformat(),
        'users': [
            {
                'id': u.id,
                'email': u.email,
                'name': u.name,
                'is_admin': u.is_admin,
                'created_at': u.created_at.isoformat(),
            }
            for u in users
        ],
        'predictions': [
            {
                'user_email': p.user.email,
                'match_external_id': m.external_id,
                'home_team': m.home_team,
                'away_team': m.away_team,
                'round': m.round,
                'match_date': m.match_date.isoformat(),
                'predicted_outcome': p.predicted_outcome,
                'predicted_home_goals': p.predicted_home_goals,
                'predicted_away_goals': p.predicted_away_goals,
                'points': p.points,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat(),
            }
            for p, m in predictions
        ],
    }

    db.close()

    filename = f"vm_backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    import tempfile
    tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False)
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    return send_file(tmp.name, as_attachment=True, download_name=filename, mimetype='application/json')


@admin_bp.route('/backup/download-db')
@require_admin
def download_db():
    """Download the raw SQLite database file"""
    db_path = str(config.DATABASE_PATH)
    if not os.path.exists(db_path):
        flash('Database file not found.', 'error')
        return redirect(url_for('admin.backup'))
    filename = f"vm_tips_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.db"
    return send_file(db_path, as_attachment=True, download_name=filename)


@admin_bp.route('/backup/restore', methods=['POST'])
@require_admin
def restore_json():
    """Restore predictions from an uploaded JSON backup file"""
    f = request.files.get('backup_file')
    if not f or not f.filename.endswith('.json'):
        flash('Please upload a valid .json backup file.', 'error')
        return redirect(url_for('admin.backup'))

    try:
        data = json.load(f)
    except Exception:
        flash('Could not parse JSON file.', 'error')
        return redirect(url_for('admin.backup'))

    db = SessionLocal()
    restored = 0
    skipped = 0

    for entry in data.get('predictions', []):
        user = db.query(User).filter_by(email=entry['user_email']).first()
        match = db.query(Match).filter_by(external_id=entry['match_external_id']).first()

        if not user or not match:
            skipped += 1
            continue

        pred = (db.query(Prediction)
                .filter_by(user_id=user.id, match_id=match.id)
                .first())

        if pred:
            # Overwrite existing prediction
            pred.predicted_outcome = entry.get('predicted_outcome')
            pred.predicted_home_goals = entry.get('predicted_home_goals')
            pred.predicted_away_goals = entry.get('predicted_away_goals')
            pred.points = entry.get('points')
        else:
            pred = Prediction(
                user_id=user.id,
                match_id=match.id,
                predicted_outcome=entry.get('predicted_outcome'),
                predicted_home_goals=entry.get('predicted_home_goals'),
                predicted_away_goals=entry.get('predicted_away_goals'),
                points=entry.get('points'),
            )
            db.add(pred)

        restored += 1

    db.commit()
    db.close()

    flash(f'Restored {restored} predictions. Skipped {skipped} (user or match not found).')
    return redirect(url_for('admin.backup'))

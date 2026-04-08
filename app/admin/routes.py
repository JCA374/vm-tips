"""Admin routes - User management, deadlines, system status"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from database.models import User, Match, Prediction, RoundDeadline, SessionLocal
from app.match_data.service import sync_matches, update_match_results
from app.prediction.service import calculate_all_scores

admin_bp = Blueprint('admin', __name__)


def require_admin(f):
    """Decorator to require admin access"""
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            flash('Admin access required.')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function


@admin_bp.route('/')
@require_admin
def index():
    """Admin dashboard"""
    return render_template('admin/dashboard.html')


@admin_bp.route('/users')
@require_admin
def users():
    """User management"""
    db = SessionLocal()
    all_users = db.query(User).all()
    db.close()
    return render_template('admin/users.html', users=all_users)


@admin_bp.route('/deadlines', methods=['GET', 'POST'])
@require_admin
def deadlines():
    """Manage round deadlines"""
    db = SessionLocal()

    if request.method == 'POST':
        # Update deadlines
        rounds = ['round_of_16', 'quarter_final', 'semi_final', 'final']

        for round_name in rounds:
            deadline_str = request.form.get(round_name)
            if deadline_str:
                deadline_dt = datetime.fromisoformat(deadline_str)

                existing = db.query(RoundDeadline).filter_by(round=round_name).first()
                if existing:
                    existing.deadline = deadline_dt
                    existing.updated_at = datetime.utcnow()
                else:
                    new_deadline = RoundDeadline(round=round_name, deadline=deadline_dt)
                    db.add(new_deadline)

        db.commit()
        flash('Deadlines updated!')
        db.close()
        return redirect(url_for('admin.deadlines'))

    # Get existing deadlines
    existing_deadlines = db.query(RoundDeadline).all()

    # Format for form
    deadline_dict = {}
    for d in existing_deadlines:
        deadline_dict[d.round] = d.deadline.strftime('%Y-%m-%dT%H:%M')

    db.close()

    return render_template('admin/deadlines.html',
                          deadlines=deadline_dict,
                          existing_deadlines=existing_deadlines)


@admin_bp.route('/status')
@require_admin
def status():
    """System status and match data sync"""
    db = SessionLocal()

    # Get database stats
    stats = {
        'users': db.query(User).count(),
        'matches': db.query(Match).count(),
        'predictions': db.query(Prediction).count()
    }

    db.close()

    return render_template('admin/status.html', stats=stats)


@admin_bp.route('/sync-matches', methods=['POST'])
@require_admin
def sync_matches_route():
    """Manually trigger match sync"""
    result = sync_matches()

    if result['status'] == 'success':
        flash(f"Synced {result['synced']} new matches, updated {result['updated']} matches.")
    else:
        flash(f"Error syncing matches: {result.get('message', 'Unknown error')}", 'error')

    return redirect(url_for('admin.status'))


@admin_bp.route('/calculate-scores', methods=['POST'])
@require_admin
def calculate_scores_route():
    """Manually trigger score calculation"""
    # First update match results
    update_match_results()

    # Then calculate scores
    result = calculate_all_scores()

    if result['status'] == 'success':
        flash(f"Calculated scores for {result['updated']} predictions.")
    else:
        flash(f"Error calculating scores: {result.get('message', 'Unknown error')}", 'error')

    return redirect(url_for('admin.status'))

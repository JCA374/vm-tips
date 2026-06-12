"""Cron job: send reminder emails 24h before round deadlines.

Only emails users who have missing predictions for that round.
In demo mode (REMINDER_DEMO=1), only sends to ADMIN_EMAIL.

Suggested crontab (runs every hour, only sends when 24h window matches):
  0 * * * * docker exec vm-tips-web-1 python cron_reminder.py >> /var/log/vm_reminder.log 2>&1

Usage:
  python cron_reminder.py              # normal mode
  REMINDER_DEMO=1 python cron_reminder.py   # demo: only sends to admin
  REMINDER_SEND_NOW=1 python cron_reminder.py  # ignore 24h window, send now
"""
import os
import sys
from datetime import datetime, timezone, timedelta

if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'vm_tips.db')

from backend import config
from backend.models import SessionLocal, User, Match, Prediction, RoundDeadline
from backend.auth.service import _brevo_send

DEMO_MODE = os.getenv('REMINDER_DEMO', '').strip() == '1'
SEND_NOW = os.getenv('REMINDER_SEND_NOW', '').strip() == '1'

ROUND_LABELS = {
    'group_md1': 'Omgång 1',
    'group_md2': 'Omgång 2',
    'group_md3': 'Omgång 3',
    'round_of_32': 'Åttondelsfinal',
    'round_of_16': 'Sextondelsfinal',
    'quarter_final': 'Kvartsfinal',
    'semi_final': 'Semifinal',
    'third_place': 'Match om tredje pris',
    'final': 'Final',
}


def get_missing_predictions(db, round_name):
    """Return list of (user, [missing_matches]) for users with incomplete predictions."""
    matches = (
        db.query(Match)
        .filter(Match.round == round_name, Match.home_team != 'TBD')
        .order_by(Match.match_date)
        .all()
    )
    if not matches:
        return []

    match_ids = [m.id for m in matches]
    users = db.query(User).all()

    # Get all predictions for this round
    preds = (
        db.query(Prediction)
        .filter(Prediction.match_id.in_(match_ids))
        .all()
    )
    pred_map = {}  # (user_id, match_id) -> prediction
    for p in preds:
        pred_map[(p.user_id, p.match_id)] = p

    results = []
    for user in users:
        missing = []
        for match in matches:
            pred = pred_map.get((user.id, match.id))
            if not pred or not pred.predicted_outcome:
                missing.append(match)
        if missing:
            results.append((user, missing))

    return results


def build_email_html(user_name, round_label, deadline_str, missing_matches):
    matches_html = ''
    for m in missing_matches:
        local_time = m.match_date.strftime('%d/%m %H:%M')
        matches_html += f'<li><strong>{m.home_team} vs {m.away_team}</strong> — {local_time} UTC</li>\n'

    return f"""
<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
    <div style="background: #0A1C2E; color: white; padding: 16px 20px; border-radius: 8px 8px 0 0; text-align: center;">
        <span style="font-size: 24px;">⚽</span>
        <span style="font-size: 18px; font-weight: 700; margin-left: 8px;">VM Tips 2026</span>
    </div>
    <div style="background: #f8f9fa; padding: 24px 20px; border: 1px solid #ddd; border-top: none; border-radius: 0 0 8px 8px;">
        <p style="font-size: 16px; margin: 0 0 12px;">Hej <strong>{user_name}</strong>!</p>
        <p style="font-size: 15px; color: #333; margin: 0 0 16px;">
            Deadline för <strong>{round_label}</strong> är snart —
            <strong>{deadline_str}</strong>.
        </p>
        <p style="font-size: 15px; color: #c0392b; margin: 0 0 12px;">
            Du saknar tips för {len(missing_matches)} {'match' if len(missing_matches) == 1 else 'matcher'}:
        </p>
        <ul style="font-size: 14px; color: #333; padding-left: 20px; margin: 0 0 20px;">
            {matches_html}
        </ul>
        <div style="text-align: center; margin: 24px 0 8px;">
            <a href="{config.APP_URL}/predict"
               style="display: inline-block; padding: 12px 32px; background: #1565C0; color: white;
                      text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 16px;">
                Tippa nu
            </a>
        </div>
        <p style="font-size: 12px; color: #999; margin-top: 20px; text-align: center;">
            Du får detta mail för att du är med i Stora Hults VM-tipsning.
        </p>
    </div>
</div>
"""


def main():
    now = datetime.now(timezone.utc)
    print(f'[{now.strftime("%Y-%m-%d %H:%M UTC")}] Checking deadlines...')

    db = SessionLocal()
    deadlines = db.query(RoundDeadline).all()

    sent_total = 0

    for dl in deadlines:
        # Make deadline timezone-aware for comparison
        deadline_utc = dl.deadline.replace(tzinfo=timezone.utc)
        hours_until = (deadline_utc - now).total_seconds() / 3600

        # Send if deadline is 23-25 hours away (1 hour window to avoid duplicates)
        # Or if SEND_NOW is set and deadline hasn't passed yet
        if SEND_NOW:
            if deadline_utc < now:
                continue  # skip past deadlines
        else:
            if hours_until < 23 or hours_until > 25:
                continue

        round_label = ROUND_LABELS.get(dl.round, dl.round)
        deadline_str = deadline_utc.strftime('%Y-%m-%d %H:%M UTC')

        print(f'  Round: {round_label} (deadline: {deadline_str}, {hours_until:.1f}h away)')

        missing = get_missing_predictions(db, dl.round)
        if not missing:
            print(f'    Everyone has predicted! No emails needed.')
            continue

        for user, missing_matches in missing:
            to_email = user.email
            to_name = user.name

            if DEMO_MODE:
                to_email = config.ADMIN_EMAIL or 'jonca374@gmail.com'
                to_name = f'{user.name} [DEMO]'

            html = build_email_html(user.name, round_label, deadline_str, missing_matches)
            subject = f'⚽ Glöm inte tippa {round_label}! ({len(missing_matches)} matcher kvar)'

            try:
                _brevo_send(to_email, to_name, subject, html)
                print(f'    Sent to {to_email} ({user.name}): {len(missing_matches)} missing')
                sent_total += 1
            except Exception as e:
                print(f'    FAILED {to_email}: {e}')

            if DEMO_MODE:
                print(f'    (DEMO: would send to {user.email}, redirected to {to_email})')
                break  # Only send one in demo mode

    db.close()
    print(f'  Done. Sent {sent_total} emails.')


if __name__ == '__main__':
    main()

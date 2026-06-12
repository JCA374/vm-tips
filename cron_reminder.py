"""Cron job: send reminder emails 24h before round deadlines.

Only emails users who have missing predictions for that round.
Each user gets MAX ONE email per round (tracked in a sent-log file).
In demo mode (REMINDER_DEMO=1), only sends to ADMIN_EMAIL.

Suggested crontab (runs every hour, only sends when 24h window matches):
  0 * * * * docker exec vm-tips-web-1 python cron_reminder.py >> /var/log/vm_reminder.log 2>&1

Usage:
  python cron_reminder.py              # normal mode
  REMINDER_DEMO=1 python cron_reminder.py   # demo: only sends to admin
  REMINDER_SEND_NOW=1 python cron_reminder.py  # ignore 24h window, send now
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'vm_tips.db')

from backend import config
from backend.models import SessionLocal, User, Match, Prediction, RoundDeadline
from backend.auth.service import _brevo_send

DEMO_MODE = os.getenv('REMINDER_DEMO', '').strip() == '1'
SEND_NOW = os.getenv('REMINDER_SEND_NOW', '').strip() == '1'

# Track which (round, user_email) combos we already sent
SENT_LOG = Path(__file__).parent / 'data' / 'reminders_sent.json'

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


def load_sent_log():
    """Load set of 'round:email' strings already sent."""
    if SENT_LOG.exists():
        try:
            return set(json.loads(SENT_LOG.read_text()))
        except Exception:
            return set()
    return set()


def save_sent_log(sent_set):
    SENT_LOG.write_text(json.dumps(sorted(sent_set)))


def get_missing_predictions(db, round_name):
    """Return list of (user, missing_count) for users with incomplete predictions."""
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

    preds = (
        db.query(Prediction)
        .filter(Prediction.match_id.in_(match_ids))
        .all()
    )
    pred_map = {}
    for p in preds:
        pred_map[(p.user_id, p.match_id)] = p

    results = []
    for user in users:
        missing = 0
        for match in matches:
            pred = pred_map.get((user.id, match.id))
            if not pred or not pred.predicted_outcome:
                missing += 1
        if missing > 0:
            results.append((user, missing))

    return results


def build_email_html(user_name, round_label, deadline_str, missing_count):
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
        <p style="font-size: 15px; color: #c0392b; margin: 0 0 20px;">
            Du saknar tips för {missing_count} {'match' if missing_count == 1 else 'matcher'}.
        </p>
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
    sent_log = load_sent_log()

    sent_total = 0

    for dl in deadlines:
        deadline_utc = dl.deadline.replace(tzinfo=timezone.utc)
        hours_until = (deadline_utc - now).total_seconds() / 3600

        # Send if deadline is 23-25 hours away (2h window)
        # Or if SEND_NOW is set and deadline hasn't passed yet
        if SEND_NOW:
            if deadline_utc < now:
                continue
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

        for user, missing_count in missing:
            # Check if already sent for this round + user
            log_key = f'{dl.round}:{user.email}'
            if log_key in sent_log and not DEMO_MODE:
                print(f'    Skip {user.email} ({user.name}): already sent')
                continue

            to_email = user.email
            to_name = user.name

            if DEMO_MODE:
                to_email = config.ADMIN_EMAIL or 'jonca374@gmail.com'
                to_name = f'{user.name} [DEMO]'

            html = build_email_html(user.name, round_label, deadline_str, missing_count)
            subject = f'⚽ Glöm inte tippa {round_label}! ({missing_count} matcher kvar)'

            try:
                _brevo_send(to_email, to_name, subject, html)
                print(f'    Sent to {to_email} ({user.name}): {missing_count} missing')
                sent_total += 1

                # Mark as sent (use real email, not demo redirect)
                sent_log.add(f'{dl.round}:{user.email}')

            except Exception as e:
                print(f'    FAILED {to_email}: {e}')

            if DEMO_MODE:
                print(f'    (DEMO: would send to {user.email}, redirected to {to_email})')
                break

    save_sent_log(sent_log)
    db.close()
    print(f'  Done. Sent {sent_total} emails.')


if __name__ == '__main__':
    main()

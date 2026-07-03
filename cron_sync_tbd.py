"""Cron job: fill in TBD team names for upcoming matches.

As knockout rounds progress, the API populates the next round's fixtures with
real team names once both sides are decided. This job pulls those names into
matches we still have stored as 'TBD'.

One API call per run (all matches in one request). Safe to run every few hours.

Suggested crontab (runs every 6 hours):
  0 */6 * * *  cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync_tbd.py >> /var/log/vm_sync_tbd.log 2>&1
"""
import os
from datetime import datetime, timezone

# Use production database by default
if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'vm_tips.db')

from backend.match_data.service import sync_tbd_teams


def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'[{now}] Syncing TBD teams...')

    result = sync_tbd_teams()
    print(f'  Result: {result}')
    print('  Done.')


if __name__ == '__main__':
    main()

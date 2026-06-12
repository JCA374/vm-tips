"""Cron job: sync match results from football-data.org and recalculate points.

One API call per run (all matches in one request). Safe to run frequently.

Suggested crontab (Swedish time, CEST = UTC+2):
  # After evening matches (21:00 kick-off → done ~23:00)
  0 23 * * *   cd /home/jonas/Code/sport/vm && /home/jonas/Code/sport/vm/venv/bin/python cron_sync.py >> /var/log/vm_sync.log 2>&1
  # After night matches (00:00-01:00 kick-off → done ~03:00)
  0 3 * * *    cd /home/jonas/Code/sport/vm && /home/jonas/Code/sport/vm/venv/bin/python cron_sync.py >> /var/log/vm_sync.log 2>&1
  # After early morning matches (03:00-04:00 kick-off → done ~06:00)
  30 6 * * *   cd /home/jonas/Code/sport/vm && /home/jonas/Code/sport/vm/venv/bin/python cron_sync.py >> /var/log/vm_sync.log 2>&1
  # Extra pass to catch stragglers
  30 7 * * *   cd /home/jonas/Code/sport/vm && /home/jonas/Code/sport/vm/venv/bin/python cron_sync.py >> /var/log/vm_sync.log 2>&1
"""
import os
import sys
from datetime import datetime, timezone

# Use production database by default
if 'DATABASE_PATH' not in os.environ:
    os.environ['DATABASE_PATH'] = os.path.join(os.path.dirname(__file__), 'data', 'vm_tips.db')

from backend.match_data.service import sync_matches
from backend.prediction.service import calculate_all_scores


def main():
    now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f'[{now}] Starting sync...')

    result = sync_matches()
    print(f'  Sync: {result}')

    if result.get('status') == 'success':
        scores = calculate_all_scores()
        print(f'  Scores: {scores}')
    else:
        print('  Skipping score calculation due to sync error')

    print(f'  Done.')


if __name__ == '__main__':
    main()

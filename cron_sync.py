"""Cron job: sync match results from football-data.org and recalculate points.

One API call per run (all matches in one request). Safe to run frequently.

WC 2026 is in USA/Canada/Mexico. Late games can kick off 21:00 ET (03:00 CEST)
and finish ~05:00 CEST. The API sometimes needs 1-2 hours to report FINISHED.
Extra morning syncs ensure results are captured before people check the app.

Suggested crontab (server runs UTC; CEST = UTC+2):
  # After evening matches (21:00 CEST kick-off → done ~23:00)
  0 21 * * *   cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
  # After night matches (00:00-01:00 CEST kick-off → done ~03:00)
  0 1 * * *    cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
  # Morning catch-up syncs at CEST 06:00, 07:00, 07:30, 08:00 (UTC 04:00, 05:00, 05:30, 06:00)
  0 4 * * *    cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
  0 5 * * *    cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
  30 5 * * *   cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
  0 6 * * *    cd /opt/vm-tips && docker exec vm-tips-web-1 python cron_sync.py >> /var/log/vm_sync.log 2>&1
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
        if result.get('updated', 0) > 0 or result.get('synced', 0) > 0:
            scores = calculate_all_scores()
            print(f'  Scores: {scores}')
        else:
            print('  No changes, skipping score calculation')
    else:
        print('  Skipping score calculation due to sync error')

    print(f'  Done.')


if __name__ == '__main__':
    main()

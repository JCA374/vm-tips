#!/bin/bash
# Deploy code to production server.
# SAFE: excludes data/, .env, and non-code files to protect the live database.

set -euo pipefail

# Auto-commit any uncommitted changes before deploying
if ! git diff --quiet HEAD 2>/dev/null; then
  echo "Uncommitted changes detected — committing before deploy..."
  git add -A
  git commit -m "auto-save before deploy $(date +%Y-%m-%d_%H:%M)"
  echo ""
fi

SERVER="root@178.128.254.166"
REMOTE_DIR="/opt/vm-tips/"
DB_PATH="${REMOTE_DIR}data/vm_tips.db"

# Create restore point before deploying
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="${REMOTE_DIR}data/vm_tips_backup_${TIMESTAMP}.db"
echo "Creating restore point: $BACKUP_PATH ..."
ssh "$SERVER" "cp $DB_PATH $BACKUP_PATH"
echo "Restore point created."

echo ""
echo "Deploying to $SERVER:$REMOTE_DIR ..."

rsync -avz \
  --exclude='.git' \
  --exclude='venv' \
  --exclude='__pycache__' \
  --exclude='.env' \
  --exclude='data/' \
  --exclude='database/' \
  --exclude='playwright/' \
  --exclude='design/' \
  --exclude='*.db' \
  --exclude='*.sqlite3' \
  --exclude='.claude/' \
  /home/jonas/Code/sport/vm/ "$SERVER:$REMOTE_DIR"

echo "Rebuilding container..."
ssh "$SERVER" "cd $REMOTE_DIR && docker compose down && docker compose up -d --build"

echo "Deploy complete. Checking logs..."
ssh "$SERVER" "docker compose -f ${REMOTE_DIR}docker-compose.yml logs --tail=5"

#!/bin/bash
#
# Weekly Obscuriboxd DB refresh + deploy.
# Runs refresh_db.py (which must run on a residential IP - Letterboxd blocks datacenter/CI IPs),
# then commits and pushes films_complete.db.gz so Render auto-deploys the fresh database.
#
# Wired up to run weekly via launchd (see com.obscuriboxd.weekly-refresh.plist).
# Set OBSCURIBOXD_AUTO_PUSH=0 to build/commit locally without pushing.

set -euo pipefail

BACKEND_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BACKEND_DIR"

LOG_DIR="$BACKEND_DIR/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/refresh_$(date +%Y%m%d_%H%M%S).log"

AUTO_PUSH="${OBSCURIBOXD_AUTO_PUSH:-1}"
PYTHON="$BACKEND_DIR/venv/bin/python"

{
  echo "===== Obscuriboxd weekly refresh $(date) ====="

  "$PYTHON" refresh_db.py --recent-years 1 --popular-pages 30

  if [ "$AUTO_PUSH" = "1" ]; then
    if ! git diff --quiet -- films_complete.db.gz; then
      echo "Changes detected in films_complete.db.gz - committing and pushing..."
      git add films_complete.db.gz
      git commit -m "chore: weekly database refresh ($(date +%Y-%m-%d))"
      git push
      echo "Pushed. Render will redeploy with the fresh database."
    else
      echo "No changes in films_complete.db.gz - nothing to push."
    fi
  else
    echo "OBSCURIBOXD_AUTO_PUSH=0 - skipping git push. Commit/push manually to deploy."
  fi

  echo "===== Done $(date) ====="
} 2>&1 | tee "$LOG_FILE"

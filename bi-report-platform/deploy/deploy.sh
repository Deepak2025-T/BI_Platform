#!/usr/bin/env bash
#
# The server side of a deploy, run over SSH by .github/workflows/deploy.yml as the deploy user.
#
#   deploy.sh snapshot   keep a copy of what is running now, so a bad release can be undone
#   deploy.sh release    install dependencies, migrate, restart, and check it answers
#   deploy.sh rollback   put the snapshot back and restart
#
# Kept as three steps because the files arrive between the first two: CI snapshots, rsyncs the
# new build in, then releases. If the release does not come up, CI rolls back and goes red.
set -euo pipefail

APP_DIR=/opt/ReportAI
PREV_DIR=$APP_DIR/previous
VENV=$APP_DIR/.venv
HEALTH=http://127.0.0.1:8000/api/health

say() { printf '\n== %s\n' "$1"; }

# Waits for the API to answer rather than guessing at a sleep. uvicorn is listening within a
# second or two, but the first request also opens the database pool.
wait_for_health() {
  for i in $(seq 1 30); do
    if curl -fsS --max-time 5 "$HEALTH" >/dev/null 2>&1; then
      echo "  healthy after ${i}s"
      return 0
    fi
    sleep 1
  done
  return 1
}

case "${1:-}" in

snapshot)
  say "Keeping a copy of the running release"
  mkdir -p "$PREV_DIR"
  # --delete so the copy is what is running, not an accumulation of every past deploy.
  # uploads is a symlink out of the tree and is never copied or deleted.
  rsync -a --delete --exclude uploads/ "$APP_DIR/backend/" "$PREV_DIR/backend/"
  rsync -a --delete "$APP_DIR/frontend/dist/" "$PREV_DIR/frontend-dist/"
  # The .env is the server's own and is not part of a release, but a copy costs nothing and has
  # saved people before.
  [ -f "$APP_DIR/backend/.env" ] && cp -p "$APP_DIR/backend/.env" "$PREV_DIR/.env.bak"
  "$VENV/bin/pip" freeze > "$PREV_DIR/requirements.lock" 2>/dev/null || true
  echo "  snapshot in $PREV_DIR"
  ;;

release)
  cd "$APP_DIR/backend"

  say "Python dependencies"
  # --no-deps is deliberately not used: the requirements are pinned, and a new pin needs its own
  # dependencies resolved. Nothing is reinstalled when nothing changed.
  "$VENV/bin/pip" install --quiet --upgrade --requirement requirements.txt

  say "Database migrations"
  # Alembic reads DATABASE_URL through app.config, which loads backend/.env from this directory.
  "$VENV/bin/alembic" upgrade head

  say "Restarting the API"
  sudo systemctl restart reportai-api

  say "Checking it answers"
  if ! wait_for_health; then
    echo "  the API did not answer on $HEALTH"
    sudo systemctl status reportai-api --no-pager --lines 40 || true
    journalctl -u reportai-api --no-pager --lines 60 || true
    exit 1
  fi

  say "Reloading nginx"
  sudo systemctl reload nginx

  echo
  echo "Released. $(curl -fsS --max-time 5 "$HEALTH")"
  ;;

rollback)
  say "Putting the previous release back"
  if [ ! -d "$PREV_DIR/backend" ]; then
    echo "  nothing to roll back to - $PREV_DIR is empty"
    exit 1
  fi
  rsync -a --delete --exclude uploads/ "$PREV_DIR/backend/" "$APP_DIR/backend/"
  rsync -a --delete "$PREV_DIR/frontend-dist/" "$APP_DIR/frontend/dist/"
  "$VENV/bin/pip" install --quiet --upgrade --requirement "$APP_DIR/backend/requirements.txt"
  sudo systemctl restart reportai-api
  wait_for_health || { journalctl -u reportai-api --no-pager --lines 60 || true; exit 1; }
  # Migrations are not undone: downgrading a schema under a release that may already have written
  # to it loses data. The new columns are additive and the old code ignores them, so the previous
  # release runs on the new schema. If a migration itself is the problem, downgrade it by hand.
  echo "  rolled back. The schema was left at head - see the note in this script."
  ;;

*)
  echo "usage: deploy.sh {snapshot|release|rollback}" >&2
  exit 2
  ;;
esac

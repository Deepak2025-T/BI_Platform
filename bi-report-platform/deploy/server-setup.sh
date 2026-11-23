#!/usr/bin/env bash
#
# One-time provisioning of a fresh Ubuntu 24.04 server for ReportsAI.
#
# Run it once, as root, on the server:
#   sudo bash /opt/ReportAI/deploy/server-setup.sh
#
# It is safe to run again: every step checks for what it would create. It does not touch .env -
# that is the one file you fill in by hand, and the one the deploy never overwrites.
set -euo pipefail

APP_DIR=/opt/ReportAI
DATA_DIR=/var/lib/reportai
DB_NAME=reportai
DB_USER=reportai
SERVICE_USER=reportai
DEPLOY_USER=${DEPLOY_USER:-deploy}

say() { printf '\n== %s\n' "$1"; }

say "Packages"
apt-get update -qq
# python3.12 and its venv for the API; node for building the frontend if you ever build on the
# server; nginx to serve it; unixodbc for the SQL Server driver pyodbc links against.
apt-get install -y --no-install-recommends \
  python3 python3-venv python3-dev build-essential \
  nginx rsync curl ca-certificates unixodbc unixodbc-dev libpq5 acl

say "Users"
id -u "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
id -u "$DEPLOY_USER"  >/dev/null 2>&1 || useradd --create-home --shell /bin/bash "$DEPLOY_USER"
# The deploy user writes the tree; the service user reads it and writes uploads.
usermod -aG "$SERVICE_USER" "$DEPLOY_USER"

say "Directories"
mkdir -p "$APP_DIR"/{backend,frontend/dist} "$DATA_DIR"/uploads
# Uploaded logos and images live outside the deployed tree, so no deploy can delete them.
if [ ! -L "$APP_DIR/backend/uploads" ]; then
  rm -rf "$APP_DIR/backend/uploads"
  ln -s "$DATA_DIR/uploads" "$APP_DIR/backend/uploads"
fi
chown -R "$DEPLOY_USER:$SERVICE_USER" "$APP_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod -R g+rX "$APP_DIR"
# New files the deploy writes stay group-readable, so the service can read them without a chmod.
setfacl -R -d -m g::rX "$APP_DIR" 2>/dev/null || true

say "Database"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  DB_PASS=$(python3 -c "import secrets; print(secrets.token_urlsafe(24))")
  sudo -u postgres psql -qc "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS'"
  printf '\n  Database password (put it in %s/backend/.env as DATABASE_URL):\n    %s\n\n' "$APP_DIR" "$DB_PASS"
else
  echo "  role $DB_USER already exists, password left alone"
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"

say "Python environment"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip wheel
chown -R "$DEPLOY_USER:$SERVICE_USER" "$APP_DIR/.venv"

say "Secrets file"
if [ ! -f "$APP_DIR/backend/.env" ]; then
  if [ -f "$APP_DIR/deploy/env.production.example" ]; then
    install -o "$DEPLOY_USER" -g "$SERVICE_USER" -m 640 \
      "$APP_DIR/deploy/env.production.example" "$APP_DIR/backend/.env"
    echo "  wrote $APP_DIR/backend/.env from the example - fill it in before starting"
  fi
else
  chown "$DEPLOY_USER:$SERVICE_USER" "$APP_DIR/backend/.env"
  chmod 640 "$APP_DIR/backend/.env"
fi

say "systemd"
install -m 644 "$APP_DIR/deploy/reportai-api.service" /etc/systemd/system/reportai-api.service
systemctl daemon-reload
systemctl enable reportai-api

say "The reportai command"
# One command for start/stop/status/logs, so nobody has to remember the unit name or that systemd
# reports success before the API can actually answer anything.
install -m 755 "$APP_DIR/deploy/reportai" /usr/local/bin/reportai
echo "  installed /usr/local/bin/reportai - try: reportai status"

say "nginx"
if [ ! -f /etc/nginx/sites-available/reportai ]; then
  install -m 644 "$APP_DIR/deploy/nginx-reportai.conf" /etc/nginx/sites-available/reportai
  echo "  edit server_name in /etc/nginx/sites-available/reportai"
fi
ln -sfn /etc/nginx/sites-available/reportai /etc/nginx/sites-enabled/reportai
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

say "Letting the deploy user restart the service"
cat > /etc/sudoers.d/reportai-deploy <<SUDO
# Narrow on purpose: the deploy may restart the API and reload nginx, and nothing else.
$DEPLOY_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart reportai-api, /usr/bin/systemctl status reportai-api, /usr/bin/systemctl is-active reportai-api, /usr/bin/systemctl reload nginx
SUDO
chmod 440 /etc/sudoers.d/reportai-deploy
visudo -cf /etc/sudoers.d/reportai-deploy

cat <<DONE

Done. What is left to do by hand:

  1. Fill in $APP_DIR/backend/.env - DATABASE_URL (password above), JWT_SECRET, CONNECTIONS_KEY,
     CORS_ORIGINS. Generate the two secrets with:
       $APP_DIR/.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
       $APP_DIR/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
     Keep a copy of CONNECTIONS_KEY somewhere safe and separate from the database backups:
     without it, every saved connection password and API key is unreadable.
  2. Put the CI deploy key's public half in /home/$DEPLOY_USER/.ssh/authorized_keys.
  3. Set server_name in /etc/nginx/sites-available/reportai, then: certbot --nginx -d your.host
  4. Push to the deploy branch, or run the workflow by hand.

Day to day: reportai start | stop | restart | status | logs | url
DONE

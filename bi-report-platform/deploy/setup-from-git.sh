#!/usr/bin/env bash
#
# ReportsAI on a Linux server, from a git clone to a running service, in one command.
#
#   sudo bash setup-from-git.sh
#
# Run it again any time: every step checks for what it would create, so a second run installs new
# dependencies, rebuilds the frontend, applies new migrations and restarts - it is the update
# command as much as the setup command.
#
# The checkout *is* the deployment. /opt/ReportAI/backend and /opt/ReportAI/frontend are symlinks
# into it, so `git pull` updates the code with nothing to copy afterwards - which is what went
# wrong with copying: a stale copy, or a stray nested directory that came along for the ride.
# `.env` and `uploads/` live inside the checkout and are both in .gitignore, so a pull never
# touches them.
set -euo pipefail

REPO_URL=${REPO_URL:-https://github.com/Deepak2025-T/BI_Platform.git}
BRANCH=${BRANCH:-Bi_platformV1}
APP_DIR=${APP_DIR:-/opt/ReportAI}
REPO_DIR=$APP_DIR/repo
PROJECT=$REPO_DIR/bi-report-platform
DATA_DIR=/var/lib/reportai
DB_NAME=reportai
DB_USER=reportai
SERVICE_USER=reportai
# Whoever will run deploys by hand. SUDO_USER is who typed sudo, which is almost always right.
DEPLOY_USER=${DEPLOY_USER:-${SUDO_USER:-root}}
# nginx serves this app on a port of its own. Not 80 or 443: this server already runs another
# application on those, and anything that shares a port with it is one typo away from taking it
# down. A separate port cannot touch it.
NGINX_PORT=${NGINX_PORT:-8080}

say() { printf '\n== %s\n' "$1"; }
die() { printf '\nStopped: %s\n' "$1" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "run this with sudo."

# ---------------------------------------------------------------- packages

say "Packages  (setup-from-git.sh rev 3)"
apt-get update -qq
# python3-venv for the API, nginx to serve it, unixodbc because
# pyodbc links against it, acl so files the deploy writes stay readable by the service.
apt-get install -y --no-install-recommends \
  git curl ca-certificates rsync acl \
  python3 python3-venv python3-dev build-essential \
  nginx unixodbc unixodbc-dev libpq5 postgresql-client

# Node builds the frontend, and is the one package that cannot simply be asked for. A nodejs from
# NodeSource already contains npm and declares a conflict with Ubuntu's separate npm package, so on
# such a machine 'apt install nodejs npm' can never be satisfied - apt reports held broken packages
# and the whole install fails. So install Node only when it is genuinely missing.
if command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1; then
    echo "  node $(node -v) and npm $(npm -v) are already here"
else
    # Non-fatal: if apt cannot work this out, the message below says what to do, rather than the
    # run dying inside apt's dependency report with everything after this step untouched.
    apt-get install -y --no-install-recommends nodejs npm || true
    if ! command -v npm >/dev/null 2>&1; then
        apt-get install -y --reinstall nodejs || true
    fi
fi
command -v node >/dev/null 2>&1 && command -v npm >/dev/null 2>&1 || die "node and npm are needed to build the frontend, and apt on this machine cannot supply them together. Install Node 20 from https://deb.nodesource.com/ (its package carries its own npm), then run this again."

# ---------------------------------------------------------------- users and directories

say "Users and directories"
id -u "$SERVICE_USER" >/dev/null 2>&1 \
  || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
id -u "$DEPLOY_USER" >/dev/null 2>&1 || die "the deploy user $DEPLOY_USER does not exist."
usermod -aG "$SERVICE_USER" "$DEPLOY_USER"
mkdir -p "$APP_DIR" "$DATA_DIR/uploads"

# ---------------------------------------------------------------- the checkout

say "The code ($BRANCH)"
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" remote set-url origin "$REPO_URL"
    git -C "$REPO_DIR" fetch --quiet origin "$BRANCH"
    git -C "$REPO_DIR" checkout --quiet "$BRANCH"
    git -C "$REPO_DIR" reset --hard --quiet "origin/$BRANCH"
    echo "  updated to $(git -C "$REPO_DIR" log -1 --format='%h %s')"
else
    git clone --quiet --branch "$BRANCH" "$REPO_URL" "$REPO_DIR"
    echo "  cloned at $(git -C "$REPO_DIR" log -1 --format='%h %s')"
fi
[ -d "$PROJECT/backend" ] || die "$PROJECT/backend is missing - is $BRANCH the right branch?"

# ---------------------------------------------------------------- the layout

say "Layout"
# An earlier copy-based install leaves real directories here. The .env inside one is the server's
# own and is not in git, so it is rescued before anything is moved, and the old directory is put
# aside rather than deleted - this script does not get to destroy a configuration by surprise.
for part in backend frontend; do
    link=$APP_DIR/$part
    target=$PROJECT/$part
    if [ -L "$link" ]; then
        ln -sfn "$target" "$link"
    elif [ -d "$link" ]; then
        if [ -f "$link/.env" ] && [ ! -f "$target/.env" ]; then
            cp -p "$link/.env" "$target/.env"
            echo "  kept your $part/.env"
        fi
        mv "$link" "$link.replaced-$(date +%Y%m%d%H%M%S)"
        ln -s "$target" "$link"
        echo "  $part was a copy; it is now a link into the checkout (the old one is kept beside it)"
    else
        ln -s "$target" "$link"
    fi
done

# Uploaded logos and images live outside the checkout, so neither a pull nor a rebuild can take
# them with it.
if [ ! -L "$PROJECT/backend/uploads" ]; then
    [ -d "$PROJECT/backend/uploads" ] && rsync -a "$PROJECT/backend/uploads/" "$DATA_DIR/uploads/"
    rm -rf "$PROJECT/backend/uploads"
    ln -s "$DATA_DIR/uploads" "$PROJECT/backend/uploads"
fi

chown -R "$DEPLOY_USER:$SERVICE_USER" "$APP_DIR" "$REPO_DIR"
chown -R "$SERVICE_USER:$SERVICE_USER" "$DATA_DIR"
chmod -R g+rX "$REPO_DIR"
setfacl -R -d -m g::rX "$REPO_DIR" 2>/dev/null || true

# ---------------------------------------------------------------- secrets

ENV_FILE=$PROJECT/backend/.env
PY=$APP_DIR/.venv/bin/python

say "Python environment"
[ -d "$APP_DIR/.venv" ] || python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --quiet --upgrade pip wheel
"$APP_DIR/.venv/bin/pip" install --quiet --requirement "$PROJECT/backend/requirements.txt"
chown -R "$DEPLOY_USER:$SERVICE_USER" "$APP_DIR/.venv"

# Filled in means a real Fernet key and no leftover placeholder - not merely "the line exists".
# A half-edited .env is worse than none: it looks configured and fails at the first query.
env_is_filled() {
    [ -f "$ENV_FILE" ] || return 1
    grep -qE '^CONNECTIONS_KEY=[A-Za-z0-9_-]{43}=$' "$ENV_FILE" || return 1
    if grep -qE 'PUT-THE|PUT-A-|<first command|<second command|passw0rd|change-me' "$ENV_FILE"; then
        echo "  $ENV_FILE still has a placeholder in it - writing a fresh one"
        return 1
    fi
    return 0
}

# The one address a fresh server has is its own IP, and two steps below need it: the origin the
# browser will send, and the name nginx answers to. Empty on a host with no global address.
HOST_IP=$(ip -4 addr show scope global 2>/dev/null | grep -oP 'inet \K[\d.]+' | head -1 || true)

say "Secrets"
if env_is_filled; then
    echo "  $ENV_FILE is already filled in - left exactly as it is"
else
    DB_PASS=$("$PY" -c "import secrets; print(secrets.token_urlsafe(24))")
    cat > "$ENV_FILE" <<ENV
DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASS@127.0.0.1:5432/$DB_NAME
JWT_SECRET=$("$PY" -c "import secrets; print(secrets.token_urlsafe(48))")
CONNECTIONS_KEY=$("$PY" -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
CORS_ORIGINS=http://127.0.0.1:$NGINX_PORT${HOST_IP:+,http://$HOST_IP:$NGINX_PORT}
SCHEDULER_ENABLED=true
AI_TIMEOUT_SECONDS=300
AI_DASHBOARD_MAX_SECONDS=1500
OLLAMA_NUM_CTX=16384
OLLAMA_KEEP_ALIVE=30m
ENV
    echo "  wrote $ENV_FILE with fresh secrets"
    echo "  !! save CONNECTIONS_KEY somewhere safe: without it, saved connection passwords and"
    echo "     API keys cannot be decrypted, and there is no recovery."
fi
chown "$DEPLOY_USER:$SERVICE_USER" "$ENV_FILE"
chmod 640 "$ENV_FILE"

# ---------------------------------------------------------------- database

say "Database"
systemctl enable --now postgresql >/dev/null 2>&1 || true
# The password in .env is the one that counts, so the role is set to match it. That is the failure
# this avoids: a role and a config file each holding a different password, and a migration that
# stops on "password authentication failed" with no clue which of the two is wrong.
DB_PASS_IN_ENV=$(sed -n 's|^DATABASE_URL=postgresql+psycopg://[^:]*:\([^@]*\)@.*|\1|p' "$ENV_FILE")
[ -n "$DB_PASS_IN_ENV" ] || die "DATABASE_URL in $ENV_FILE has no password in it."
if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    sudo -u postgres psql -qc "ALTER ROLE $DB_USER WITH LOGIN PASSWORD '$DB_PASS_IN_ENV'"
else
    sudo -u postgres psql -qc "CREATE ROLE $DB_USER LOGIN PASSWORD '$DB_PASS_IN_ENV'"
fi
sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 \
  || sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
(cd "$PROJECT/backend" && "$PY" -c "
from app.config import settings
from sqlalchemy import create_engine, text
create_engine(settings.database_url).connect().execute(text('select 1'))
print('  the API can reach the database')") || die "the database refused the credentials in $ENV_FILE."

say "Migrations"
(cd "$PROJECT/backend" && "$APP_DIR/.venv/bin/alembic" upgrade head)

# ---------------------------------------------------------------- the frontend

say "Frontend"
# `npm ci` installs exactly what package-lock.json pins, and fails rather than quietly resolving
# something else - which is what you want on a server.
(cd "$PROJECT/frontend" && npm ci --no-audit --no-fund && npm run build)
[ -f "$PROJECT/frontend/dist/index.html" ] || die "the frontend build produced no dist/index.html."
chown -R "$DEPLOY_USER:$SERVICE_USER" "$PROJECT/frontend/dist"

# ---------------------------------------------------------------- service, command, web server

say "The service"
install -m 644 "$PROJECT/deploy/reportai-api.service" /etc/systemd/system/reportai-api.service
systemctl daemon-reload
systemctl enable reportai-api >/dev/null

say "The reportai command"
install -m 755 "$PROJECT/deploy/reportai" /usr/local/bin/reportai

say "Permission for $DEPLOY_USER to restart it"
cat > /etc/sudoers.d/reportai-deploy <<SUDO
# Narrow on purpose: this user may restart the API and reload nginx, and nothing else.
$DEPLOY_USER ALL=(root) NOPASSWD: /usr/bin/systemctl restart reportai-api, /usr/bin/systemctl start reportai-api, /usr/bin/systemctl stop reportai-api, /usr/bin/systemctl status reportai-api, /usr/bin/systemctl is-active reportai-api, /usr/bin/systemctl enable reportai-api, /usr/bin/systemctl disable reportai-api, /usr/bin/systemctl reload nginx, /usr/bin/journalctl -u reportai-api *
SUDO
chmod 440 /etc/sudoers.d/reportai-deploy
visudo -cf /etc/sudoers.d/reportai-deploy

say "nginx"
if [ ! -f /etc/nginx/sites-available/reportai ]; then
    install -m 644 "$PROJECT/deploy/nginx-reportai.conf" /etc/nginx/sites-available/reportai
    echo "  installed /etc/nginx/sites-available/reportai"
else
    echo "  /etc/nginx/sites-available/reportai already exists - updating only its port"
fi
# The port is the one thing this script owns in that file, so it is set on every run while any
# hand edits (a hostname, a certificate certbot added) are left alone.
sed -i -E "s/^(\s*listen\s+)(\[::\]:)?[0-9]+;/\1\2$NGINX_PORT;/" /etc/nginx/sites-available/reportai
ln -sfn /etc/nginx/sites-available/reportai /etc/nginx/sites-enabled/reportai
# -t checks every enabled site, so a fault in a neighbour's config stops here too. Better that
# than reloading nginx into a broken state and taking the other application down with us.
nginx -t || die "nginx is not happy with its configuration - nothing was reloaded. See the lines above."
# A reload only works on a running nginx, and asking a stopped one to reload fails outright -
# which, under set -e, ended the run right here and left the API unstarted. Enable it so it comes
# back after a reboot, and start it when it is down instead of asking it to reload.
systemctl enable nginx >/dev/null 2>&1 || true
if systemctl is-active --quiet nginx; then
    systemctl reload nginx
else
    echo "  nginx was not running - starting it"
    systemctl start nginx || die "nginx would not start. See: systemctl status nginx"
fi
echo "  serving on port $NGINX_PORT"

# A closed firewall port is indistinguishable from a broken deploy in a browser, so open the one
# port this app needs. Only that port: nothing else about the firewall is touched.
if command -v ufw >/dev/null 2>&1 && ufw status 2>/dev/null | grep -q "Status: active"; then
    ufw allow "$NGINX_PORT/tcp" >/dev/null && echo "  opened $NGINX_PORT/tcp in ufw"
fi

# ---------------------------------------------------------------- start

say "Starting"
systemctl restart reportai-api
for i in $(seq 1 30); do
    if curl -fsS --max-time 5 http://127.0.0.1:8000/api/health >/dev/null 2>&1; then
        READY=yes; break
    fi
    sleep 1
done
if [ "${READY:-no}" != "yes" ]; then
    journalctl -u reportai-api -n 40 --no-pager
    die "the API did not answer on 127.0.0.1:8000 within 30 seconds."
fi

cat <<DONE

== Running

  reportai status | start | stop | restart | logs | url

Address:
$(reportai url 2>/dev/null || echo "  http://127.0.0.1/ - set server_name in the nginx site")

Open this:

  http://${HOST_IP:-this-server}:$NGINX_PORT/

Still to do by hand:
  1. Your first account (not app.seed - that makes demo logins with published passwords):
       cd $PROJECT/backend
       sudo -u $SERVICE_USER $PY -m app.create_admin you@example.com "Your Name"
  2. To use a hostname instead of the IP, both of these have to agree, or the page loads and
     every call it makes is refused:
       sed -i 's/server_name .*/server_name YOUR.HOST;/' /etc/nginx/sites-available/reportai
       nginx -t && systemctl reload nginx
       sed -i 's|^CORS_ORIGINS=.*|CORS_ORIGINS=http://YOUR.HOST:$NGINX_PORT|' $ENV_FILE
       reportai restart

This app is on port $NGINX_PORT and touches nothing on 80 or 443, where the other application on
this server lives.

To update later, run this script again - it pulls $BRANCH, rebuilds, migrates and restarts.
DONE

# Deploying ReportsAI

The server runs three things: **PostgreSQL**, the **API** under systemd, and **nginx** serving the
built React app and passing `/api` to the API. GitHub Actions builds and tests on its own runners
and copies the result in over SSH — the server never needs node, a compiler, or a copy of the
repository.

```
GitHub Actions                        srv (Ubuntu 24.04)
  backend  -> pytest                    nginx :80/:443
  frontend -> tsc + vite build             /     -> /opt/ReportAI/frontend/dist
       |                                   /api  -> 127.0.0.1:8000
       | rsync over SSH                 reportai-api.service (uvicorn, 1 worker)
       +--------------------------->    PostgreSQL 16 on 127.0.0.1:5432
```

## What lives where on the server

| Path | What it is | Replaced on deploy |
|---|---|---|
| `/opt/ReportAI/backend` | API source and pinned requirements | yes |
| `/opt/ReportAI/frontend/dist` | The built app nginx serves | yes |
| `/opt/ReportAI/deploy` | These scripts | yes |
| `/opt/ReportAI/.venv` | Python environment | kept, updated from `requirements.txt` |
| `/opt/ReportAI/backend/.env` | Secrets | **never** — it is the server's own |
| `/var/lib/reportai/uploads` | Logos and images people uploaded | **never** — symlinked into the tree |
| `/opt/ReportAI/previous` | The release before this one | written by each deploy |

## One-time setup

### 1. On the server

```bash
sudo mkdir -p /opt/ReportAI/deploy
# Copy the deploy folder up by hand the first time; after that the workflow keeps it current:
#   scp -r bi-report-platform/deploy/* root@srv:/opt/ReportAI/deploy/
sudo bash /opt/ReportAI/deploy/server-setup.sh
```

It installs the packages, makes the `reportai` service user and the `deploy` SSH user, creates the
database and role (printing the generated password **once**), builds the virtualenv, installs the
systemd unit and the nginx site, and gives the deploy user permission to restart the service and
nothing else. Running it again is safe.

### 2. Fill in the secrets

```bash
sudo -u deploy nano /opt/ReportAI/backend/.env    # from deploy/env.production.example
```

`DATABASE_URL` takes the password the setup script printed. Generate the other two:

```bash
/opt/ReportAI/.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(48))"
/opt/ReportAI/.venv/bin/python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

> **Back up `CONNECTIONS_KEY` somewhere separate from the database.** It encrypts every saved
> database password and AI API key. Without it those values cannot be decrypted, and there is no
> recovery — people would have to re-enter every connection.

Keep the file to plain `KEY=value` lines with no quotes and no trailing comments: systemd reads it
too, and would take the quotes as part of the value.

### 3. The deploy key

On your laptop:

```bash
ssh-keygen -t ed25519 -f reportai_deploy -C "github-actions" -N ""
ssh-keyscan -p 22 YOUR.SERVER.IP          # for SSH_KNOWN_HOSTS below
```

Put the **public** half on the server:

```bash
sudo -u deploy mkdir -p /home/deploy/.ssh
sudo -u deploy tee -a /home/deploy/.ssh/authorized_keys < reportai_deploy.pub
sudo -u deploy chmod 700 /home/deploy/.ssh
sudo -u deploy chmod 600 /home/deploy/.ssh/authorized_keys
```

### 4. GitHub secrets

*Settings → Secrets and variables → Actions*, or in the `production` environment if you want a
manual approval before each release:

| Secret | Value |
|---|---|
| `SSH_HOST` | the server's IP or hostname |
| `SSH_USER` | `deploy` |
| `SSH_PORT` | the SSH port (omit for 22) |
| `SSH_KEY` | the whole **private** key file, `-----BEGIN` line included |
| `SSH_KNOWN_HOSTS` | the `ssh-keyscan` output from step 3 |

The key is written to the runner, used, and deleted in the last step. The known-hosts secret is
what makes the connection *verified* rather than trusted blindly — without it a deploy could be
pointed at another machine.

### 5. First release and first account

Push to `Bi_platformV1`, or run the workflow by hand from the Actions tab. Then create a real
manager — **not** `app.seed`, which makes demo accounts with published passwords:

```bash
cd /opt/ReportAI/backend
sudo -u reportai /opt/ReportAI/.venv/bin/python -m app.create_admin you@company.com "Your Name"
```

### 6. A name and a certificate

Point a DNS record at the server, set `server_name` in `/etc/nginx/sites-available/reportai`, then:

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d reports.yourcompany.com
```

Certbot rewrites the site for TLS and sets up renewal. Afterwards set `CORS_ORIGINS` in `.env` to
the `https://` address and restart the API. Only ports 80, 443 and SSH need to be open: PostgreSQL
and uvicorn both listen on `127.0.0.1` only.

## What a deploy does

1. **backend** runs `pytest` (SQLite, so no database service is needed) and **frontend** runs
   `tsc -b && vite build`. A failure in either stops the release.
2. The deploy scripts go up, then `deploy.sh snapshot` copies the running release to
   `/opt/ReportAI/previous`.
3. `rsync --delete` sends the backend source and the built frontend. `.env`, `.venv` and `uploads`
   are excluded, so no deploy can delete them.
4. `deploy.sh release` installs any changed requirements, runs `alembic upgrade head`, restarts the
   service, and polls `/api/health` for up to 30 seconds.
5. If the API does not answer, the job prints the journal, runs `deploy.sh rollback` to put the
   previous build back, and goes red.

Expect a few seconds of downtime at the restart. Anyone mid-build loses that build; saved reports
and their data are untouched.

**Migrations are not rolled back.** Downgrading a schema the new release may already have written
to loses data. The migrations here are additive, so the previous release runs fine against the
newer schema. If a migration is itself the problem, downgrade it by hand:
`sudo -u reportai /opt/ReportAI/.venv/bin/alembic downgrade -1`.

## Day to day

```bash
sudo systemctl status reportai-api          # is it up
journalctl -u reportai-api -f               # live log
journalctl -u reportai-api --since "1 hour ago" | grep -i error
sudo systemctl restart reportai-api         # after an .env change
curl -s localhost:8000/api/health           # what the deploy checks
sudo tail -f /var/log/nginx/reportai.error.log
bash /opt/ReportAI/deploy/deploy.sh rollback   # undo the last release by hand
```

### Backups

Two things matter, and they are worth little apart: the database, and `CONNECTIONS_KEY`.

```bash
sudo -u postgres pg_dump -Fc reportai > /var/backups/reportai-$(date +%F).dump
sudo tar czf /var/backups/reportai-uploads-$(date +%F).tgz -C /var/lib/reportai uploads
```

Put those two lines in a nightly cron or a systemd timer, keep a few weeks, and store the key
itself in your password manager — not next to the dumps.

## Why one worker

Scheduled report refreshes run inside the API process (`SCHEDULER_ENABLED`), so a second uvicorn
worker would refresh every scheduled report twice. The work is almost entirely waiting on a
database or a model, which one asyncio worker handles comfortably. If you outgrow it, set
`SCHEDULER_ENABLED=false` on the extra workers and keep one process with it on.

## When something is wrong

| What you see | Usually |
|---|---|
| 502 from nginx | the API is down — `journalctl -u reportai-api -n 50` |
| 504 on a dashboard build | a build over 30 minutes; raise `proxy_read_timeout` in the nginx site |
| "JWT_SECRET … is still the default" on Settings | `.env` was never filled in, or systemd read quotes as part of a value |
| Connections cannot be saved | `CONNECTIONS_KEY` is empty |
| Everyone signed out after a deploy | `JWT_SECRET` changed — every token signed with the old one is void |
| Sign-in fails from the browser only | `CORS_ORIGINS` does not match the address people actually use |
| Uploaded logos gone | `backend/uploads` is a real directory instead of the symlink to `/var/lib/reportai/uploads` |

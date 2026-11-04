# BI Report Platform: set it up on another computer

This guide takes a clean computer to a running BI Report Platform, step by step, with every command. It is written for **Windows 10/11** (PowerShell). Linux and macOS commands are in [Appendix A](#appendix-a-linux-and-macos).

`README.md` explains the features. This file only covers installing, moving and running the app.

## What you are installing

```
 Browser  ──►  React frontend (Vite)     http://localhost:5173
                    │  /api/... (Vite forwards to the backend)
                    ▼
               FastAPI backend (Python)  http://localhost:8000
                    │  SQL
                    ▼
               PostgreSQL 16 (app database "bi_db")   localhost:5432
                    ▲
   optional:   Ollama / Claude API / OpenAI-compatible server (AI models)
```

| Part | Version used by this project | Where it lives |
|---|---|---|
| Python | 3.12 | `backend/` (virtual environment in `backend/.venv`) |
| Node.js + npm | 22 LTS or newer | `frontend/` (packages in `frontend/node_modules`) |
| PostgreSQL | 16 (Docker image `pgvector/pgvector:pg16`, or a normal install) | Docker volume, or the Windows PostgreSQL service |
| Database tables | Alembic migrations `0001` to `0004` | `backend/migrations/versions/` |

Time needed: about 30 to 45 minutes the first time, most of it installing tools.

---

## Step 0: Decide two things first

**1. How will you run PostgreSQL?**

| Option | Choose it when | Start the app with |
|---|---|---|
| **A. Docker** (easiest) | Docker Desktop can be installed | `scripts\setup-windows.ps1`, then `scripts\start-dev.ps1` |
| **B. PostgreSQL installed on Windows** | Docker isn't allowed, or PostgreSQL is already installed | `start-local.bat` |

**2. Is this a fresh install, or are you moving an existing one?**

- **Fresh install:** you get two demo accounts and sample data. Follow Steps 1 to 8.
- **Moving an existing install** (keep its users, reports and connections): follow Steps 1 to 8, but also do [Step 9](#step-9-move-the-data-from-the-old-computer) before you open the app. You need the old computer's `CONNECTIONS_KEY`. Without it, saved database passwords and AI API keys can't be read.

---

## Step 1: Install the tools

Install these in order. Accept the defaults unless a note says otherwise.

1. **Git**: https://git-scm.com/download/win
2. **Node.js 22 LTS** (or newer): https://nodejs.org
3. **Python 3.12**: https://www.python.org/downloads/windows/
   On the first installer screen, **tick "Add python.exe to PATH"**.
4. **PostgreSQL**, one of:
   - **Option A: Docker Desktop**: https://www.docker.com/products/docker-desktop/
     Keep "Use WSL 2" ticked, restart Windows, open Docker Desktop once and wait for **Engine running**.
   - **Option B: PostgreSQL 16 for Windows**: https://www.postgresql.org/download/windows/
     Write down the password you give the `postgres` superuser. Keep the port at **5432**.
5. *Optional:* **Microsoft ODBC Driver 18 for SQL Server**, only if you will connect the app to SQL Server databases.
6. *Optional:* **Ollama** (https://ollama.com), only if you want a local AI model.

Open a **new** PowerShell window and check:

```powershell
git --version
node -v
npm -v
py -3.12 --version
docker --version            # Option A only
docker compose version      # Option A only
```

Allow PowerShell to run the project's scripts (once per Windows user, no admin needed):

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Close PowerShell and open a new window afterwards.

---

## Step 2: Copy the project to the new computer

Use a short path without spaces, for example `C:\dev\bi-report-platform`.

**Do not copy** these folders and files. They belong to the old computer and are rebuilt in Steps 4 to 6:

| Skip | Why |
|---|---|
| `backend\.venv` | Python environment, tied to the old computer's paths |
| `frontend\node_modules` | npm packages, reinstalled by `npm install` |
| `__pycache__`, `frontend\dist`, `.local-run`, `frontend\tsconfig.tsbuildinfo` | generated files |
| `backend\.env` | holds secrets. Create a new one in Step 4 (copy only `CONNECTIONS_KEY` over, see Step 9) |

**Copy on the old computer with robocopy** (to a USB drive or network share, here `E:\`):

```powershell
robocopy D:\bi-report-platform E:\bi-report-platform /E /XD node_modules .venv __pycache__ .local-run dist /XF .env tsconfig.tsbuildinfo
```

Then copy `E:\bi-report-platform` to `C:\dev\bi-report-platform` on the new computer.

**Or with Git** (easiest on a new computer): the code is on GitHub, in the `bi-report-platform` folder of the
`BI-Project` branch.

```powershell
cd C:\dev
git clone --branch BI-Project https://github.com/Deepak2025-T/BI_Platform.git
cd C:\dev\BI_Platform\bi-report-platform
```

Cloned this way, the project folder is `C:\dev\BI_Platform\bi-report-platform`: use it wherever this guide says
`C:\dev\bi-report-platform`. `git pull` in `C:\dev\BI_Platform` gets later updates.

`.gitignore` already leaves out `.env`, `.venv`, `node_modules` and `dist`.

All the following steps run in this folder:

```powershell
cd C:\dev\bi-report-platform
```

---

## Step 3: Start PostgreSQL and create the app database

### Option A: Docker

```powershell
docker compose up -d
docker ps
```

`docker ps` should list `bi_postgres` with status `Up`. The container already creates user `bi`, password `bi_dev_password`, database `bi_db` (see `docker-compose.yml`). Data stays in the Docker volume `pgdata` across restarts.

### Option B: PostgreSQL installed on Windows

Create the `bi` login and the `bi_db` database once. Use your PostgreSQL version number in the path (16 or 17), and replace `choose-a-password`:

```powershell
$psql = "C:\Program Files\PostgreSQL\16\bin\psql.exe"
& $psql -U postgres -h localhost -c "CREATE ROLE bi LOGIN PASSWORD 'choose-a-password';"
& $psql -U postgres -h localhost -c "CREATE DATABASE bi_db OWNER bi;"
```

It asks for the `postgres` password from Step 1. Check the new login works:

```powershell
& $psql -U bi -h localhost -d bi_db -c "SELECT version();"
```

**Port 5432 already used?** If both a Windows PostgreSQL and Docker are present, change the port line in `docker-compose.yml` to `"5433:5432"` and use `localhost:5433` in `DATABASE_URL` (Step 4).

---

## Step 4: Set up the backend (Python)

```powershell
cd C:\dev\bi-report-platform\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Your prompt now starts with `(.venv)`. Generate the two secrets:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Open `backend\.env` (for example `notepad .env`) and fill it in:

```ini
# Option A (Docker): keep this line as it is.
# Option B: put the password you chose in Step 3.
DATABASE_URL=postgresql+psycopg://bi:bi_dev_password@localhost:5432/bi_db

# First value printed above
JWT_SECRET=<paste the long random string>
JWT_EXPIRE_MINUTES=480

# The address people open in the browser (comma-separate several)
CORS_ORIGINS=http://localhost:5173

# Second value printed above. MOVING an install: use the OLD computer's key instead (Step 9).
CONNECTIONS_KEY=<paste the Fernet key>
```

Optional setting: `SCHEDULER_ENABLED=false` turns off scheduled report refreshes in this process. Leave it out normally.

**Keep a copy of `CONNECTIONS_KEY` in a password manager**, separate from database backups. It encrypts the saved database passwords and AI API keys. If it is lost, those have to be entered again.

> If a password contains `@`, `:`, `/` or `#`, write it URL-encoded in `DATABASE_URL` (for example `@` becomes `%40`).

---

## Step 5: Create the tables and the demo data

Still in `backend` with `(.venv)` active:

```powershell
python -m app.migrate
```

This runs all Alembic migrations (`alembic upgrade head`). It is safe to run on any database, including one restored from an older install. It should end with `Database is up to date.`

**Fresh install:** add the demo accounts, sample sales data, categories and templates:

```powershell
python -m app.seed
```

Running the seed again doesn't create duplicates.

*Optional:* a bigger demo database (an electronics shop, about 9,000 orders) with a ready-made **Demo shop** connection:

```powershell
python -m app.demo_shop
```

**Moving an install:** do Step 9 *before* this step, then run `python -m app.migrate`. Skip `app.seed` (it would add the demo accounts to your real data).

---

## Step 6: Set up the frontend (React)

Open a **second** PowerShell window:

```powershell
cd C:\dev\bi-report-platform\frontend
npm install
```

You don't need `frontend\.env` for local use. In development, `vite.config.ts` forwards every `/api` call to `http://127.0.0.1:8000`.

---

## Step 7: Start the app

### By hand (any option): two windows

Window 1, the backend:

```powershell
cd C:\dev\bi-report-platform\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

Window 2, the frontend:

```powershell
cd C:\dev\bi-report-platform\frontend
npm run dev
```

Open **http://localhost:5173**. Leave both windows open while you use the app.

### With the scripts

| Option | Start | Stop |
|---|---|---|
| A. Docker | `.\scripts\start-dev.ps1` (starts Docker PostgreSQL, opens a backend and a frontend window, and the browser) | Ctrl+C in both windows, then `docker compose stop` |
| B. Windows PostgreSQL | Double-click `start-local.bat` (checks port 5432, runs migrations and the seed, opens both windows and the browser) | Double-click `stop-local.bat` |

Note: `start-local.bat` runs `python -m app.seed` every time. That's harmless for a demo install, but on a moved install it adds the demo accounts if they are missing. Delete them in the app afterwards, or start by hand instead.

---

## Step 8: Check that it works

| Check | Expected |
|---|---|
| http://localhost:8000/api/health | `{"status":"ok"}` |
| http://localhost:8000/docs | The API page listing every endpoint |
| http://localhost:5173 | The sign-in page |

Sign in with a demo account (fresh install only):

| Role | Email | Password |
|---|---|---|
| Manager | manager@example.com | Manager@123 |
| User | user@example.com | User@123 |

Then, as the manager:

1. Open **Settings**. It lists any setup problems (for example a missing `CONNECTIONS_KEY` or a weak `JWT_SECRET`). The list should be empty.
2. Open **Users and access**. **Change both demo passwords**, or create real accounts and disable the demo ones, before anyone else uses the app.
3. Ask "Show monthly revenue by region for Q1 2024" on the home page to see a report built from the sample data.

*Optional:* run the backend tests (they use a throwaway SQLite database, never your real one):

```powershell
cd C:\dev\bi-report-platform\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
python -m pytest
```

---

## Step 9: Move the data from the old computer

Skip this step for a fresh install.

### 9.1 On the old computer: back up the database

**Docker:**

```powershell
docker exec bi_postgres pg_dump -U bi -Fc -f /tmp/bi_db.dump bi_db
docker cp bi_postgres:/tmp/bi_db.dump .\bi_db.dump
```

**Windows PostgreSQL:**

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_dump.exe" -U bi -h localhost -Fc -f bi_db.dump bi_db
```

Also copy the `CONNECTIONS_KEY=` line from the old `backend\.env`. Copy it securely, not by email or chat.

### 9.2 On the new computer: restore it

Do this after Step 3 and Step 4, and **before** Step 5. The `bi_db` database must exist and be empty.

**Docker:**

```powershell
docker cp .\bi_db.dump bi_postgres:/tmp/bi_db.dump
docker exec bi_postgres pg_restore -U bi -d bi_db --no-owner /tmp/bi_db.dump
```

**Windows PostgreSQL:**

```powershell
& "C:\Program Files\PostgreSQL\16\bin\pg_restore.exe" -U bi -h localhost -d bi_db --no-owner bi_db.dump
```

Then put the old `CONNECTIONS_KEY` in the new `backend\.env`, and in `backend`:

```powershell
python -m app.migrate
```

This brings the restored database up to the latest migration, including databases from before Alembic was added.

### 9.3 Things that point at the old computer

- **Connections** (Manage > Connections) to databases on `localhost` now mean the *new* computer. Edit them to use the real server name, then click **Test connection**.
- **AI models** with base URL `http://localhost:11434` (Ollama) need Ollama installed on the new computer, with the same models pulled (`ollama pull <model>`).
- `.claude\launch.json` contains `D:\bi-report-platform` paths. Update them if you use Claude Code's preview on the new computer.

---

## Step 10 (optional): AI models

You don't need AI to use the app: the built-in engine answers questions about the sample data. To add AI models, sign in as a manager and open **Manage > AI models**.

| Provider | What to install or get | In the app |
|---|---|---|
| Ollama (runs locally) | Install Ollama, then for example `ollama pull qwen2.5-coder:14b` | Base URL `http://localhost:11434`, then **Find installed models** |
| Claude (Anthropic API) | An API key from console.anthropic.com | Paste the key in the form. It is stored encrypted with `CONNECTIONS_KEY` |
| OpenAI-compatible (LM Studio, vLLM, ...) | The server running, for example `http://localhost:1234/v1` | Base URL, plus a key if the server needs one |

API keys are typed into the app, never into `.env` or the code. `CONNECTIONS_KEY` must be set first (Step 4).

---

## Every day after setup

| Task | Commands |
|---|---|
| Start (Docker) | `.\scripts\start-dev.ps1` |
| Start (Windows PostgreSQL) | double-click `start-local.bat` |
| Stop | Ctrl+C in both windows (or `stop-local.bat`); Docker: `docker compose stop` |
| After updating the code | in `backend`: `pip install -r requirements.txt` and `python -m app.migrate`; in `frontend`: `npm install` |
| Back up the app database | see Step 9.1 |
| Reset everything (Docker, **deletes all data**) | `docker compose down -v`, `docker compose up -d`, then in `backend`: `python -m app.migrate` and `python -m app.seed` |

---

## Running it for other people (production notes)

The steps above are a development setup. For a shared server:

1. Build the frontend with `VITE_API_URL` set to the API's address:
   ```powershell
   cd frontend
   $env:VITE_API_URL = "https://bi-api.yourcompany.com"
   npm run build
   ```
   It creates `frontend\dist`. Serve that folder with a web server (IIS, Nginx), over HTTPS.
2. Run the API without `--reload`, as a service:
   ```powershell
   cd backend
   .\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
   Put it behind the same web server (HTTPS), and open port 8000 only to that server.
3. In `backend\.env`, set `CORS_ORIGINS` to the frontend's real address. Use a strong database password instead of `bi_dev_password`. Keep `.env` out of Git.
4. Remove or disable the demo accounts.
5. Schedule a daily `pg_dump` backup (Step 9.1). Store `CONNECTIONS_KEY` separately from the backups.
6. Scheduled report refreshes run inside the API process, so keep it running. With several API processes, `SCHEDULER_ENABLED=false` on the extra ones is optional.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`, then open a new window. Or run a script once with `powershell -ExecutionPolicy Bypass -File .\scripts\<name>.ps1` |
| `py` is not recognised | Reinstall Python with "Add python.exe to PATH" ticked, or use `python` instead of `py -3.12` |
| `docker: error during connect` | Docker Desktop isn't running. Open it and wait for **Engine running** |
| `PostgreSQL is not listening on 127.0.0.1:5432` (start-local.bat) | Start the PostgreSQL service: `services.msc`, find `postgresql-x64-16`, click Start |
| Port 5432 already in use | Another PostgreSQL is running. Use port 5433 for Docker (see Step 3) |
| `password authentication failed for user "bi"` | `DATABASE_URL` has the wrong password. With Docker, an old volume may have a different password: `docker compose down -v` (deletes its data) and start again |
| `RuntimeError: The database has no migrations applied` | Run `python -m app.migrate` in `backend` |
| `relation "app_users" already exists` during `alembic upgrade head` | Run `python -m app.migrate` instead. It handles databases from before Alembic |
| `ModuleNotFoundError: No module named 'app'` | Run Python commands from the `backend` folder, with `.venv` activated |
| Sign-in page says "Can't reach the server" | The backend isn't running. Check its window, and http://localhost:8000/api/health |
| Everyone is signed out ("Session expired") | `JWT_SECRET` changed. Sign in again |
| Saved connections fail with a decryption error after moving | `CONNECTIONS_KEY` differs from the old computer's. Put the old key back, or re-enter each connection's password |
| SQL Server connection: `Can't open lib 'ODBC Driver 18 for SQL Server'` | Install Microsoft ODBC Driver 18 on the computer that runs the backend |
| `npm install` is slow or fails | Check the company proxy, or `npm config set registry https://registry.npmjs.org/` |
| `pip install` fails building a package | Make sure the venv uses Python 3.12 (`python --version`). Recreate `.venv` with `py -3.12 -m venv .venv` |

---

## Appendix A: Linux and macOS

The same steps with shell commands. Install Git, Python 3.12, Node.js 22+, and Docker or PostgreSQL 16 with your package manager (for example `sudo apt install python3.12 python3.12-venv postgresql`, or `brew install python@3.12 node postgresql@16`).

```bash
cd ~/dev/bi-report-platform

# Database (Docker)
docker compose up -d
# ...or a local PostgreSQL:
#   sudo -u postgres psql -c "CREATE ROLE bi LOGIN PASSWORD 'choose-a-password';"
#   sudo -u postgres psql -c "CREATE DATABASE bi_db OWNER bi;"

# Backend
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"                                  # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"    # CONNECTIONS_KEY
nano .env                      # fill in DATABASE_URL, JWT_SECRET, CONNECTIONS_KEY
python -m app.migrate
python -m app.seed             # fresh install only
uvicorn app.main:app --reload --port 8000

# Frontend (second terminal)
cd ~/dev/bi-report-platform/frontend
npm install
npm run dev
```

The `scripts\*.ps1` and `.bat` files are Windows-only. Use the commands above instead. For SQL Server connections on Linux, install `msodbcsql18` and `unixodbc`.

## Appendix B: Command checklist (fresh install, Docker, Windows)

```powershell
# one time
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
cd C:\dev\bi-report-platform
docker compose up -d
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
notepad .env                    # paste JWT_SECRET and CONNECTIONS_KEY
python -m app.migrate
python -m app.seed
cd ..\frontend
npm install

# every day
cd C:\dev\bi-report-platform
.\scripts\start-dev.ps1         # then open http://localhost:5173
```

`scripts\setup-windows.ps1` does the one-time part in one go (Docker database, venv, packages, `.env` with a random `JWT_SECRET`, migrations, seed, `npm install`). It does **not** set `CONNECTIONS_KEY`, so add that to `backend\.env` by hand afterwards (Step 4), or saving connections and AI models won't work.

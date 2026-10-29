# Local setup log — this machine

Record of the exact commands used to bring this checkout up on **Windows 11**, at
`D:\Timus-COM\BI_Platform\bi-report-platform`, on **2026-10-26**.

`SETUP.md` is the general guide. This file records what was actually run here, including the
four machine-specific problems that had to be solved along the way.

---

## 1. What was already on the machine

```powershell
git --version              # git version 2.55.0.windows.4
node -v                    # v24.22.0
npm -v                     # 11.19.1
py -0p                     # 3.15, 3.13, 3.12, 3.9 installed
py -3.12 --version         # Python 3.12.10
docker --version           # Docker version 29.9.1
docker compose version     # Docker Compose version v5.6.0
psql --version             # not on PATH (PostgreSQL 18 is installed as a Windows service)
```

Nothing new had to be installed.

---

## 2. Problems found, and the fix for each

| # | Problem | Cause | Fix |
|---|---|---|---|
| 1 | `TypeError: descriptor '__getitem__' requires a 'typing.Union' object` on `import app.main` | `backend\.venv` had been built with **Python 3.15**; SQLAlchemy 2.0.36 does not support it | Rebuilt the venv with **Python 3.12** |
| 2 | `password authentication failed for user "bi"` | The Docker volume `pgdata` was first created with a different password, so `POSTGRES_PASSWORD` in `docker-compose.yml` no longer applied | `ALTER ROLE bi WITH PASSWORD ...` inside the container |
| 3 | Still `password authentication failed` from Windows | A **native PostgreSQL 18 Windows service** owns `0.0.0.0:5432`, so `localhost:5432` never reached the container | Moved the container to port **5433** and pointed `DATABASE_URL` there |
| 4 | `Setup: CONNECTIONS_KEY is not set` | `backend\.env` had an empty `CONNECTIONS_KEY=` | Generated a Fernet key and wrote it into `.env` |

---

## 3. The commands, in order

### 3.1 Rebuild the backend virtual environment on Python 3.12

The old `.venv` was moved aside rather than deleted, so it can still be inspected:

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\backend
Rename-Item .venv .venv-py315-old
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe --version          # Python 3.12.10
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

`.venv-py315-old` and the stray `bi_pv1\` venv in the project root are both unused now and can be
deleted at any time.

> Always use `py -3.12`. Plain `python` on this machine is **3.15**, which this project's pinned
> dependencies do not support.

### 3.2 Move Docker PostgreSQL to port 5433

Port 5432 is taken by the native PostgreSQL 18 service. In `docker-compose.yml`:

```yaml
    ports:
      - "5433:5432"      # was "5432:5432"
```

Then:

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform
docker compose up -d
docker ps --filter name=bi_postgres --format "{{.Names}} | {{.Status}} | {{.Ports}}"
# bi_postgres | Up | 0.0.0.0:5433->5432/tcp
```

To see for yourself what holds 5432:

```powershell
Get-NetTCPConnection -LocalPort 5432 -State Listen | ForEach-Object { Get-Process -Id $_.OwningProcess }
Get-Service postgresql*
```

### 3.3 Reset the `bi` role's password inside the container

Needed only because the `pgdata` volume predates the current `docker-compose.yml`:

```powershell
docker exec bi_postgres psql -U bi -d bi_db -c "ALTER ROLE bi WITH PASSWORD 'bi_dev_password';"
```

The alternative is `docker compose down -v` (which **deletes the database**) followed by
`docker compose up -d`.

### 3.4 Fill in `backend\.env`

`backend\.env` already existed with `DATABASE_URL`, `JWT_SECRET`, `JWT_EXPIRE_MINUTES` and
`CORS_ORIGINS` set. Two changes were made:

- the port in `DATABASE_URL` went from `5432` to **`5433`**
- `CONNECTIONS_KEY` was empty, so a key was generated and written in

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\backend
# Generate the key (prints it; paste it after CONNECTIONS_KEY= in .env)
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
notepad .env
```

The working `DATABASE_URL` line on this machine:

```ini
DATABASE_URL=postgresql+psycopg://bi:bi_dev_password@localhost:5433/bi_db
```

> **Back up `CONNECTIONS_KEY` to a password manager now.** It encrypts every saved database
> password and AI API key. Lose it and they all have to be entered again.

### 3.5 Create the tables and demo data

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\backend
.\.venv\Scripts\python.exe -m app.migrate
.\.venv\Scripts\python.exe -m app.seed
```

`app.migrate` applied migrations `0001_baseline` through `0005_report_history` and ended with
`Database is up to date.`

`app.seed` created:

```
  created manager: manager@example.com / Manager@123
  created user:    user@example.com    / User@123
  inserted 240 sample sales rows
  created 5 sample templates
  created 3 sample report categories
```

Optional, for a larger demo dataset (~9,000 orders plus a "Demo shop" connection):

```powershell
.\.venv\Scripts\python.exe -m app.demo_shop
```

### 3.6 Install the frontend packages

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\frontend
npm install
```

99 packages installed. `npm` reported 8 advisories and warned that `esbuild`'s postinstall script
was not auto-approved; Vite still starts and builds correctly, so no action was needed.

---

## 4. Starting the app every day

Two PowerShell windows, kept open while you use the app.

**Window 1 — backend:**

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\backend
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000
```

**Window 2 — frontend:**

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform\frontend
npm run dev
```

Then open **http://localhost:5173**.

If PowerShell refuses to run `Activate.ps1`, allow local scripts once per Windows user:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

The database container keeps running on its own. Start it after a reboot with:

```powershell
cd D:\Timus-COM\BI_Platform\bi-report-platform
docker compose up -d
```

> `start-local.bat` and `scripts\start-local.ps1` are for the **native** PostgreSQL on port 5432.
> This machine uses the Docker database on **5433**, so use `scripts\start-dev.ps1` or the two
> windows above instead.

---

## 5. What was verified

| Check | Result |
|---|---|
| `GET /api/health` | `{"status":"ok"}` |
| `GET /docs` | HTTP 200 |
| `POST /api/auth/login` as `manager@example.com` | HTTP 200, token returned, role `manager` |
| `POST /api/auth/login` through the Vite proxy | HTTP 200 |
| `http://localhost:5173` | HTTP 200 |

All of the above were confirmed with the backend on its normal port **8000** and the frontend on
**5173**.

Useful one-liners:

```powershell
curl http://localhost:8000/api/health
curl http://localhost:5173
docker exec bi_postgres psql -U bi -d bi_db -c "\dt"
```

> Vite listens on **IPv6 only** (`::1:5173`). `http://localhost:5173` works; a hard-coded
> `http://127.0.0.1:5173` does not.

---

## 6. Sign in

| Role | Email | Password |
|---|---|---|
| Manager | manager@example.com | Manager@123 |
| User | user@example.com | User@123 |

Change both passwords under **Users and access** before anyone else uses this install.

---

## 7. Known issues on this machine

### A stale backend process holding port 8000 (resolved)

A `uvicorn app.main:app --reload --port 8000` left over from an earlier attempt kept the port bound
without answering requests, so a new backend failed with:

```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8000)
```

It was stopped and the backend now runs on 8000 normally. If it happens again, close the backend's
PowerShell window, or:

```powershell
Get-Process uvicorn,python -ErrorAction SilentlyContinue |
  Where-Object { $_.Path -like "*bi-report-platform*" } |
  Stop-Process -Force
```

> Match on `uvicorn.exe` / `python.exe` under the project path. Filtering `Win32_Process` by
> command line alone also matches the PowerShell window that launched the server — and the one
> you are typing in.

Then start the backend as in section 4.

### `pyodbc` is blocked by Windows Application Control

```
ImportError: DLL load failed while importing pyodbc: An Application Control policy has blocked this file.
```

This only affects **SQL Server** connections. The rest of the app, including the PostgreSQL app
database, works without it. If SQL Server connections are needed, install the
**Microsoft ODBC Driver 18 for SQL Server** and have the Application Control / Smart App Control
policy allow `pyodbc`.

---

## 8. Full command list (clean rerun on this machine)

```powershell
# 1. Database
cd D:\Timus-COM\BI_Platform\bi-report-platform
docker compose up -d                    # docker-compose.yml maps 5433:5432

# 2. Backend
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
python -c "import secrets; print(secrets.token_urlsafe(48))"                                # JWT_SECRET
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # CONNECTIONS_KEY
notepad .env                            # set both, and use port 5433 in DATABASE_URL
python -m app.migrate
python -m app.seed

# 3. Frontend
cd ..\frontend
npm install

# 4. Run (two windows)
#    backend : uvicorn app.main:app --reload --port 8000
#    frontend: npm run dev
#    browser : http://localhost:5173
```

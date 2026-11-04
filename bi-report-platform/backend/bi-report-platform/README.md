# BI Report Platform: Windows setup guide

This is the starter project for the BI Report Platform v2 design. It runs on your own Windows machine and contains three parts that talk to each other:

```
 Browser (React, port 5173)
        │  /api/...  (Vite forwards these calls)
        ▼
 FastAPI backend (Python, port 8000)  ── login, roles, reports, query engine
        │  SQL
        ▼
 PostgreSQL + pgvector (Docker, port 5432)  ── users, reports, sample sales data
```

What already works: sign in, two roles (user and manager), asking a question, the "how I understood it" review with editable chips, building a report, the editor canvas (sections, chart type, colours, number format, autosave), publishing, the read-only viewer with filters, PDF download through the browser's print dialog, and user management for managers.

What is stubbed: the AI step. In phase 1, a small keyword engine (`backend/app/query_engine.py`) answers questions about the sample `sales` table so you can build and test the whole app. Phase 2 swaps it for Ollama + pgvector without changing the frontend.

## Who can do what

| Action | User | Manager |
|---|---|---|
| Sign in, ask questions, build reports | Yes | Yes |
| See their own reports and all published reports | Yes | Yes |
| Edit or delete a report | Only their own | Any report |
| See "Edit the SQL myself" after a failed question | No | Yes |
| Add people, change roles, reset passwords, disable accounts | No | Yes |
| Create private templates, duplicate any template | Yes | Yes |
| Share a template with everyone, edit built-in templates | No | Yes |
| Usage and settings page | No | Yes |

Roles are enforced in the backend (`backend/app/deps.py`), not just hidden in the menu. A user who types `/manage/users` into the address bar gets "You don't have access", and the API returns 403.

---

## Part 1: Install the tools (one time, about 30 minutes)

Install these in order. Restart the computer after Docker Desktop.

1. **Git**: https://git-scm.com/download/win. Accept the defaults.
2. **Node.js 22 LTS**: https://nodejs.org. Choose the LTS installer. Accept the defaults.
3. **Python 3.12**: https://www.python.org/downloads/windows/. On the first installer screen, **tick "Add python.exe to PATH"** before clicking Install.
4. **Docker Desktop**: https://www.docker.com/products/docker-desktop/. When asked, keep **"Use WSL 2 instead of Hyper-V"** ticked. Restart Windows when it finishes, then open Docker Desktop once and wait until it says "Engine running".
5. **VS Code** (recommended): https://code.visualstudio.com. Add the Python and ESLint extensions.

Open a **new** PowerShell window and check each one:

```powershell
git --version
node -v          # v22.x
npm -v
py --version     # Python 3.12.x
docker --version
docker compose version
```

If PowerShell refuses to run scripts later ("running scripts is disabled on this system"), run this once:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

## Part 2: Put the project on your machine

The code is on GitHub, in the `bi-report-platform` folder of the `BI-Project` branch. Clone it to a short path without
spaces (needs [Git](https://git-scm.com/download/win)):

```powershell
cd C:\dev
git clone --branch BI-Project https://github.com/Deepak2025-T/BI_Platform.git
cd C:\dev\BI_Platform\bi-report-platform
```

All the following steps run in that folder (this guide writes it as `C:\dev\bi-report-platform`). To get later
updates, run `git pull` in `C:\dev\BI_Platform`. Without Git, download the branch as a ZIP on GitHub (Code > Download
ZIP) and use its `bi-report-platform` folder.

## Part 3: Quick setup (scripted)

If you want the fastest route, run the setup script. It does Parts 4 to 6 for you.

```powershell
cd C:\dev\bi-report-platform
.\scripts\setup-windows.ps1
.\scripts\start-dev.ps1
```

`start-dev.ps1` opens two PowerShell windows (backend and frontend) and your browser at http://localhost:5173. Skip to Part 7.

If anything fails, follow Parts 4 to 6 by hand. They are the same steps, one at a time, so you can see where it breaks.

## Part 4: Start the database

```powershell
cd C:\dev\bi-report-platform
docker compose up -d
docker ps        # you should see bi_postgres with "Up"
```

This starts PostgreSQL 16 with the pgvector extension. Data is kept in a Docker volume, so it survives restarts. The login is in `docker-compose.yml`: user `bi`, password `bi_dev_password`, database `bi_db`.

## Part 5: Start the backend (FastAPI)

```powershell
cd C:\dev\bi-report-platform\backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1          # your prompt now starts with (.venv)
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

Open `backend\.env` in VS Code and replace `JWT_SECRET` with a random value. Generate one with:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Create the tables with Alembic, then add the two demo accounts and the sample sales data:

```powershell
alembic upgrade head
python -m app.seed
```

The tables are defined by the migrations in `backend\migrations\versions`. The API no longer creates tables when it starts; if you forget this step it stops with a message telling you what to run.

**Upgrading an install from before Alembic.** If your database was created by an earlier version of this project (the tables exist but there is no `alembic_version` table), don't run `alembic upgrade head` on it: it would try to create tables that already exist. Instead run, once:

```powershell
python -m app.migrate
```

It adds the `reports.category_id` column if your database doesn't have it yet, marks the database as being at the baseline migration (`0001_baseline`), and then applies any newer migrations. Back up the database first if it holds anything you care about. To do the same by hand: check that `reports` has a `category_id` column (very old installs: start the previous version of the app once, which adds it), then run `alembic stamp 0001_baseline` and `alembic upgrade head`. Today the baseline is also `head`, so `alembic stamp head` does the same thing. After that, use `alembic upgrade head` like everyone else.

`python -m app.migrate` is safe on any database: on a new one it simply runs `alembic upgrade head`. The scripts in `scripts\` use it.

**Changing the tables.** Edit `backend/app/models.py`, then in `backend` run `alembic revision --autogenerate -m "describe the change"`, read the generated file in `migrations\versions`, and apply it with `alembic upgrade head`. `alembic check` tells you whether the models and migrations still match.

Start the API:

```powershell
uvicorn app.main:app --reload --port 8000
```

Leave this window open. Check it in the browser:

- http://localhost:8000/api/health shows `{"status":"ok"}`
- http://localhost:8000/docs shows every endpoint, and you can try them there

## Part 6: Start the frontend (React)

Open a **second** PowerShell window:

```powershell
cd C:\dev\bi-report-platform\frontend
npm install
npm run dev
```

Open http://localhost:5173.

**How the frontend connects to the backend:** the React code calls relative URLs like `/api/auth/login`. In development, `frontend/vite.config.ts` forwards every `/api` call to `http://127.0.0.1:8000`. That means no CORS problems and no hard-coded server addresses in the code. The login token is attached to every call in `frontend/src/api/client.ts`.

## Part 7: Sign in and try it

| Role | Email | Password |
|---|---|---|
| Manager | manager@example.com | Manager@123 |
| User | user@example.com | User@123 |

The login page shows these as one-click buttons in development only. **Change both passwords** (Users and access, then Reset password) before anyone else uses the app, or delete the accounts and create real ones.

A good first run:

1. Sign in as the **user**. Ask "Show monthly revenue by region for Q1 2024 and the top 5 products".
2. On the review screen, click **Measure** and switch to gross revenue. The numbers re-run.
3. Click **Looks right, build the report**. Change the chart to Stacked, move sections, and click **Publish**.
4. In the viewer, filter by region. Click **Download PDF** to save it.
5. Ask "Show customer churn by signup cohort" to see the failure screen.
6. Sign out, sign in as the **manager**, open **Users and access**, and add a real person.

## Part 8: Every day after setup

```powershell
.\scripts\start-dev.ps1
```

Or by hand: `docker compose up -d`, then the backend window (`cd backend`, `.\.venv\Scripts\Activate.ps1`, `alembic upgrade head`, `uvicorn app.main:app --reload --port 8000`) and the frontend window (`cd frontend`, `npm run dev`). Both reload automatically when you save a file. `alembic upgrade head` applies any new migrations that came with an update and does nothing otherwise.

If your database was set up before this project used Alembic, run `python -m app.migrate` once in `backend` (see Part 5) before anything else. `start-local.bat` and the scripts do this for you.

To stop: press Ctrl+C in both windows, then `docker compose stop`.

To reset the database completely (deletes all users and reports): `docker compose down -v`, then `docker compose up -d`, and in `backend` run `alembic upgrade head` and `python -m app.seed`.

## Part 9: Connect your own databases

The app database (users, reports, templates, connections) is the one in `DATABASE_URL`. The databases you report on are added in the app, under **Manage > Connections** (managers only). Supported types: PostgreSQL, MySQL or MariaDB, SQL Server and SQLite.

**One-time setup**

1. Install the drivers: in `backend` with `.venv` activated, run `pip install -r requirements.txt` (adds `cryptography`, `pymysql` and `pyodbc`).
2. Create the key that encrypts saved connection passwords:
   ```powershell
   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ```
   Add it to `backend\.env` as `CONNECTIONS_KEY=...` and restart the backend. **Keep a copy somewhere safe and separate from database backups.** Without it, saved passwords can't be read, and you'll have to re-enter them.
3. For SQL Server, install **Microsoft ODBC Driver 18 for SQL Server** on the machine that runs the backend.

**Adding a connection:** click **Add connection**, pick the database type, fill in the server, database and account, and click **Test connection**. After saving, click **Choose tables** to pick which tables and views users may ask about. Leave out tables with personal or sensitive data. Passwords are encrypted with the key above and never sent back to the browser. Users only ever see connection names.

**Always use a read-only account.** Ask each database owner for one:

| Database | Read-only account |
|---|---|
| PostgreSQL | `CREATE ROLE report_reader LOGIN PASSWORD '...'; GRANT CONNECT ON DATABASE company_db TO report_reader; GRANT USAGE ON SCHEMA public TO report_reader; GRANT SELECT ON ALL TABLES IN SCHEMA public TO report_reader; ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO report_reader;` |
| MySQL or MariaDB | `CREATE USER 'report_reader'@'%' IDENTIFIED BY '...'; GRANT SELECT ON reporting.* TO 'report_reader'@'%';` |
| SQL Server | `CREATE LOGIN report_reader WITH PASSWORD = '...';` then in the database: `CREATE USER report_reader FOR LOGIN report_reader; ALTER ROLE db_datareader ADD MEMBER report_reader;` |
| SQLite | Make the database file read-only for the Windows account that runs the backend. |

Reports still use the sample `sales` table for now. Asking questions against your connections is week 2 of the build plan (schema index, dialect-aware SQL).

### IBM OpenPages

OpenPages is connected through its REST API, not its database: questions become OpenPages Query Service SQL
(`GET /grc/api/query`), with object types and fields in brackets (`SELECT [SOXIssue].[Name] FROM [SOXIssue]`) and
joins along the object hierarchy (`JOIN [SOXBusEntity] ON CHILD([Finding])`). Results respect the account's
OpenPages permissions, so use an account whose role can only read.

1. **Connections > Add connection > IBM OpenPages.** Enter the server address or its `/grc/api` URL.
2. Pick the **Sign-in type**:
   - **Basic Auth**: username and password.
   - **OAuth 2.0 client credentials** (OpenPages 9.1+): token URL, client ID and client secret.
   - **MP-JWT**: paste the token; paste a new one when it expires.
   - **IBM Cloud IAM**: an IBM Cloud API key (the token URL defaults to `https://iam.cloud.ibm.com/identity/token`).
   - **Client certificate / mutual TLS**: the certificate and private key (PEM), optionally with a username and password.
   Passwords, secrets, tokens, API keys and private keys are stored encrypted and never shown again.
3. Optionally set a **default audit** (ID and/or name): questions that don't name an audit are answered for it.
4. **Test connection** signs in and lists the object types. Then **Choose tables** picks the object types people may
   query (SOXRisk, SOXIssue, Finding...).

The AI model gets the OpenPages SQL rules and each chosen type's fields (with their allowed values), read from
`/grc/api/types`. Every query is checked before it runs: one SELECT only, chosen object types only, no subqueries,
UNION, comments or LIMIT (rows are capped instead). Dashboards, filters, auto-refresh and Excel export work the
same as for databases; filter values are written into the query as quoted text, because OpenPages has no bound
parameters.

**OpenPages dashboard templates.** Templates includes six built-in OpenPages dashboards: Controls effectiveness,
Issues and remediation, Audit findings, Audit programme, Risk and KRI monitor, and Policies and obligations. Click
one, choose the OpenPages connection, and **Build dashboard** makes a draft dashboard of ready-written queries (no AI
model), with filters such as control type or finding status. Each chart needs its object type shared on the
connection (SOXControl, SOXIssue, Finding, AuditProgram, SOXRisk, KeyRiskIndicator, Policy, Obligation); charts that
can't run are left out and listed. They use the standard OpenPages field groups (OPSS-Ctl, OPSS-Iss, OPSS-Finding...).

**OpenPages SQL limits** (seen on OpenPages 9.x and enforced before a query is sent): no `AS` aliases (a count comes
back as `Count_Resource ID`), COUNT is the only function and works on one object type only (no JOIN in that query),
no DISTINCT, SUM, MIN, MAX, date functions, subqueries or LIMIT, and no sorting on enum fields. Joined fields with
the same name come back as, for example, "AuditProgram Name" and "Finding Name".

## Chat with your data and AI dashboards

The Ask box on the home page has two modes, and a **Database** picker next to the **AI model** picker:

- **Chat with the data** opens the chat page (also in the sidebar as **Chat with data**). Ask anything about the chosen database: the AI model writes the SQL, the app checks and runs it, and you get a short answer, a chart, the rows and the SQL. Follow-up questions ("and by month?") use the earlier turns. Questions that don't need data ("which tables can I ask about?") are answered directly. **Pin** answers and **Save as report** to keep them as a dashboard.
- **Chat history:** every chat is saved as you go (each question with its answer, SQL, rows and chart, or its error) and listed under **History** on the chat page, newest first. Open one to read it or carry on; follow-up context comes from the saved turns. Chats are named after their first question; rename or delete them from the list. Each person sees only their own chats. Saved chats live in the `chat_conversations` and `chat_messages` tables (migration `0003_chat_history`; run `python -m app.migrate` after updating).
- **Build a report** with an AI model plans a dashboard of 4 to 6 charts from the chosen database (KPI tiles first, then breakdowns). Optional **parameters** (date range, filter such as `region = North`) are applied to every chart. The new dashboard opens as a draft, where you can rename charts, change chart types, reorder, remove, **add a chart by asking**, and publish with a category. With a template, or without an AI model, **Build a report** makes the classic sales report as before.

**Databases you can choose:** "Sample sales data" (the `sales` table in the app database) and every connection that has tables chosen under **Manage > Connections > Choose tables**. People only ever see connection names.

**Safety:** the model only writes SQL; it never runs anything. Every query is checked before it runs (`backend/app/sql_guard.py`, using sqlglot): exactly one SELECT, only the chosen tables, no writes anywhere in the statement, no row locks, no file, sleep or remote-server functions, and a 500-row limit. It then runs read-only with a 15-second timeout (PostgreSQL and SQLite enforce read-only in the database; for MySQL and SQL Server rely on the read-only account from Part 9). If a query fails, the error goes back to the model for up to 3 tries in total. Saved dashboards re-run their saved SQL each time they open, checked again against the tables allowed at that moment; no AI is used to show them.

**Dashboard filters:** while editing a dashboard, add filters under **Filters**: a **Date range** (for example "Order date") or a **Category** (for example "Region"). When you add one, the AI model picks the matching column in each chart's tables, once; the choice is saved with the report, and **Map again** asks again (for example after adding charts). Viewers then get a filter bar above the charts: two dates for a date range (the end date counts in full), and a list of values for a category. Applying a filter uses no AI: each mapped table in a chart's saved SQL is replaced with a subquery that keeps only matching rows, with the dates and values sent as bound parameters (never written into the SQL), and the result is checked by `sql_guard` again. Because the table is filtered rather than the chart's output, KPI totals are filtered too. A chart whose tables have no matching column shows **Not filtered**.

**Result cache:** each chart's result is kept for 15 minutes (per connection version, SQL and filter values), so opening a dashboard again, or switching back to an earlier filter, doesn't query the database again. The filter bar says when the data was fetched; **Refresh** runs every query again now. Editing a connection starts fresh. The cache is in the backend's memory, so restarting the backend clears it.

**Excel export:** **Download Excel** in the dashboard viewer gives an `.xlsx` file with an **About** sheet (data source, filters applied, which charts each filter didn't apply to) and one sheet per chart with its rows (at most 500), using the filters currently chosen. Text from the database is always written as text, never as a formula.

**What the model sees:** the question, the last few chat turns, the chosen tables' columns, the values of short text columns (at most 12 distinct values, such as regions or statuses; never names or emails), and up to 20 result rows to explain an answer. With a cloud model (Claude, or an Ollama `:cloud` model) this leaves your network; use a local Ollama model if it must not.

**Tested with:** Gemma 4 31B through Ollama on PostgreSQL. MySQL and SQL Server connections use the same code with their own SQL dialects, but haven't been tried against a real server yet.

## Try it on demo data

`python -m app.demo_shop` (in `backend`, with `.venv`; or `.\.venv\Scripts\python.exe -m app.demo_shop`) builds a demo business database for a small electronics retailer: about 450 customers, 22 products, 9,000 orders with 15,000 order lines, and monthly revenue targets per region, from January 2024 up to today. It goes in a separate schema, `demo_shop`, inside the app database, and the command adds a ready-to-use **Demo shop** connection on the Connections page limited to those tables. Pick **Demo shop** as the database in the Ask box or on the chat page. Things to try:

- Chat: "Which product category earned the most revenue in 2025?", then "Show monthly revenue for that category", or "How did each region do against its target last month?"
- Build a report: "Sales dashboard for this year: revenue, orders, top products and regions", then set **Auto-refresh**.
- See auto-refresh pick up new data: `python -m app.demo_shop --add-orders 25` adds 25 orders dated today. The dashboard keeps its saved numbers until the next scheduled refresh or **Refresh**.
- Run `python -m app.demo_shop` again to rebuild the data from scratch, or `python -m app.demo_shop --remove` to delete the schema and the connection.

The demo tables have **column comments** (for example "discount is a money amount, not a percentage"), and the AI model reads them. Add comments like these to your own databases (`COMMENT ON COLUMN ...` in PostgreSQL) to tell the model what columns mean; it is the simplest way to get correct numbers. The model is also given today's date, so "this year" and "last month" work.

Because the app's database account can't create a separate database or login, the demo connection uses the app's own account. Queries are still checked (one SELECT on the demo tables only) and run in read-only transactions. For real databases, use a read-only account (Part 9).

## Editing and duplicating reports

Everything the AI builds can be changed. Owners and managers have these on a dashboard:

- **Edit a chart** with the pencil on the chart, in edit mode or straight from the preview (changes from the preview save immediately). The chart editor has a live preview and four tabs. **Chart**: title, description, chart type, which columns go on X and Y, width on the dashboard (auto, quarter, third, half, two thirds or full) and height (short, medium, tall, extra tall, or any size in pixels). **Style**: colour (or **Use this colour for every chart**), number format (short, full, currency with your symbol, percent), order (largest or smallest first), show values on the chart, legend, horizontal bars, and stacking when a chart has several series. **Data (SQL)**: change the query and **Run** it; it's checked like every query (one SELECT on the shared tables, read-only). **Ask AI to change it**: describe the change, for example "only completed orders, by week" or "show it by sales channel".
- **Edit mode** also has rename and **Add a chart by asking**; each tile's **⋯** menu has Duplicate, Move earlier/later and Remove. A removed chart can be brought back with **Undo** in the message that appears. Changes save automatically, and a change made just before leaving the editor is still saved.
- **Full screen** (on the report and in the editor) shows the report on the whole screen without the sidebar; Esc leaves. Dashboards use the full width of the window.
- **Card colours**: in edit mode, each tile's palette button sets a **header colour** (a coloured band behind the title) and a **card background**, or resets them; **Use on every card** applies them to the whole dashboard. The same choices are in the chart editor's Style tab under **Card**, with a live preview. Text switches to white or dark, whichever reads better, and charts on a dark card get light axis text.
- **Drag and drop**: hold a tile's grip handle (the six dots before its title) and drop it on another tile. Dragging down puts it after that tile, dragging up puts it before.
- **Resize**: drag a tile's bottom-right corner. Sideways changes the width (quarter, third, half, two thirds, full), up and down changes the height in 40 px steps, and a label shows the size as you drag. With the corner focused, the arrow keys do the same. Number tiles and headings change width only. On narrow screens every tile is full width. Classic reports (from **Ask a question**) resize the same way: drag a section's corner, or pick **Width** (and **Height** for the revenue chart) in the section settings on the right.
- **Headings and notes**: **Add a heading or note** adds a text tile to split the dashboard into sections. Drag it where you want it; it has no query, so filters, refresh and Excel export skip it.
- **Filters**: the AI can find each chart's column (**Add filter**), or choose them yourself with **Add a custom filter**. Pick a column once and every chart reading the same table gets it too. Charts left as "Not filtered" ignore the filter. **Edit** on an existing filter changes its columns.
- **Duplicate** (on the report, and in the Reports list) copies any report you can see, AI dashboard or classic, into a new draft of your own with every chart, filter and setting. Change the copy freely; the original stays as it was. Copies start without a category or auto-refresh.

## Auto-refresh

Any report, AI dashboard or classic sales report, can refresh itself on a schedule: every 15 minutes, every hour, every 6 hours, daily at a time, or weekly on a day at a time. Times are the server's time. Set it with **Set up auto-refresh** under the report's title (owner or manager).

On each refresh the report runs its saved queries against its database, with no AI, and saves the results as a snapshot. Everyone who opens the report sees the latest snapshot, so the numbers match for everyone and the report opens without querying the database. The report shows when it was last refreshed and when it refreshes next. **Refresh** runs the queries straight away and saves the result for everyone. Setting dashboard filters, or changing a classic report's period or region, queries live as before. Editing a dashboard's charts refreshes it the next time it opens.

The scheduler runs inside the API process (`backend/app/refresh.py`) and checks for due reports every 30 seconds. No extra services are needed, but **the backend must be running for refreshes to happen**. A refresh missed while it was stopped runs soon after it starts again. If you run more than one API process, each due report is still refreshed only once; set `SCHEDULER_ENABLED=false` in `.env` on the extra processes if you prefer one scheduler. How long snapshots are kept is set per report (see Report history below). If a refresh fails (database down, connection removed), the report says so and keeps showing the last good data.

### Report history

With auto-refresh on, a dashboard keeps its refreshes for **Keep history for** in the auto-refresh settings: only the
latest 10, 30 days (the default), 90 days or 1 year. Older history is thinned to one refresh per hour after a day and
one per day after a week, so storage stays small. Run `python -m app.migrate` after updating (migration
`0005_report_history`).

- **Compare with** (next to the filters): previous refresh, 1 day, 1 week or 1 month ago, or the start of the quarter.
  If history doesn't go back that far, the oldest kept refresh is used, and its date is shown.
- **Number tiles** show the change, such as "▲ 22.7K (+1%) since 23 Oct, 10:52", and a small trend line. In the
  chart editor's Style tab, set whether going up is good (green), bad (red) or neither (grey).
- **Bar, line and area charts** draw the earlier refresh beside the current values (faded bars or dashed lines).
  **Pie charts** list the biggest changes under the chart.
- **Tables** show what changed: new rows, rows gone, and changed values for rows with the same first column
  ("Store: Orders 2,744 → 2,746").
- **History** (the clock button on a chart) shows the chart over all kept refreshes: one line for a number, or one
  line for each of the 6 largest categories.

History compares the unfiltered dashboard, so comparisons are hidden while filters are set. Editing a chart's query
starts its history afresh. Classic sales reports keep snapshots for their retention but don't show history yet.
API: `GET /api/reports/{id}/history` and `GET /api/reports/{id}/history/compare?at=...`.

## AI models

Managers add the AI models people can use under **Manage > AI models**. When someone asks a question, the **AI model** picker in the Ask box lists every model that is turned on, plus "Built-in engine (no AI)". The default model is preselected, and each browser remembers the last choice.

| Where the model runs | What you need |
|---|---|
| **Ollama (local)** | [Ollama](https://ollama.com) on this or another server, and a model pulled into it, e.g. `ollama pull qwen2.5-coder:14b`. Questions never leave your network. **Find installed models** lists what Ollama has. Models ending in `:cloud` run on ollama.com, not locally, and may need an Ollama plan. |
| **Claude (Anthropic API)** | An API key from console.anthropic.com. Suggested models: `claude-opus-5-5` (most capable), `claude-sonnet-5-5`, `claude-haiku-5-5` (fastest, cheapest), `claude-fable-5-1`. Usage is billed to that Anthropic account. For Opus, Sonnet and Fable, if Claude's safety checks decline a request, the API retries on a fallback model automatically (server-side fallback). |
| **OpenAI-compatible server** | Any server with the `/v1/chat/completions` API: LM Studio (`http://localhost:1234/v1`), vLLM, llama.cpp server, LocalAI, or a hosted service. API key only if the server needs one. |

API keys are encrypted with `CONNECTIONS_KEY` (see Part 9) and never sent back to the browser. Use **Test** to check a model answers, **Make default** to preselect it, and **Turn off** to hide it from the picker.

**What the model does today:** it reads the question and picks the period, measure and date column for the sales report. It never writes or runs SQL, so it can't read or change anything else. If a model can't be reached, the question is answered with the built-in engine and the review screen says so. If the model decides the data can't answer the question, the person sees the model's reason. Writing SQL against your own connections is week 2 of the build plan.

## Report categories

When you click **Publish** (or **Update published report**) in the editor, a dialog asks which category the report belongs in. Pick an existing one, choose "No category", or add a new category right there. The **Reports** page groups reports by category, with filter buttons and a search box at the top. Use **Manage categories** on that page to add, rename, recolour or delete categories. Deleting a category keeps its reports; they move to "No category".

Anyone can create a category. Only the person who created it, or a manager, can change or delete it. `python -m app.seed` adds three sample categories: Sales, Finance and Executive. The `reports.category_id` column is part of the baseline migration. A database from before Alembic that doesn't have it yet gets it from `python -m app.migrate` (see Part 5).

## Templates

A template is a saved question plus an optional report layout (which sections, chart type, colours, number format, top 3 or 5 products). Open **Templates** in the sidebar to create, edit, duplicate or delete them, or click **New template** on the home page. In the report editor, **Save as template** turns the report you are working on into a template with its current layout.

`python -m app.seed` also adds five sample templates (the list is in `backend/app/template_data.py`): four shared by the demo manager (Quarterly sales review, Executive snapshot, Holiday quarter (gross), Product leaderboard) and one private to the demo user (My regional table). Each one uses a question the phase 1 query engine can answer and shows a different layout. Running the seed again doesn't create duplicates.

Picking a template on the home page fills in its question; reports built from it start with its layout. Templates are private to their owner unless a manager shares them with everyone. The four starter templates are built in and are created automatically when the API starts (the `report_templates` table comes from the migrations, like every other table).

## Tests

The backend tests cover the role rules (users, reports, templates, categories) and connections. They use a throwaway SQLite database, built with the Alembic migrations, so they never touch the database in `.env`. In `backend` with `.venv` activated:

```powershell
pip install -r requirements-dev.txt
python -m pytest
```

## Project structure

```
bi-report-platform/
├── docker-compose.yml          PostgreSQL 16 + pgvector
├── scripts/
│   ├── setup-windows.ps1       one-time setup
│   └── start-dev.ps1           start everything
├── backend/
│   ├── requirements.txt
│   ├── .env.example            copy to .env
│   ├── alembic.ini             Alembic settings (the database address comes from .env)
│   ├── migrations/             env.py and versions/: one file per schema change
│   └── app/
│       ├── main.py             FastAPI app, CORS, routers
│       ├── config.py           reads .env
│       ├── database.py         SQLAlchemy engine and session
│       ├── models.py           User, Report, ReportCategory, ReportTemplate, Sale tables
│       ├── security.py         bcrypt passwords, JWT tokens
│       ├── deps.py             get_current_user, require_manager
│       ├── schemas.py          request and response shapes
│       ├── query_engine.py     question → SQL → result (phase 1 stub)
│       ├── connections/        engines per database type, password encryption
│       ├── ai/                 AI providers, question reading, chat and dashboard planning
│       ├── sql_guard.py        checks AI-written SQL before it runs
│       ├── datasources.py      sample data and connections: table descriptions, read-only runs
│       ├── migrate.py          alembic upgrade head, adopting pre-Alembic databases
│       ├── seed.py             demo accounts and sample data
│       └── routers/            auth, users, query, reports, categories, templates, connections, admin
│   └── tests/                  pytest: role rules and connections
└── frontend/
    ├── vite.config.ts          dev server and /api proxy
    └── src/
        ├── api/                axios client, endpoints, types
        ├── auth/               AuthContext (login state), RequireAuth (route guard)
        ├── layout/AppShell.tsx sidebar with role-based menu
        ├── components/         ReportBody, RevenueChart (ECharts), DataTable, Toast, Icon
        ├── lib/                number formatting, insights, report helpers
        ├── pages/              Login, Home, AskFlow, ReportEditor, ReportViewer,
        │                       Chat, BuildDashboard, MyReports, Templates, Connections, AIModels, Users, Settings
        └── styles/app.css      design tokens and all styles
```

## API reference

| Method and path | Who | What it does |
|---|---|---|
| POST /api/auth/login | Anyone | Email and password in, token and user out |
| GET /api/auth/me | Signed in | The current user |
| POST /api/query/generate | Signed in | Question → understanding, SQL, result. Optional `model_id` picks the AI model |
| POST /api/query/run | Signed in | Re-runs a saved query with new filters (no AI) |
| GET/POST /api/reports | Signed in | List and create reports |
| GET/PUT/DELETE /api/reports/{id} | Owner or manager to change | Read, update, delete |
| POST /api/reports/{id}/publish | Owner or manager | Publish, optionally with `{"category_id": n}` |
| GET/POST /api/templates | Signed in | List templates (built-in, shared and your own) and create one |
| GET/POST /api/connections | Manager | List connections (never with passwords) and add one |
| PUT/DELETE /api/connections/{id} | Manager | Change a connection, choose its allowed tables, or delete it |
| POST /api/connections/test, POST /api/connections/{id}/test | Manager | Test unsaved form details, or a saved connection |
| GET /api/connections/{id}/tables | Manager | Tables and views the connection's account can see |
| GET /api/connections/available | Signed in | Connection names and types only |
| GET/POST /api/ai-models | Manager | List AI models (never with API keys) and add one |
| PUT/DELETE /api/ai-models/{id} | Manager | Change, turn on or off, make default, or delete a model |
| POST /api/ai-models/test, POST /api/ai-models/{id}/test | Manager | Test unsaved form details, or a saved model |
| POST /api/ai-models/discover | Manager | Models available on an Ollama, OpenAI-compatible or Anthropic account |
| GET /api/ai-models/available | Signed in | Models that are turned on, for the picker (names only) |
| GET /api/sources | Signed in | Databases you can chat with (names and types only) |
| POST /api/assistant/chat | Signed in | One chat question: answer, SQL, rows and chart |
| GET/POST /api/chats | Signed in | Your saved chats, and start a new one |
| GET/PATCH/DELETE /api/chats/{id} | Chat owner | Open (with all messages), rename or change model, delete |
| POST /api/chats/{id}/messages | Chat owner | Ask in a saved chat; the turn is saved, answer or error |
| POST /api/assistant/dashboard | Signed in | Plan, run and save a dashboard as a draft report |
| POST /api/assistant/widget | Signed in | One chart from a question (add a chart by asking) |
| POST /api/assistant/save | Signed in | Save pinned chat answers as a dashboard report |
| POST /api/reports/{id}/data | Can see the report | Run a dashboard's saved queries (no AI), with filter values; cached 15 minutes unless `refresh` |
| POST /api/reports/{id}/export | Can see the report | The dashboard as an Excel file, one sheet per chart |
| POST /api/reports/{id}/filters/map | Owner or manager | AI model maps a new filter to a column per chart (not saved) |
| GET/POST /api/categories | Signed in | List report categories (with report counts) and create one |
| PUT/DELETE /api/categories/{id} | Creator or manager | Rename, recolour or delete a category (its reports become uncategorised) |
| PUT/DELETE /api/templates/{id} | Owner or manager (built-in: manager) | Change or delete a template |
| GET/POST /api/users, PATCH /api/users/{id} | Manager | Manage people and roles |
| GET /api/admin/usage | Manager | Usage counts and model settings |

## Next phases

**Phase 2, the real AI step.** Replace `interpret_prompt` in `backend/app/query_engine.py`:

1. `docker exec -it bi_postgres psql -U bi -d bi_db -c "CREATE EXTENSION IF NOT EXISTS vector;"`
2. Install Ollama for Windows from https://ollama.com, then `ollama pull qwen2.5-coder:14b` and `ollama pull nomic-embed-text`.
3. Add `pgvector`, `sqlglot`, `httpx` and `langgraph` to `requirements.txt`.
4. Index table and column descriptions (plus sample values) into a pgvector table, retrieve the top matches for each question, ask the model for SQL, validate it with sqlglot (SELECT only), run `EXPLAIN`, and send errors back to the model up to 3 times.
5. Return the same dict shape as `run_query`, and the frontend keeps working unchanged.

**Phase 3, operations.** Add scheduled emails with Celery and Redis, server-side PDF export with Playwright, an audit log, and single sign-on with Keycloak if your company needs it.

**Before production.** Serve the built frontend (`npm run build` creates `frontend/dist`) behind a web server such as Nginx or IIS, set `VITE_API_URL` and `CORS_ORIGINS` to the real addresses, use HTTPS, and keep `.env` out of Git (it already is, through `.gitignore`).

## Troubleshooting

| Problem | Fix |
|---|---|
| `running scripts is disabled on this system` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, then open a new window |
| `py` is not recognised | Reinstall Python and tick "Add python.exe to PATH", or use `python` instead of `py -3.12` |
| `docker: error during connect` | Docker Desktop is not running. Open it and wait for "Engine running" |
| Port 5432 already in use | You have PostgreSQL installed on Windows. Change the port line in `docker-compose.yml` to `"5433:5432"` and use `localhost:5433` in `DATABASE_URL` |
| Login page says "Can't reach the server" | The backend window isn't running or crashed. Check its output and that http://localhost:8000/api/health works |
| `password authentication failed for user "bi"` | The Docker volume was created with a different password. Run `docker compose down -v` and start again (this deletes data) |
| `RuntimeError: The database has no migrations applied` when the API starts | Run `alembic upgrade head` in `backend` (new database) or `python -m app.migrate` (database from before Alembic) |
| `alembic upgrade head` fails with `relation "app_users" already exists` | The database was created before Alembic. Run `python -m app.migrate` instead (Part 5) |
| Everything shows "Session expired" | `JWT_SECRET` changed, so old tokens are invalid. Sign in again |
| `npm install` is very slow or fails | Check your company proxy settings, or run `npm config set registry https://registry.npmjs.org/` |

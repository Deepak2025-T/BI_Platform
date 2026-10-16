# DTE — AI-Powered ETL + Prompt-to-BI Platform (MVP)

FastAPI + React. PostgreSQL is the active target; pgvector holds the RAG index. LLM mode is switchable in the UI:
**Ollama** (open source, self-hosted) or **Claude** (client-paid API key).

```
backend/   FastAPI app — connectors, RAG, NL→SQL pipeline, report builder, ETL, forecasting
frontend/  React (Vite) — Report Builder, drag-drop Designer, ETL wizard, Forecast, Connections, Model config
deploy/    DB init + nginx config
docker-compose.yml   postgres+pgvector, ollama, backend, frontend
```

## Quick start (Docker)

```bash
docker compose up -d --build
docker compose exec ollama ollama pull qwen2.5-coder:7b      # SQL model
docker compose exec ollama ollama pull nomic-embed-text      # embeddings (768-d)
docker compose exec backend python sample/seed_finance.py postgresql+psycopg://postgres:postgres@db:5432/finance_demo
```

Open http://localhost:8080 → **Connections** → add `db:5432 / finance_demo / postgres / postgres` → **Index schema** →
**Report Builder** → type a prompt, pick a template → **Generate report** → customize in Designer → **Publish**.

## Local dev

```bash
# backend
cd backend && pip install -r requirements.txt && cp .env.example .env
python sample/seed_finance.py                     # demo finance DB (24 months)
uvicorn app.main:app --reload                     # http://localhost:8000/docs
pytest -q tests/                                  # 11 end-to-end tests (real Postgres, scripted fake LLM)

# frontend
cd frontend && npm install && npm run dev         # http://localhost:5173 (proxies /api → :8000)
```

## How a prompt becomes a report

1. **ReportPlanner** (fast model) turns the prompt + template slots into one focused question per widget.
2. For each widget: **IntentAgent** → **pgvector retrieval** (top-k tables + FK neighbours, glossary, verified examples)
   → **SQLAgent** writes dialect SQL → **validator** (sqlglot: one statement, SELECT-only, row cap; then `EXPLAIN`)
   → on failure the error goes back to the LLM (max 3 fixes) → **read-only execution** with statement timeout.
3. Chart type is inferred from column roles (time / measure / dimension) or forced by the template slot; KPIs get
   latest-vs-previous change. **LayoutAgent** writes 2 insight bullets per widget.
4. Saved reports store SQL + layout + style only and re-query on open, so they stay live.
5. **Publish** stores each widget's question→SQL pair in pgvector as a few-shot example (learning loop).

## ETL (Accounts / Finance)

Upload → **Extract** (Excel/CSV/JSON/XML via pandas; DOCX/PPTX tables; PDF tables incl. borderless; images via
Tesseract OCR with word-box table rebuild; text-only docs → LLM field extraction) → **AI mapping** to the target table
(heuristic fallback) with editable transforms → **Transform** (type coercion, date parsing, ₹/comma cleanup, FK lookup by
name/code) → **Validate** (required columns, duplicates in file and DB, Dr = Cr, untaxed + tax = total, paid ≤ total)
→ **Load** in one transaction (append / upsert / replace) **directly** or via **REST API**. External systems can also push
rows to `POST /api/etl/load-records`.

## Connectors

| Dialect | Status | Driver |
|---|---|---|
| PostgreSQL | active | psycopg |
| MySQL, SQL Server, Oracle, IBM Db2, SQLite | wired, beta | see `requirements-extra.txt` |

All go through SQLAlchemy, with dialect-aware `EXPLAIN` and row limits. Passwords and API keys are Fernet-encrypted
with `SECRET_KEY`.

## Model configuration notes

- Ollama defaults: `qwen2.5-coder:7b` (SQL), `nomic-embed-text` (embeddings). `sqlcoder` or a 14b coder model improves accuracy.
- Claude: the strong model writes SQL/mappings, the fast model handles intent and insights. Model IDs are editable in
  the UI — check Anthropic's models page for current IDs.
- Embeddings always run on Ollama (Claude has no embedding endpoint). If Ollama is down the app falls back to hashed
  embeddings so it keeps working, with lower retrieval quality.

## Next steps (not in this MVP)

Auth + RBAC (row caps, PII masking per role), scheduled ETL from S3/SFTP/DB sources, multi-domain target schemas,
report sharing links, and per-tenant model/billing settings.

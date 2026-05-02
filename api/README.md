# BL/GL Intelligence — API Service

FastAPI + Claude Agent SDK service powering the FASB ASU compliance platform.
Replaces the legacy Flask service in `gl_intelligence/api/server.py` (kept
running during the migration; will be retired in Phase 4).

## Status

| Phase | Scope | Status |
|---|---|---|
| 0 | Supabase migrations (review state + RLS) + BigQuery mirror DDL + promotion worker | ✅ Shipped |
| 1 | Vertical slice — Tax classifier (Agent SDK + tools + review UI + audit) | ✅ Shipped |
| 2 | ETR bridge agent + tax disclosure narrative + ASU 2023-09 compliance harness | 📅 Planned |
| 3 | DISE agents (mapping, recon, anomaly, disclosure) | 📅 Planned |
| 4 | Platform polish + retire Flask | 📅 Planned |

The full plan lives at `~/.claude/plans/woolly-petting-journal.md`.

## Run locally

### Prerequisites

- Python 3.11+
- A Supabase project (this repo points at `https://uljbbwfnldikdathtkbh.supabase.co`)
- `gcloud auth application-default login` for BigQuery access
- An `ANTHROPIC_API_KEY` or AWS Bedrock credentials

### Apply migrations

```bash
# Supabase — via SQL editor or supabase-cli
supabase db push    # reads migrations/supabase/*.sql

# BigQuery — via bq CLI
bq query --use_legacy_sql=false < migrations/bigquery/0001_mirror_tables.sql
```

### Install + run the API

```bash
cd api/
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then fill in SUPABASE_*, ANTHROPIC_API_KEY, etc.
uvicorn src.main:app --reload --port 8001
```

### Run the Next.js dashboard

```bash
cd ../web/
npm install
npm run dev      # http://localhost:3000
```

The Supabase URL + publishable key are already in `web/.env.local`.

## End-to-end smoke test

1. Sign up a user in Supabase, assign them a `controller` role on a company:
   ```sql
   insert into role_assignments (user_id, company_id, role)
   values ('<auth.users.id>', '<companies.id>', 'controller');
   ```
2. Open <http://localhost:3000/dashboard/tax/classifier>.
3. Click **Start** in the agent run pane.
4. Watch the SSE stream as Claude calls each tool. Pending rows appear in
   the queue. Click a row → Approve / Override / Reject.
5. Verify the audit log:
   ```sql
   select event_type, gl_account, actor_type, payload
   from audit_log
   where module = 'tax'
   order by event_timestamp desc
   limit 20;
   ```

## Architecture overview

```
Next.js 16 dashboard (web/)
        │  Bearer JWT
        ▼
FastAPI (api/, port 8001)
   ├─ /api/cortex/*    SAP/Oracle/SFDC reads (read-only)
   ├─ /api/tax/*       review queue + approve/reject + classifier kickoff
   ├─ /api/dise/*      placeholder — Phase 3
   └─ /api/sessions/*  SSE stream + cancel + status
        │
        ├─ Supabase (system of record for review state + RLS + audit log)
        └─ BigQuery (Cortex GL data + nightly mirror of approved mappings)
```

### What lives where

- **`src/agents/tax/classifier_agent.py`** — Claude Agent SDK strategy, system
  prompt, hook + tool wiring.
- **`src/agents/tax/tools.py`** — 4 decomposed tools exposed via in-process
  MCP server: `get_unmapped_tax_accounts`, `lookup_similar_approved_mappings`,
  `lookup_asc_citation`, `write_pending_mapping`.
- **`src/agents/tax/categories.py`** — 11 ASC 740 categories, citations, the
  8 ASU 2023-09 rate-recon categories. Single source of truth — TS mirror in
  `web/lib/tax-categories.ts`.
- **`src/agents/common/hooks.py`** — `PostToolUse` audit hook + `UserPromptSubmit`
  state-prefix injection (memory_injection pattern from claude-code-sdk-1).
- **`src/session_management/`** — per-job worker registry. Phase 1 uses a
  simple per-request session; Phase 2 will add 1-hour reuse + replay buffer.
- **`src/db/audit.py`** — single helper for append-only audit log writes.
- **`infra/promotion_worker.py`** — Supabase → BigQuery MERGE job. Run once
  or `--watch` (default 5-minute interval).

## Required env vars

| Var | Purpose |
|---|---|
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Used when forwarding user JWTs |
| `SUPABASE_SERVICE_ROLE_KEY` | Used by audit log + agent writes |
| `SUPABASE_JWT_SECRET` | HS256 secret for JWT verification |
| `ANTHROPIC_API_KEY` | Or `AWS_*` for Bedrock |
| `BQ_DATA_PROJECT` | Default `diplomatic75` |
| `BQ_BILLING_PROJECT` | Default `trufflesai-loans` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to BQ service account JSON |

## Verification

- TypeScript: `cd ../web && npx tsc --noEmit`
- Python syntax: `python3 -c "import ast; ..."` (see CI workflow)
- Tools (deterministic, no LLM): `pytest tests/agents/tax/test_tools.py`

## Migration from Flask

The legacy `gl_intelligence/` Flask app continues to serve the static-HTML
dashboards and the old single-shot agent endpoints. Each module migration
replaces a slice of those routes with FastAPI equivalents:

- Phase 1 (this) — `/api/tax/classifier/*` migrated.
- Phase 2 — `/api/tax/etr-bridge/*` and `/api/tax/disclosure` migrated.
- Phase 3 — DISE routes migrated.
- Phase 4 — Flask deleted, static HTML deleted, single FastAPI service.

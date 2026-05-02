-- ============================================================
-- BL/GL Intelligence Platform — Review State (Supabase / Postgres)
-- Migration: 0001_review_state.sql
-- ============================================================
-- Translates the BigQuery review tables (FASB DISE ASSETS/agent_tables_ddl.sql)
-- into a Postgres schema with:
--   - Enum types for status / confidence / materiality
--   - JSONB for similar_accounts (instead of STRING)
--   - B-tree indexes (instead of CLUSTER BY)
--   - pg_trgm for similarity matching (replaces local Jaccard in mapping_agent.py)
--   - RLS by company_id with controller / reviewer / cfo / auditor roles
--
-- The Supabase project for this platform is uljbbwfnldikdathtkbh.
-- Run via Supabase SQL editor or `supabase db push`.
-- ============================================================

-- ── Extensions ─────────────────────────────────────────────────────────
create extension if not exists "uuid-ossp";
create extension if not exists "pg_trgm";    -- description similarity search
create extension if not exists "pgcrypto";


-- ── Enum types ─────────────────────────────────────────────────────────
do $$ begin
  create type mapping_status as enum ('PENDING', 'APPROVED', 'REJECTED', 'OVERRIDDEN');
exception when duplicate_object then null; end $$;

do $$ begin
  create type confidence_label as enum ('HIGH', 'MEDIUM', 'LOW');
exception when duplicate_object then null; end $$;

do $$ begin
  create type materiality_flag as enum ('HIGH', 'MEDIUM', 'LOW');
exception when duplicate_object then null; end $$;

do $$ begin
  create type tax_category as enum (
    'current_federal', 'current_state', 'current_foreign',
    'deferred_federal', 'deferred_state', 'deferred_foreign',
    'deferred_tax_asset', 'deferred_tax_liab',
    'pretax_domestic', 'pretax_foreign',
    'not_tax_account'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type dise_category as enum (
    'Purchases of inventory',
    'Employee compensation',
    'Depreciation',
    'Intangible asset amortization',
    'Other expenses'
  );
exception when duplicate_object then null; end $$;

do $$ begin
  create type dise_caption as enum ('COGS', 'SG&A', 'R&D', 'Other income/expense');
exception when duplicate_object then null; end $$;

do $$ begin
  create type platform_role as enum ('controller', 'reviewer', 'cfo', 'auditor');
exception when duplicate_object then null; end $$;

do $$ begin
  create type anomaly_priority as enum ('P1', 'P2', 'P3');
exception when duplicate_object then null; end $$;

do $$ begin
  create type anomaly_alert_status as enum ('open', 'acknowledged', 'resolved', 'dismissed');
exception when duplicate_object then null; end $$;


-- ── Companies & role assignments ───────────────────────────────────────
-- Multi-tenant from day 1. Every reviewable row is scoped to a company.
create table if not exists public.companies (
  id            uuid primary key default uuid_generate_v4(),
  code          text not null unique,                 -- e.g. 'C006'
  name          text not null,
  fiscal_year   text not null default '2025',         -- current open fiscal year
  statutory_rate numeric(5,4) not null default 0.21,  -- US federal default
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now()
);

create table if not exists public.role_assignments (
  user_id    uuid not null references auth.users(id) on delete cascade,
  company_id uuid not null references public.companies(id) on delete cascade,
  role       platform_role not null,
  granted_at timestamptz not null default now(),
  granted_by uuid references auth.users(id),
  primary key (user_id, company_id, role)
);

create index if not exists idx_role_assignments_user on public.role_assignments(user_id);
create index if not exists idx_role_assignments_company on public.role_assignments(company_id);


-- ── Helper: does the calling user have a role in this company? ─────────
-- Used by every RLS policy. SECURITY DEFINER so it can read role_assignments
-- without recursive RLS. STABLE so Postgres can hoist out of joins.
create or replace function public.has_company_role(
  p_company_id uuid,
  p_roles platform_role[]
) returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists(
    select 1
    from public.role_assignments
    where user_id = auth.uid()
      and company_id = p_company_id
      and role = any(p_roles)
  )
$$;

create or replace function public.user_has_company_access(p_company_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists(
    select 1
    from public.role_assignments
    where user_id = auth.uid()
      and company_id = p_company_id
  )
$$;


-- ── App config (per-company thresholds) ────────────────────────────────
create table if not exists public.app_config (
  company_id          uuid primary key references public.companies(id) on delete cascade,
  -- DISE thresholds
  dise_high_materiality_amount    numeric not null default 500000,
  dise_medium_materiality_amount  numeric not null default 100000,
  dise_recon_variance_threshold_pct numeric(5,2) not null default 20.00,
  dise_anomaly_p1_pct             numeric(5,2) not null default 100.00,
  dise_anomaly_p2_pct             numeric(5,2) not null default 50.00,
  dise_anomaly_p3_pct             numeric(5,2) not null default 25.00,
  dise_anomaly_min_amount         numeric not null default 100000,
  -- Tax thresholds
  tax_auto_approve_confidence     numeric(3,2) not null default 0.80,
  tax_jurisdictional_threshold_pct numeric(5,4) not null default 0.05,
  tax_state_majority_threshold_pct numeric(5,4) not null default 0.50,
  -- Bookkeeping
  updated_at  timestamptz not null default now(),
  updated_by  uuid references auth.users(id)
);


-- ── DISE: pending mappings ─────────────────────────────────────────────
create table if not exists public.dise_pending_mappings (
  id                  uuid primary key default uuid_generate_v4(),
  company_id          uuid not null references public.companies(id) on delete cascade,

  -- Account identity
  gl_account          text not null,
  description         text,
  posting_amount      numeric not null,
  fiscal_year         text not null,

  -- Agent decision
  suggested_category  dise_category,
  suggested_caption   dise_caption,
  suggested_citation  text,
  draft_reasoning     text,
  confidence_score    numeric(4,3),
  confidence_label    confidence_label,
  similar_accounts    jsonb not null default '[]'::jsonb,
  materiality_flag    materiality_flag,

  -- Workflow status
  status              mapping_status not null default 'PENDING',

  -- Human review (nullable until acted on)
  reviewed_category   dise_category,
  reviewed_caption    dise_caption,
  reviewed_citation   text,
  override_reason     text,
  reviewer            uuid references auth.users(id),
  reviewed_at         timestamptz,

  -- Agent metadata
  drafted_by          text not null,             -- e.g. 'GL_MAPPING_AGENT_v2'
  drafted_at          timestamptz not null default now(),
  model_version       text not null,
  prompt_version      text not null,

  unique(company_id, gl_account, fiscal_year, drafted_at)
);

create index if not exists idx_dise_pending_status on public.dise_pending_mappings(company_id, status, fiscal_year);
create index if not exists idx_dise_pending_materiality on public.dise_pending_mappings(company_id, materiality_flag, status);
create index if not exists idx_dise_pending_desc_trgm on public.dise_pending_mappings using gin (description gin_trgm_ops);


-- ── DISE: approved mappings (mirror of approved rows) ──────────────────
create table if not exists public.dise_approved_mappings (
  id                  uuid primary key default uuid_generate_v4(),
  company_id          uuid not null references public.companies(id) on delete cascade,
  pending_id          uuid references public.dise_pending_mappings(id) on delete set null,

  gl_account          text not null,
  description         text,
  posting_amount      numeric not null,
  fiscal_year         text not null,

  dise_category       dise_category not null,
  expense_caption     dise_caption not null,
  asc_citation        text,
  override_reason     text,

  reviewer            uuid references auth.users(id),
  reviewed_at         timestamptz not null default now(),
  promoted_to_bq_at   timestamptz,                -- set by BQ promotion worker

  unique(company_id, gl_account, fiscal_year)
);

create index if not exists idx_dise_approved_company_fy on public.dise_approved_mappings(company_id, fiscal_year);
create index if not exists idx_dise_approved_unpromoted on public.dise_approved_mappings(promoted_to_bq_at)
  where promoted_to_bq_at is null;
create index if not exists idx_dise_approved_desc_trgm on public.dise_approved_mappings using gin (description gin_trgm_ops);


-- ── TAX: pending mappings ──────────────────────────────────────────────
create table if not exists public.tax_pending_mappings (
  id                  uuid primary key default uuid_generate_v4(),
  company_id          uuid not null references public.companies(id) on delete cascade,

  gl_account          text not null,
  description         text,
  posting_amount      numeric not null,
  fiscal_year         text not null,
  account_type        text,                      -- expense | balance_sheet | income
  jurisdiction_hint   text,                      -- federal | state | foreign | domestic | <empty>

  tax_category        tax_category,
  tax_category_label  text,
  asc_citation        text,
  disclosure_table    text,                      -- 'Table A — ETR ...' / etc.
  draft_reasoning     text,
  confidence_score    numeric(4,3),
  confidence_label    confidence_label,
  similar_accounts    jsonb not null default '[]'::jsonb,

  status              mapping_status not null default 'PENDING',

  reviewed_category   tax_category,
  override_reason     text,
  reviewer            uuid references auth.users(id),
  reviewed_at         timestamptz,

  drafted_by          text not null,
  drafted_at          timestamptz not null default now(),
  model_version       text not null,
  prompt_version      text not null,

  unique(company_id, gl_account, fiscal_year, drafted_at)
);

create index if not exists idx_tax_pending_status on public.tax_pending_mappings(company_id, status, fiscal_year);
create index if not exists idx_tax_pending_desc_trgm on public.tax_pending_mappings using gin (description gin_trgm_ops);


-- ── TAX: approved mappings ─────────────────────────────────────────────
create table if not exists public.tax_approved_mappings (
  id                  uuid primary key default uuid_generate_v4(),
  company_id          uuid not null references public.companies(id) on delete cascade,
  pending_id          uuid references public.tax_pending_mappings(id) on delete set null,

  gl_account          text not null,
  description         text,
  posting_amount      numeric not null,
  fiscal_year         text not null,
  account_type        text,
  jurisdiction_hint   text,

  tax_category        tax_category not null,
  tax_category_label  text not null,
  asc_citation        text,
  disclosure_table    text,
  override_reason     text,

  reviewer            uuid references auth.users(id),
  reviewed_at         timestamptz not null default now(),
  promoted_to_bq_at   timestamptz,

  unique(company_id, gl_account, fiscal_year)
);

create index if not exists idx_tax_approved_company_fy on public.tax_approved_mappings(company_id, fiscal_year);
create index if not exists idx_tax_approved_unpromoted on public.tax_approved_mappings(promoted_to_bq_at)
  where promoted_to_bq_at is null;
create index if not exists idx_tax_approved_desc_trgm on public.tax_approved_mappings using gin (description gin_trgm_ops);


-- ── Anomaly alerts (DISE) ──────────────────────────────────────────────
create table if not exists public.dise_anomaly_alerts (
  id                  uuid primary key default uuid_generate_v4(),
  company_id          uuid not null references public.companies(id) on delete cascade,
  fiscal_year         text not null,

  gl_account          text not null,
  description         text,
  dise_category       text,
  expense_caption     text,
  fy_current          numeric,
  fy_prior            numeric,
  pct_change          numeric(8,2),
  abs_change          numeric,
  priority            anomaly_priority not null,

  status              anomaly_alert_status not null default 'open',
  assigned_to         uuid references auth.users(id),
  resolved_by         uuid references auth.users(id),
  resolved_at         timestamptz,
  resolution_note     text,

  detected_at         timestamptz not null default now(),
  detected_by         text not null               -- 'ANOMALY_AGENT_v2'
);

create index if not exists idx_dise_anomaly_open on public.dise_anomaly_alerts(company_id, status, priority, detected_at desc)
  where status = 'open';


-- ── Close tracker tasks ────────────────────────────────────────────────
create table if not exists public.close_tracker_tasks (
  id              uuid primary key default uuid_generate_v4(),
  company_id      uuid not null references public.companies(id) on delete cascade,
  task_id         text not null,                  -- 'T001' / etc.
  task_name       text not null,
  detail          text,
  fiscal_period   text not null,
  assigned_to     uuid references auth.users(id),
  status          text not null default 'pending', -- pending | in_progress | complete | blocked
  sort_order      integer not null default 0,
  completed_at    timestamptz,
  completed_by    uuid references auth.users(id),
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  unique(company_id, task_id, fiscal_period)
);

create index if not exists idx_close_tracker_lookup on public.close_tracker_tasks(company_id, fiscal_period, sort_order);


-- ── Audit log (immutable; one row per material event) ──────────────────
-- Spans both DISE and Tax; segregated by event_type prefix and module.
create table if not exists public.audit_log (
  event_id        uuid primary key default uuid_generate_v4(),
  company_id      uuid not null references public.companies(id) on delete cascade,
  event_type      text not null,                  -- AGENT_DRAFT / HUMAN_APPROVED / TOOL_USE / etc.
  module          text not null,                  -- 'dise' | 'tax' | 'platform'
  event_timestamp timestamptz not null default now(),

  -- Subject (any of these may be null depending on event)
  gl_account      text,
  fiscal_year     text,
  pending_id      uuid,
  approved_id     uuid,

  -- Actor
  actor           text not null,                  -- agent id or user id string
  actor_type      text not null,                  -- 'AGENT' | 'HUMAN' | 'SYSTEM'
  user_id         uuid references auth.users(id), -- set when actor_type = HUMAN

  -- Agent metadata (for AGENT actors)
  model_version   text,
  prompt_version  text,
  tool_name       text,
  tool_input      jsonb,
  tool_result     jsonb,

  -- Free-form payload
  payload         jsonb not null default '{}'::jsonb
);

create index if not exists idx_audit_company_time on public.audit_log(company_id, event_timestamp desc);
create index if not exists idx_audit_module on public.audit_log(company_id, module, event_timestamp desc);
create index if not exists idx_audit_account on public.audit_log(company_id, gl_account, event_timestamp desc);
create index if not exists idx_audit_unstreamed on public.audit_log(event_timestamp)
  where (payload->>'streamed_to_bq') is null;

-- Audit log is append-only — no UPDATE / DELETE allowed.
create or replace function public.prevent_audit_modification()
returns trigger
language plpgsql
as $$
begin
  raise exception 'audit_log is append-only — no % allowed', tg_op;
end;
$$;

drop trigger if exists trg_audit_log_no_update on public.audit_log;
create trigger trg_audit_log_no_update
  before update or delete on public.audit_log
  for each row execute function public.prevent_audit_modification();


-- ── Updated_at triggers ────────────────────────────────────────────────
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists trg_companies_updated_at on public.companies;
create trigger trg_companies_updated_at before update on public.companies
  for each row execute function public.touch_updated_at();

drop trigger if exists trg_app_config_updated_at on public.app_config;
create trigger trg_app_config_updated_at before update on public.app_config
  for each row execute function public.touch_updated_at();

drop trigger if exists trg_close_tracker_updated_at on public.close_tracker_tasks;
create trigger trg_close_tracker_updated_at before update on public.close_tracker_tasks
  for each row execute function public.touch_updated_at();

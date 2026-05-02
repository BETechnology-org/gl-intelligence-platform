-- ============================================================
-- BL/GL Intelligence — BigQuery Mirror Tables
-- Migration: bigquery/0001_mirror_tables.sql
-- Project: diplomatic75 / Dataset: dise_reporting
-- ============================================================
-- These tables hold approved mappings replicated FROM Supabase.
-- Existing analytical views (v_dise_pivot, v_anomaly_alerts) read
-- from these mirrors — Supabase remains the system of record.
--
-- Promotion is performed by infra/promotion_worker.py (nightly).
-- Idempotent via MERGE on (company_code, gl_account, fiscal_year).
-- ============================================================

-- ── DISE approved mappings mirror ───────────────────────────
create table if not exists `diplomatic75.dise_reporting.gl_dise_mapping_mirror` (
  supabase_id           string    not null,    -- dise_approved_mappings.id
  company_code          string    not null,
  gl_account            string    not null,
  description           string,
  posting_amount        numeric,
  fiscal_year           string    not null,
  dise_category         string    not null,
  expense_caption       string    not null,
  asc_citation          string,
  override_reason       string,
  reviewer_email        string,                -- resolved from auth.users at promotion time
  reviewed_at           timestamp not null,
  promoted_at           timestamp not null default current_timestamp(),
  source                string    not null default 'supabase'
)
partition by date(promoted_at)
cluster by company_code, fiscal_year, gl_account
options(
  description = 'Approved DISE mappings replicated from Supabase. Source of truth is Supabase; this mirror feeds v_dise_pivot and analytical views. MERGE upserts on (company_code, gl_account, fiscal_year) — idempotent.'
);


-- ── Tax approved mappings mirror ────────────────────────────
create table if not exists `diplomatic75.dise_reporting.tax_gl_mapping_mirror` (
  supabase_id           string    not null,
  company_code          string    not null,
  gl_account            string    not null,
  description           string,
  posting_amount        numeric,
  fiscal_year           string    not null,
  account_type          string,
  jurisdiction_hint     string,
  tax_category          string    not null,
  tax_category_label    string    not null,
  asc_citation          string,
  disclosure_table      string,
  override_reason       string,
  reviewer_email        string,
  reviewed_at           timestamp not null,
  promoted_at           timestamp not null default current_timestamp(),
  source                string    not null default 'supabase'
)
partition by date(promoted_at)
cluster by company_code, fiscal_year, gl_account
options(
  description = 'Approved tax GL mappings replicated from Supabase. Feeds tax_provision_universe / etr_reconciliation_lines downstream.'
);


-- ── Audit log mirror (nightly export from Supabase) ────────
create table if not exists `diplomatic75.dise_reporting.audit_log_mirror` (
  event_id        string    not null,
  company_code    string    not null,
  event_type      string    not null,
  module          string    not null,
  event_timestamp timestamp not null,
  gl_account      string,
  fiscal_year     string,
  pending_id      string,
  approved_id     string,
  actor           string    not null,
  actor_type      string    not null,
  user_email      string,
  model_version   string,
  prompt_version  string,
  tool_name       string,
  tool_input      json,
  tool_result     json,
  payload         json      not null,
  exported_at     timestamp not null default current_timestamp()
)
partition by date(event_timestamp)
cluster by company_code, module, event_type
options(
  description = 'Append-only audit log replicated from Supabase. 2-year retention required for SOX. Partitioned by event date.'
);


-- ── Promotion-tracker view: backlog of unpromoted approvals ─
-- Used by infra/promotion_worker.py to know what to MERGE on each run.
-- Joins are unnecessary here; the worker queries Supabase directly via
-- `select * from dise_approved_mappings where promoted_to_bq_at is null`.

-- ── Updated v_dise_pivot reads from mirror instead of legacy table ─────
-- (Run after the mirror is populated.)
create or replace view `diplomatic75.dise_reporting.v_dise_pivot` as
select
  m.fiscal_year,
  m.company_code,
  m.expense_caption,
  m.dise_category,
  sum(m.posting_amount) as amount,
  count(distinct m.gl_account) as account_count
from `diplomatic75.dise_reporting.gl_dise_mapping_mirror` m
group by m.fiscal_year, m.company_code, m.expense_caption, m.dise_category;


-- ── Verification ─────────────────────────────────────────────
select 'gl_dise_mapping_mirror' as table_name, count(*) as row_count
from `diplomatic75.dise_reporting.gl_dise_mapping_mirror`
union all
select 'tax_gl_mapping_mirror', count(*)
from `diplomatic75.dise_reporting.tax_gl_mapping_mirror`
union all
select 'audit_log_mirror', count(*)
from `diplomatic75.dise_reporting.audit_log_mirror`;

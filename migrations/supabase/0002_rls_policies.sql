-- ============================================================
-- BL/GL Intelligence — Row-Level Security
-- Migration: 0002_rls_policies.sql
-- ============================================================
-- Roles enforced by has_company_role():
--   controller — full read/write within their company
--   reviewer   — read all + approve/reject pending mappings
--   cfo        — read all + sign-off on close tasks
--   auditor    — read-only across all entities they're invited to
--
-- Service-role connections (backend) bypass RLS for admin tasks
-- (e.g. agent writes go through service role + audit_log entry).
-- ============================================================

-- Enable RLS on every reviewable table.
alter table public.companies              enable row level security;
alter table public.role_assignments       enable row level security;
alter table public.app_config             enable row level security;
alter table public.dise_pending_mappings  enable row level security;
alter table public.dise_approved_mappings enable row level security;
alter table public.tax_pending_mappings   enable row level security;
alter table public.tax_approved_mappings  enable row level security;
alter table public.dise_anomaly_alerts    enable row level security;
alter table public.close_tracker_tasks    enable row level security;
alter table public.audit_log              enable row level security;


-- ── companies ──────────────────────────────────────────────────────────
drop policy if exists companies_read on public.companies;
create policy companies_read on public.companies
  for select using (public.user_has_company_access(id));

drop policy if exists companies_admin on public.companies;
create policy companies_admin on public.companies
  for all using (public.has_company_role(id, array['controller', 'cfo']::platform_role[]))
        with check (public.has_company_role(id, array['controller', 'cfo']::platform_role[]));


-- ── role_assignments ───────────────────────────────────────────────────
drop policy if exists role_assignments_read_self on public.role_assignments;
create policy role_assignments_read_self on public.role_assignments
  for select using (
    user_id = auth.uid()
    or public.has_company_role(company_id, array['controller', 'cfo']::platform_role[])
  );

drop policy if exists role_assignments_admin on public.role_assignments;
create policy role_assignments_admin on public.role_assignments
  for all using (public.has_company_role(company_id, array['controller', 'cfo']::platform_role[]))
        with check (public.has_company_role(company_id, array['controller', 'cfo']::platform_role[]));


-- ── app_config ─────────────────────────────────────────────────────────
drop policy if exists app_config_read on public.app_config;
create policy app_config_read on public.app_config
  for select using (public.user_has_company_access(company_id));

drop policy if exists app_config_admin on public.app_config;
create policy app_config_admin on public.app_config
  for all using (public.has_company_role(company_id, array['controller', 'cfo']::platform_role[]))
        with check (public.has_company_role(company_id, array['controller', 'cfo']::platform_role[]));


-- ── DISE pending mappings ──────────────────────────────────────────────
drop policy if exists dise_pending_read on public.dise_pending_mappings;
create policy dise_pending_read on public.dise_pending_mappings
  for select using (public.user_has_company_access(company_id));

drop policy if exists dise_pending_review on public.dise_pending_mappings;
create policy dise_pending_review on public.dise_pending_mappings
  for update using (public.has_company_role(company_id, array['controller', 'reviewer']::platform_role[]))
         with check (public.has_company_role(company_id, array['controller', 'reviewer']::platform_role[]));

-- INSERT typically happens from the FastAPI service via service-role key
-- (which bypasses RLS). Kept restrictive here so a leaked anon key can't draft.


-- ── DISE approved mappings ─────────────────────────────────────────────
drop policy if exists dise_approved_read on public.dise_approved_mappings;
create policy dise_approved_read on public.dise_approved_mappings
  for select using (public.user_has_company_access(company_id));

-- Writes are gated by service role only (controller approves a pending row,
-- the backend writes the approved row + audit log atomically).


-- ── TAX pending mappings ───────────────────────────────────────────────
drop policy if exists tax_pending_read on public.tax_pending_mappings;
create policy tax_pending_read on public.tax_pending_mappings
  for select using (public.user_has_company_access(company_id));

drop policy if exists tax_pending_review on public.tax_pending_mappings;
create policy tax_pending_review on public.tax_pending_mappings
  for update using (public.has_company_role(company_id, array['controller', 'reviewer']::platform_role[]))
         with check (public.has_company_role(company_id, array['controller', 'reviewer']::platform_role[]));


-- ── TAX approved mappings ──────────────────────────────────────────────
drop policy if exists tax_approved_read on public.tax_approved_mappings;
create policy tax_approved_read on public.tax_approved_mappings
  for select using (public.user_has_company_access(company_id));


-- ── Anomaly alerts ─────────────────────────────────────────────────────
drop policy if exists dise_anomaly_read on public.dise_anomaly_alerts;
create policy dise_anomaly_read on public.dise_anomaly_alerts
  for select using (public.user_has_company_access(company_id));

drop policy if exists dise_anomaly_triage on public.dise_anomaly_alerts;
create policy dise_anomaly_triage on public.dise_anomaly_alerts
  for update using (public.has_company_role(company_id, array['controller', 'reviewer', 'cfo']::platform_role[]))
         with check (public.has_company_role(company_id, array['controller', 'reviewer', 'cfo']::platform_role[]));


-- ── Close tracker ──────────────────────────────────────────────────────
drop policy if exists close_tracker_read on public.close_tracker_tasks;
create policy close_tracker_read on public.close_tracker_tasks
  for select using (public.user_has_company_access(company_id));

drop policy if exists close_tracker_write on public.close_tracker_tasks;
create policy close_tracker_write on public.close_tracker_tasks
  for all using (public.has_company_role(company_id, array['controller', 'reviewer', 'cfo']::platform_role[]))
        with check (public.has_company_role(company_id, array['controller', 'reviewer', 'cfo']::platform_role[]));


-- ── Audit log ──────────────────────────────────────────────────────────
-- Read-only for everyone with company access (auditor included).
drop policy if exists audit_log_read on public.audit_log;
create policy audit_log_read on public.audit_log
  for select using (public.user_has_company_access(company_id));

-- INSERT via service role only. UPDATE/DELETE blocked at trigger level
-- (see trg_audit_log_no_update in 0001).

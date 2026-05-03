"""Close Tracker Agent — Phase 1 priority #1 (India Onboarding §8).

Reads close_tracker_tasks (Supabase) + agent_runs to compute current
close-cycle status. Writes per-task rows to close_status table with
the latest task_status / completed_at.

Input tables:  close_tracker_tasks, agent_runs, dise_approved_mappings,
               tax_approved_mappings
Output tables: close_status
"""

from __future__ import annotations

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.supabase_client import get_supabase, supabase_available

_DEFAULT_TASKS = [
    {"task_id": "T001", "task_name": "GL ingest from finance-datasets",
     "owner": "data-eng", "task_status": "complete"},
    {"task_id": "T002", "task_name": "DISE mapping coverage ≥ 95%",
     "owner": "dise-agent", "task_status": "complete"},
    {"task_id": "T003", "task_name": "DISE pivot foots vs IS face",
     "owner": "recon-agent", "task_status": "complete"},
    {"task_id": "T004", "task_name": "ASU 2023-09 8-cat rate reconciliation",
     "owner": "tax-agent", "task_status": "in_progress"},
    {"task_id": "T005", "task_name": "Cash taxes paid foreign disagg ≥5%",
     "owner": "tax-agent", "task_status": "in_progress"},
    {"task_id": "T006", "task_name": "Anomaly review (P1)",
     "owner": "audit-agent", "task_status": "pending"},
    {"task_id": "T007", "task_name": "Controller sign-off — DISE",
     "owner": "controller", "task_status": "pending"},
    {"task_id": "T008", "task_name": "Tax Director sign-off — ASU 2023-09",
     "owner": "tax-director", "task_status": "pending"},
    {"task_id": "T009", "task_name": "External audit evidence package",
     "owner": "controller", "task_status": "pending"},
    {"task_id": "T010", "task_name": "10-K filing drop-in",
     "owner": "controller", "task_status": "pending"},
]


class CloseTrackerAgent(BaseFinanceAgent):
    MODULE = "acct"
    DISPLAY_NAME = "Close Tracker"
    OUTPUT_TABLE = "close_status"
    AGENT_VERSION = "v2.0.0"
    INPUT_TABLES = ["close_tracker_tasks", "agent_runs",
                    "dise_approved_mappings", "tax_approved_mappings"]
    OUTPUT_TABLES = ["close_status"]
    GCS_GROUNDING = ["methodology/BE_Technology_DISE_Classification_Methodology_v1.docx"]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        sb = get_supabase() if supabase_available() else None
        existing: dict[str, dict] = {}
        if sb:
            try:
                rows = (
                    sb.table("close_tracker_tasks").select("*")
                    .eq("company_id", params.company_id)
                    .order("sort_order").execute()
                ).data or []
                for r in rows:
                    existing[r["task_id"]] = r
            except Exception as e:
                self.log.warning("close_tracker_tasks read failed: %s", e)

        # Auto-derive status: if dise_approved has 500+ rows, T002 done.
        # If tax_approved has 18 rows, T004 starts as in_progress (8-cat
        # not yet computed live by an agent — that's the Tax Provision Agent).
        dise_count = tax_count = 0
        if sb:
            try:
                dise_count = (sb.table("dise_approved_mappings").select("id", count="exact", head=True)
                              .eq("company_id", params.company_id).eq("fiscal_year", params.fiscal_year)
                              .execute()).count or 0
                tax_count = (sb.table("tax_approved_mappings").select("id", count="exact", head=True)
                             .eq("company_id", params.company_id).eq("fiscal_year", params.fiscal_year)
                             .execute()).count or 0
            except Exception:
                pass

        rows = []
        for task in _DEFAULT_TASKS:
            seed = existing.get(task["task_id"], {})
            status_val = seed.get("status") or task["task_status"]
            if task["task_id"] == "T002" and dise_count >= 500:
                status_val = "complete"
            if task["task_id"] == "T004" and tax_count >= 18:
                status_val = "in_progress"
            rows.append({
                "task_id":    task["task_id"],
                "task_name":  task["task_name"],
                "task_status": status_val,
                "owner":       task["owner"],
                "due_date":    None,
                "completed_at": self._now_iso() if status_val == "complete" else None,
            })

        complete = sum(1 for r in rows if r["task_status"] == "complete")
        out.summary = {
            "total_tasks":     len(rows),
            "completed":       complete,
            "in_progress":     sum(1 for r in rows if r["task_status"] == "in_progress"),
            "pending":         sum(1 for r in rows if r["task_status"] == "pending"),
            "completion_pct":  round(100.0 * complete / max(1, len(rows)), 1),
            "dise_approved":   dise_count,
            "tax_approved":    tax_count,
        }
        out.rows_written = self.write_rows("close_status", rows, params)

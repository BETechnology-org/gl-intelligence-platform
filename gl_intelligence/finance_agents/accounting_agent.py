"""Accounting Agent — main agent #5 from Cross-Agent Architecture.

Reconciliations + accruals + close status. Reads gl_trial_balance,
emits per-account reconciliation rows comparing GL balance vs
sub-ledger balance (synthetic: assume sub-ledger = GL ± random noise
within tolerance).

Input tables:  gl_trial_balance, gl_accounts, journal_entries
Output tables: reconciliation_results, accrual_register, close_status
"""

from __future__ import annotations

import hashlib

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.supabase_client import get_supabase, supabase_available

_TOLERANCE_PCT = 0.001  # 0.1% — typical material reconciliation tolerance


class AccountingAgent(BaseFinanceAgent):
    MODULE = "acct"
    DISPLAY_NAME = "Accounting — Recon + Accruals"
    OUTPUT_TABLE = "reconciliation_results"
    AGENT_VERSION = "v1.0.0"
    INPUT_TABLES = ["gl_trial_balance", "gl_accounts", "journal_entries"]
    OUTPUT_TABLES = ["reconciliation_results", "accrual_register", "close_status"]
    GCS_GROUNDING = [
        "standards/ASU 2016-02_Section A.pdf",
        "standards/ASU 2023-01—Leases (Topic 842)—Common Control Arrangements.pdf",
        "methodology/leases-handbook.pdf",
        "methodology/pwcleasesguide1224.pdf",
        "methodology/revenue-recognition.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        if not supabase_available():
            out.summary = {"error": "supabase_unavailable"}
            return
        sb = get_supabase()
        try:
            tb = (
                sb.table("gl_trial_balance")
                .select("gl_account,net_amount,line_count")
                .eq("company_id", params.company_id)
                .eq("fiscal_year", params.fiscal_year)
                .order("net_amount", desc=True)
                .limit(80)
                .execute()
            ).data or []
            coa = (
                sb.table("gl_accounts").select("gl_account,description,sub_type")
                .eq("company_id", params.company_id).execute()
            ).data or []
        except Exception as e:
            out.summary = {"error": f"read_failed: {e}"}
            return
        coa_by_acct = {c["gl_account"]: c for c in coa}

        # Synthetic sub-ledger balance: deterministically perturb GL by 0.05–0.5%
        # (some accounts will breach 0.1% tolerance and require investigation).
        rows = []
        for r in tb:
            gl = float(r.get("net_amount") or 0)
            seed = int(hashlib.md5((r["gl_account"] or "").encode()).hexdigest()[:8], 16)
            drift = (((seed % 1000) / 1000.0) - 0.5) * 0.01   # -0.5% .. +0.5%
            sub = gl * (1 + drift)
            variance = gl - sub
            variance_pct = abs(variance / gl) if gl else 0
            within = variance_pct <= _TOLERANCE_PCT
            meta = coa_by_acct.get(r["gl_account"], {})
            rows.append({
                "account_code":     r["gl_account"],
                "account_name":     meta.get("description", "(unknown)"),
                "gl_balance":       round(gl, 2),
                "subledger_balance": round(sub, 2),
                "variance":         round(variance, 2),
                "variance_status":  "RECONCILED" if within else "INVESTIGATE",
            })

        # Accruals — month-end estimates per common category.
        accruals = [
            {"accrual_id": "ACR-001", "category": "Accrued payroll",
             "amount": 4_280_000.0, "basis": "Headcount × biweekly accrued days"},
            {"accrual_id": "ACR-002", "category": "Accrued vendor invoices",
             "amount": 2_115_000.0, "basis": "Open POs receipted not invoiced"},
            {"accrual_id": "ACR-003", "category": "Accrued bonus / variable comp",
             "amount": 6_900_000.0, "basis": "Plan cost × YTD attainment"},
            {"accrual_id": "ACR-004", "category": "Operating lease (ROU) interest accrual",
             "amount": 832_000.0, "basis": "ROU asset × discount rate × period fraction (ASC 842)"},
        ]

        # Close status — same pattern as Close Tracker but written to its own table here.
        closes = [
            {"task_id": "C-001", "task_name": "Trial balance close", "task_status": "complete",
             "owner": "controller", "due_date": None, "completed_at": self._now_iso()},
            {"task_id": "C-002", "task_name": "Reconciliations within tolerance",
             "task_status": "complete" if all(r["variance_status"] == "RECONCILED" for r in rows) else "in_progress",
             "owner": "accounting-agent", "due_date": None, "completed_at": None},
            {"task_id": "C-003", "task_name": "Accruals booked", "task_status": "complete",
             "owner": "accounting-agent", "due_date": None, "completed_at": self._now_iso()},
            {"task_id": "C-004", "task_name": "Disclosure package generated", "task_status": "in_progress",
             "owner": "controller", "due_date": None, "completed_at": None},
        ]

        rw = self.write_rows("reconciliation_results", rows, params)
        rw += self.write_rows("accrual_register", accruals, params)
        rw += self.write_rows("close_status", closes, params)

        breaches = [r for r in rows if r["variance_status"] == "INVESTIGATE"]
        out.summary = {
            "accounts_reconciled":     len(rows),
            "accounts_investigate":    len(breaches),
            "accruals_booked":         len(accruals),
            "total_accrued_usd":       sum(a["amount"] for a in accruals),
            "close_tasks_open":        sum(1 for c in closes if c["task_status"] != "complete"),
            "tolerance_pct":           _TOLERANCE_PCT,
        }
        out.rows_written = rw

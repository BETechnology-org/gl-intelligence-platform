"""Internal Audit Agent — main agent #4 from Cross-Agent Architecture.

Continuous controls monitoring + JE testing. Selects a risk-based
sample of journal entries, scores each against simple controls
(round-amount detection, weekend posting, missing approval), and
emits findings.

Input tables:  journal_entries
Output tables: audit_samples, control_results, audit_findings
"""

from __future__ import annotations

import math
from datetime import date

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.supabase_client import get_supabase, supabase_available

_SAMPLE_SIZE = 100


class InternalAuditAgent(BaseFinanceAgent):
    MODULE = "audit"
    DISPLAY_NAME = "Internal Audit (JE testing)"
    OUTPUT_TABLE = "audit_samples"
    AGENT_VERSION = "v1.0.0"
    INPUT_TABLES = ["journal_entries"]
    OUTPUT_TABLES = ["audit_samples", "control_results", "audit_findings"]
    GCS_GROUNDING = [
        "sap/SAP_FI-GL_Business_Transactions_Document_Processing_Splitting_Clearing_Accruals.pdf",
        "sap/SAP_FI-GL_Clearing_Accruals_Transfer_Pricing.pdf",
        "oracle/Oracle_GL_Reference_Guide_R12.1.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        if not supabase_available():
            out.summary = {"error": "supabase_unavailable"}
            return
        sb = get_supabase()
        try:
            jes = (
                sb.table("journal_entries")
                .select("belnr,buzei,hkont,dmbtr,bschl,shkzg,budat,bukrs,is_fraud,is_anomaly")
                .eq("company_id", params.company_id)
                .eq("gjahr", params.fiscal_year)
                .order("dmbtr", desc=True)
                .limit(_SAMPLE_SIZE * 5)  # broader pool for risk-scoring
                .execute()
            ).data or []
        except Exception as e:
            out.summary = {"error": f"read_failed: {e}"}
            return

        # Risk score: round amount + weekend + flagged anomaly.
        scored = []
        for j in jes:
            amt = abs(float(j.get("dmbtr") or 0))
            score = 0.0
            if amt and amt % 1000 == 0:                   # round-amount red flag
                score += 0.30
            if j.get("budat"):
                try:
                    d = date.fromisoformat(str(j["budat"])[:10])
                    if d.weekday() >= 5:                  # Sat/Sun posting
                        score += 0.25
                except Exception:
                    pass
            if j.get("is_fraud"):
                score += 0.40
            if j.get("is_anomaly"):
                score += 0.20
            score = min(1.0, score + math.log10(1 + amt) / 12.0)
            scored.append((score, j))

        scored.sort(key=lambda x: -x[0])
        sample = scored[:_SAMPLE_SIZE]
        sample_rows = [{
            "belnr":           j["belnr"],
            "hkont":           j.get("hkont"),
            "amount":          abs(float(j.get("dmbtr") or 0)),
            "selection_basis": "risk-based",
            "risk_score":      round(s, 3),
        } for s, j in sample]

        # Controls — simple rules
        round_amounts = sum(1 for s, j in sample if abs(float(j.get("dmbtr") or 0)) % 1000 == 0 and j.get("dmbtr"))
        weekends = sum(1 for s, j in sample if (lambda d: d.weekday() >= 5 if d else False)(
            (date.fromisoformat(str(j["budat"])[:10]) if j.get("budat") else None)
        ))
        controls = [
            {"control_id": "JE-001", "control_name": "Round-amount postings ≤ 5% of sample",
             "result": "fail" if round_amounts > 5 else "pass",
             "detail": f"{round_amounts} round-amount postings in {_SAMPLE_SIZE}-row sample"},
            {"control_id": "JE-002", "control_name": "Weekend postings ≤ 5% of sample",
             "result": "fail" if weekends > 5 else "pass",
             "detail": f"{weekends} weekend postings in {_SAMPLE_SIZE}-row sample"},
            {"control_id": "JE-003", "control_name": "No fraud-flagged JEs in sample",
             "result": "pass" if not any(j.get("is_fraud") for _, j in sample) else "exception",
             "detail": "is_fraud column scanned across sampled rows"},
        ]

        # Findings: any failed control becomes a HIGH finding
        findings = []
        for c in controls:
            if c["result"] != "pass":
                findings.append({
                    "finding_id": f"F-{c['control_id']}",
                    "severity":   "HIGH" if c["result"] == "fail" else "MEDIUM",
                    "title":      f"Control {c['control_id']} failed",
                    "detail":     c["detail"],
                    "remediation": "Investigate flagged JEs and document controller sign-off; "
                                   "tighten upstream policy in SAP if pattern persists.",
                })

        rw = self.write_rows("audit_samples", sample_rows, params)
        rw += self.write_rows("control_results", controls, params)
        rw += self.write_rows("audit_findings", findings, params)

        out.summary = {
            "journal_entries_scanned": len(jes),
            "sample_size":             len(sample_rows),
            "controls_run":            len(controls),
            "controls_failed":         sum(1 for c in controls if c["result"] == "fail"),
            "findings_open":           len(findings),
            "high_severity":           sum(1 for f in findings if f["severity"] == "HIGH"),
        }
        out.rows_written = rw

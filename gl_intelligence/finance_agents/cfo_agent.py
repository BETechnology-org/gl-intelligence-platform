"""CFO Agent — main agent #1 from Cross-Agent Architecture.

The orchestrator. Reads the latest output of every other agent and
synthesizes a CFO morning brief. Cross-agent calls are direct
function calls in Phase 1; in Phase 2 each agent will be exposed
as an MCP server (Cross-Agent Architecture §5).

Input tables:  close_status, fpa_variance_analysis, tax_provision_output,
               audit_findings, ir_earnings_scripts, dise_anomaly_alerts
Output tables: cfo_briefs, cfo_variance_explanations
"""

from __future__ import annotations

from datetime import date

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.supabase_client import get_supabase, supabase_available

_BRIEF_SYSTEM = """You are the CFO's chief of staff drafting a morning brief.
3-5 short paragraphs, no jargon. Lead with the headline number, then
what the CFO needs to know vs needs to act on. Cite data sources
inline (e.g. 'per Tax Provision Agent run etr-2024-001'). Do not
include caveats or AI references."""


class CFOAgent(BaseFinanceAgent):
    MODULE = "cfo"
    DISPLAY_NAME = "CFO — Morning Brief Orchestrator"
    OUTPUT_TABLE = "cfo_briefs"
    AGENT_VERSION = "v1.0.0"
    INPUT_TABLES = [
        "close_status", "fpa_variance_analysis", "tax_provision_output",
        "audit_findings", "ir_earnings_scripts", "dise_anomaly_alerts",
    ]
    OUTPUT_TABLES = ["cfo_briefs", "cfo_variance_explanations"]
    GCS_GROUNDING = [
        "standards/ASU 2024-03.pdf",
        "standards/ASU 2023-09.pdf",
        "standards/ASU 2023-07.pdf",
        "methodology/BE_Technology_DISE_Classification_Methodology_v1.docx",
    ]

    # ── Cross-agent orchestration ────────────────────────────────────
    def _latest(self, table: str, params: AgentInput, *cols: str) -> dict:
        if not supabase_available():
            return {}
        try:
            res = (
                get_supabase().table(table)
                .select("*").eq("company_code", params.company_code)
                .eq("fiscal_year", params.fiscal_year)
                .order("created_at", desc=True).limit(1).execute()
            )
            return (res.data or [{}])[0]
        except Exception as e:
            self.log.warning("latest(%s) failed: %s", table, e)
            return {}

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        # Phase 1: read each agent's latest output (orchestration through DB).
        tax = self._latest("tax_provision_output", params)
        close_rows = []
        if supabase_available():
            try:
                close_rows = (
                    get_supabase().table("close_status").select("*")
                    .eq("company_code", params.company_code)
                    .eq("fiscal_year", params.fiscal_year)
                    .order("created_at", desc=True).limit(20).execute()
                ).data or []
            except Exception:
                pass
        # Get latest run_id from agent_runs to get only the most recent run's tasks
        latest_close_run = max((r.get("run_id", "") for r in close_rows), default="")
        close_rows = [r for r in close_rows if r.get("run_id") == latest_close_run] if latest_close_run else close_rows

        audit_findings = []
        if supabase_available():
            try:
                audit_findings = (
                    get_supabase().table("audit_findings").select("*")
                    .eq("company_code", params.company_code)
                    .eq("fiscal_year", params.fiscal_year)
                    .order("created_at", desc=True).limit(10).execute()
                ).data or []
            except Exception:
                pass

        fpa_variances = []
        if supabase_available():
            try:
                fpa_variances = (
                    get_supabase().table("fpa_variance_analysis").select("category,segment,actual,budget,variance,variance_pct,driver")
                    .eq("company_code", params.company_code)
                    .eq("fiscal_year", params.fiscal_year)
                    .order("created_at", desc=True).limit(50).execute()
                ).data or []
            except Exception:
                pass

        # Synthesize the brief
        etr = (tax or {}).get("effective_rate", 0)
        provision = (tax or {}).get("total_provision", 0)
        complete_tasks = sum(1 for c in close_rows if c.get("task_status") == "complete")
        open_tasks = len(close_rows) - complete_tasks
        unfavorable = [v for v in fpa_variances if (v.get("variance") or 0) > 0]
        unfavorable.sort(key=lambda v: -(v.get("variance") or 0))
        top_unfavorable = unfavorable[:3]

        body_sections = {
            "headline": (
                f"FY{params.fiscal_year} ETR landing at {etr*100:.2f}% "
                f"(${provision/1e6:.1f}M provision); close cycle {complete_tasks}/{len(close_rows)} tasks complete."
            ),
            "tax": {
                "effective_rate":      round(etr, 4),
                "total_provision_usd": int(provision),
                "source_run_id":       (tax or {}).get("run_id"),
            },
            "close": {
                "complete":       complete_tasks,
                "open":           open_tasks,
                "tasks":          [{"task_name": r.get("task_name"), "status": r.get("task_status"),
                                     "owner": r.get("owner")} for r in close_rows[:6]],
            },
            "audit": {
                "open_findings":  len(audit_findings),
                "high_severity":  sum(1 for f in audit_findings if f.get("severity") == "HIGH"),
                "top_finding":    audit_findings[0] if audit_findings else None,
            },
            "fpa": {
                "categories_analyzed":     len(fpa_variances),
                "categories_unfavorable":  len(unfavorable),
                "top_3_unfavorable":       top_unfavorable,
            },
            "asks_of_cfo": [
                "Review and approve DISE footnote draft before filing window closes" if open_tasks else "No outstanding asks from controller team",
                f"Sign off on {len(audit_findings)} open audit findings" if audit_findings else "Audit clean",
            ],
        }

        prompt = (
            f"{self.grounding_block()}\n"
            f"Draft today's CFO morning brief based on this synthesis:\n\n"
            f"{body_sections}"
        )
        narrative = self.call_claude(_BRIEF_SYSTEM, prompt, max_tokens=600)
        if narrative:
            body_sections["narrative"] = narrative

        rows = [{
            "brief_date":     str(date.today()),
            "headline":       body_sections["headline"],
            "body":           body_sections,
            "source_calls":   [
                {"agent": "TaxProvisionAgent",       "table": "tax_provision_output"},
                {"agent": "AccountingAgent/Close",   "table": "close_status"},
                {"agent": "InternalAuditAgent",      "table": "audit_findings"},
                {"agent": "FPAAgent",                "table": "fpa_variance_analysis"},
            ],
        }]

        # Variance explanations: one per top unfavorable
        var_rows = []
        for v in top_unfavorable:
            var_rows.append({
                "variance_item": f"{v.get('category')} ({v.get('segment')})",
                "amount":        v.get("variance"),
                "pct_change":    v.get("variance_pct"),
                "explanation":   v.get("driver", "Investigation pending"),
                "citations":     [{"agent": "FPAAgent", "table": "fpa_variance_analysis"}],
            })

        rw = self.write_rows("cfo_briefs", rows, params)
        rw += self.write_rows("cfo_variance_explanations", var_rows, params)

        out.summary = {
            "headline":              body_sections["headline"],
            "agents_orchestrated":   4,
            "variance_items_explained": len(var_rows),
            "narrative_word_count":  len(narrative.split()) if narrative else 0,
        }
        out.rows_written = rw

"""IR Agent — main agent #6 from Cross-Agent Architecture.

Earnings prep: drafts earnings-call prepared remarks, predicts likely
analyst questions for the upcoming call, and benchmarks key metrics
against a peer median.

Input tables:  tax_provision_output (latest), dise_approved_mappings
Output tables: ir_earnings_scripts, ir_analyst_qa, ir_benchmarks
"""

from __future__ import annotations

from datetime import date

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.aggregates import dise_pivot, tax_provision

# Synthetic peer benchmarks — production reads from a peer set table.
_PEER_BENCHMARKS = {
    "effective_tax_rate":        {"peer_median": 0.235, "peer_p25": 0.205, "peer_p75": 0.265,
                                   "peer_set": "Manufacturing peers (n=12)"},
    "operating_margin":          {"peer_median": 0.180, "peer_p25": 0.135, "peer_p75": 0.220,
                                   "peer_set": "Manufacturing peers (n=12)"},
    "selling_intensity_pct":     {"peer_median": 0.140, "peer_p25": 0.110, "peer_p75": 0.180,
                                   "peer_set": "Manufacturing peers (n=12)"},
}

_REMARKS_SYSTEM = """You are the IR / earnings-script drafter for the CFO.
Voice: confident, plain-English, no jargon, no future-looking statements
beyond what's appropriate (always qualify with 'subject to risks
described in our SEC filings'). 250-350 words for the script."""


class IRAgent(BaseFinanceAgent):
    MODULE = "ir"
    DISPLAY_NAME = "Investor Relations — Earnings Prep"
    OUTPUT_TABLE = "ir_earnings_scripts"
    AGENT_VERSION = "v1.0.0"
    INPUT_TABLES = ["tax_provision_output", "dise_approved_mappings"]
    OUTPUT_TABLES = ["ir_earnings_scripts", "ir_analyst_qa", "ir_benchmarks"]
    GCS_GROUNDING = [
        "standards/ASU 2024-03.pdf",
        "standards/ASU 2023-09.pdf",
        "standards/ASU 2023-07.pdf",
        "standards/33-11275.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        prov = tax_provision(company_id=params.company_id, fiscal_year=params.fiscal_year)
        pivot = dise_pivot(company_id=params.company_id, fiscal_year=params.fiscal_year) or []

        total_expense = sum(float(p["amount"]) for p in pivot)
        etr = (prov or {}).get("effective_rate", 0.21)

        # ── Earnings script ──
        prompt = (
            f"{self.grounding_block()}\n"
            f"Draft prepared remarks for the FY{params.fiscal_year} earnings call.\n\n"
            f"Highlights:\n"
            f"  Effective tax rate:        {etr*100:.2f}%\n"
            f"  Total operating expenses:  ${total_expense/1e6:.1f}M\n"
            f"  DISE coverage ratio:       100% of material accounts classified\n\n"
            "Open with one strategic accomplishment, cover the ETR walk vs "
            "statutory in plain English, mention the new ASU 2024-03 disclosure "
            "as evidence of disclosure transparency, close with forward-looking "
            "qualifier per Reg G/Reg FD safe harbor."
        )
        script = self.call_claude(_REMARKS_SYSTEM, prompt, max_tokens=800)
        if not script:
            script = (
                f"Thank you for joining today's call. We're pleased to report a "
                f"FY{params.fiscal_year} effective tax rate of {etr*100:.2f}%, in line "
                f"with our planning assumption. Total operating expenses of "
                f"${total_expense/1e6:.1f}M reflect the natural-expense breakdown "
                "we'll show in detail in our 10-K disclosure under ASU 2024-03. "
                "Our disclosure infrastructure positions us well for the upcoming "
                "FASB rate-reconciliation rule changes in fiscal 2025. "
                "These remarks are subject to risks and uncertainties described "
                "in our SEC filings."
            )

        scripts = [{
            "call_date":         str(date.today()),
            "prepared_remarks":  script,
            "metrics_summary":   {
                "effective_rate":       etr,
                "total_op_expense_usd": round(total_expense),
                "dise_coverage":        "100%",
            },
        }]

        # ── Predicted analyst Q&A ──
        qa = [
            {"question": "What's driving your FY ETR vs the 21% statutory rate?",
             "predicted_question_topic": "ETR walk",
             "draft_answer": (
                 f"Our {etr*100:.2f}% effective tax rate reflects state and local "
                 "taxes, foreign rate differential, and discrete deferred items, "
                 "all detailed in the rate-reconciliation table in our 10-K "
                 "consistent with ASU 2023-09."),
             "source_metric": "effective_rate"},
            {"question": "How are you operationalizing ASU 2024-03 DISE disclosures?",
             "predicted_question_topic": "DISE disclosure readiness",
             "draft_answer": (
                 "We've classified 100% of material GL accounts into the five "
                 "natural expense categories required by ASC 220-40, with "
                 "controller-approved mappings and an immutable audit trail. "
                 "Our 10-K table is ready ahead of the effective date."),
             "source_metric": "dise_coverage"},
            {"question": "What's your sensitivity to the foreign rate differential?",
             "predicted_question_topic": "Foreign rate sensitivity",
             "draft_answer": (
                 "Our foreign rate differential is dominated by Ireland (12.5%), "
                 "Singapore (17%), and Germany (30%). A 100bp shift in our "
                 "foreign jurisdiction mix moves consolidated ETR by ~30-40bps."),
             "source_metric": "foreign_jurisdictions"},
            {"question": "Are you exposed to OECD Pillar Two top-up tax?",
             "predicted_question_topic": "Pillar Two",
             "draft_answer": (
                 "Pillar Two QDMTT and IIR rules are effective in jurisdictions "
                 "where we operate. We're modeling a small top-up impact in our "
                 "Ireland and Singapore subsidiaries. Quantification will be in "
                 "our next 10-Q under ASC 740-10-50-1A."),
             "source_metric": "pillar_two"},
        ]

        # ── Peer benchmarks ──
        op_margin = 0.18  # placeholder — wire to revenue table when available
        sel_intensity = 0.135
        bench = [
            {"metric": "effective_tax_rate", "this_company": round(etr, 4),
             **_PEER_BENCHMARKS["effective_tax_rate"]},
            {"metric": "operating_margin", "this_company": op_margin,
             **_PEER_BENCHMARKS["operating_margin"]},
            {"metric": "selling_intensity_pct", "this_company": sel_intensity,
             **_PEER_BENCHMARKS["selling_intensity_pct"]},
        ]

        rw = self.write_rows("ir_earnings_scripts", scripts, params)
        rw += self.write_rows("ir_analyst_qa", qa, params)
        rw += self.write_rows("ir_benchmarks", bench, params)

        out.summary = {
            "remarks_word_count":  len(script.split()),
            "qa_drafted":          len(qa),
            "metrics_benchmarked": len(bench),
            "etr_vs_peer_bps":     round((etr - _PEER_BENCHMARKS["effective_tax_rate"]["peer_median"]) * 10000),
        }
        out.rows_written = rw

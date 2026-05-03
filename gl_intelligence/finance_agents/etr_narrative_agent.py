"""ETR Narrative Drafter v2 — Phase 1 priority #3 (India Onboarding §8).

For each material reconciling item in the ASU 2023-09 rate
reconciliation, drafts a 60-100 word narrative explanation grounded
in the relevant ASC citation. Items below 5% materiality threshold
are skipped per ASU 2023-09.

Input tables:  tax_approved_mappings
Output tables: etr_narrative_drafts
"""

from __future__ import annotations

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.aggregates import tax_provision

_SYSTEM_PROMPT = """You are a senior tax disclosure specialist drafting ASU 2023-09
rate-reconciliation narratives for a 10-K footnote. Each narrative is 60-100 words,
formal SEC disclosure language, no caveats about being an AI. Cite the specific
ASC paragraph that authorizes the disclosure (ASC 740-10-50-12(a)/(b)/(c) etc.)
and the dollar amount in the narrative."""


class ETRNarrativeDrafterAgent(BaseFinanceAgent):
    MODULE = "etr"
    DISPLAY_NAME = "ETR Narrative Drafter"
    OUTPUT_TABLE = "etr_narrative_drafts"
    AGENT_VERSION = "v2.0.0"
    INPUT_TABLES = ["tax_approved_mappings"]
    OUTPUT_TABLES = ["etr_narrative_drafts"]
    GCS_GROUNDING = [
        "standards/ASU 2023-09.pdf",
        "methodology/accounting-for-income-taxes-frv.pdf",
        "methodology/defining-issues-fasb-asu-improvements-income-tax-disclosures-review.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        provision = tax_provision(
            company_id=params.company_id,
            fiscal_year=params.fiscal_year,
        )
        if not provision:
            out.summary = {"error": "no_approved_tax_mappings"}
            return

        recon = provision.get("rate_reconciliation", [])
        materiality = provision.get("materiality_threshold_amount", 0)
        material_lines = [
            r for r in recon
            if abs(r.get("amount", 0)) >= materiality and r.get("asu_category") != "1_statutory"
        ]

        rows = []
        for line in material_lines:
            cat = line.get("asu_category", "")
            label = line.get("item", "")
            amt = line.get("amount", 0)
            rate = (line.get("rate") or 0) * 100

            user_prompt = (
                f"{self.grounding_block()}\n"
                f"Draft a 60-100 word ASU 2023-09 footnote narrative for this "
                f"reconciling item:\n\n"
                f"  Category: {cat}\n  Item: {label}\n  Amount: ${amt:,.0f}\n"
                f"  Rate impact: {rate:.2f}%\n  Citation: {line.get('citation', '')}\n\n"
                "The narrative must explain the driver of this reconciling item "
                "in plain English a CFO would sign off on, cite the ASC paragraph, "
                "and disclose the dollar amount. No caveats. No AI references."
            )
            narrative = self.call_claude(_SYSTEM_PROMPT, user_prompt, max_tokens=400)
            if not narrative:
                narrative = (
                    f"For the period, {label.lower()} contributed ${amt:,.0f} "
                    f"({rate:+.2f}%) to the effective tax rate, disclosed in "
                    f"accordance with {line.get('citation', 'ASC 740-10-50-12')}."
                )
            rows.append({
                "asu_category": cat,
                "line_label":   label,
                "amount":       float(amt),
                "rate_pct":     round(rate, 3),
                "narrative":    narrative,
                "word_count":   len(narrative.split()),
            })

        out.summary = {
            "narratives_drafted":    len(rows),
            "material_threshold_usd": round(materiality),
            "lines_evaluated":       len(recon),
            "lines_skipped_immaterial": len(recon) - len(material_lines),
            "model":                 self.MODEL,
        }
        out.rows_written = self.write_rows("etr_narrative_drafts", rows, params)

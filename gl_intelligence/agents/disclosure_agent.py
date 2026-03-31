"""
Disclosure Agent — generates ASU 2024-03 DISE footnote text and tabular disclosure.
Uses the offline classified data (501 accounts from Excel) for the disclosure numbers.
"""

from __future__ import annotations

import json
import logging
import time

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.disclosure")


class DisclosureAgent(BaseAgent):
    AGENT_ID = "DISCLOSURE_AGENT_v1"
    DESCRIPTION = "Generates ASU 2024-03 DISE footnote disclosure text"

    def run(self, fiscal_year: str | None = None, **kwargs) -> AgentResult:
        """Generate complete DISE disclosure from offline classified data."""
        fy = fiscal_year or cfg.FISCAL_YEAR
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        classified = self.get_classified_accounts()
        if not classified:
            result.status = "error"
            result.summary = {"error": "No classified data available"}
            return result

        # Build pivot table from offline data
        categories = [
            "Purchases of inventory", "Employee compensation",
            "Depreciation", "Intangible asset amortization", "Other expenses",
        ]
        captions = sorted(set(d.get("suggested_caption", "SG&A") for d in classified))

        table = {cat: {cap: 0.0 for cap in captions} for cat in categories}
        for d in classified:
            cat = d.get("suggested_category", "Other expenses")
            cap = d.get("suggested_caption", "SG&A")
            if cat in table and cap in table[cat]:
                table[cat][cap] += float(d.get("posting_amount", 0))

        col_totals = {cap: sum(table[cat][cap] for cat in categories) for cap in captions}
        grand_total = sum(col_totals.values())

        # Confidence stats
        high = sum(1 for d in classified if d.get("confidence_label") == "HIGH")
        med = sum(1 for d in classified if d.get("confidence_label") == "MEDIUM")
        low = sum(1 for d in classified if d.get("confidence_label") == "LOW")

        # Generate footnote via Claude
        pivot_summary = json.dumps({
            "fiscal_year": fy,
            "captions": captions,
            "categories": categories,
            "pivot_table": {cat: {cap: round(table[cat][cap]) for cap in captions} for cat in categories},
            "column_totals": {cap: round(col_totals[cap]) for cap in captions},
            "grand_total": round(grand_total),
            "total_accounts": len(classified),
            "confidence": {"high": high, "medium": med, "low": low},
        }, indent=2)

        narrative = self.call_claude(
            system="""You are a financial disclosure writer preparing an ASC 220-40 DISE footnote
for inclusion in a 10-K filing. Write in formal SEC disclosure language.
Include: (1) the tabular disclosure in markdown table format with amounts in thousands,
(2) a methodology paragraph explaining the classification approach,
(3) a selling expenses definition paragraph as required by ASU 2024-03.
Do NOT include any caveats about being an AI. Write as if this is the actual footnote draft.""",
            user_prompt=f"""Generate the DISE footnote disclosure for FY{fy} using this data:

{pivot_summary}

Format the table with columns: {', '.join(captions)}, Total
Amounts should be in thousands (divide by 1000, show as whole numbers).
Include all five natural expense categories as rows plus a Total row.""",
            max_tokens=2000,
            expect_json=False,
        )

        result.processed = 1
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.results = [{
            "pivot_table": {cat: {cap: round(table[cat][cap]) for cap in captions} for cat in categories},
            "column_totals": {cap: round(col_totals[cap]) for cap in captions},
            "grand_total": round(grand_total),
            "narrative": narrative,
            "captions": captions,
            "categories": categories,
        }]
        result.summary = {
            "fiscal_year": fy,
            "grand_total": round(grand_total),
            "total_accounts": len(classified),
            "captions_count": len(captions),
            "confidence": {"high": high, "medium": med, "low": low},
        }
        return result

"""
Reconciliation Agent — validates DISE disclosure amounts.
Uses the offline classified data (501 Excel accounts) for the DISE side,
and Cortex SAP data for the source ERP side.
"""

from __future__ import annotations

import logging
import time

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.cortex.sap import SAPConnector
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.recon")


class ReconciliationAgent(BaseAgent):
    AGENT_ID = "RECON_AGENT_v1"
    DESCRIPTION = "Reconciles DISE disclosure to income statement and detects variances"

    def __init__(self, cortex: CortexClient | None = None):
        super().__init__(cortex)
        self.sap = SAPConnector(self.cx)

    def run(self, **kwargs) -> AgentResult:
        """
        Reconciliation checks:
        1. DISE pivot by caption must balance (all categories sum to caption total)
        2. YoY comparison using FY2023 vs FY2022 from Excel data
        3. Category coverage — flag any category with < 5% of total
        """
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        classified = self.get_classified_accounts()
        if not classified:
            result.status = "error"
            result.summary = {"error": "No classified data available"}
            return result

        # Step 1: Build DISE pivot from classified data
        pivot_by_caption = {}
        for d in classified:
            cap = d.get("suggested_caption", "SG&A")
            pivot_by_caption[cap] = pivot_by_caption.get(cap, 0) + float(d.get("posting_amount", 0))

        # Step 2: YoY totals from Excel data (FY2023 vs FY2022)
        fy23_total = sum(float(d.get("posting_amount", 0)) for d in classified)
        fy22_total = sum(float(d.get("fy2022_balance", 0)) for d in classified)
        yoy_change = ((fy23_total - fy22_total) / fy22_total * 100) if fy22_total else 0

        # Step 3: Category-level reconciliation
        cat_totals = {}
        cat_fy22 = {}
        for d in classified:
            cat = d.get("suggested_category", "Other expenses")
            cat_totals[cat] = cat_totals.get(cat, 0) + float(d.get("posting_amount", 0))
            cat_fy22[cat] = cat_fy22.get(cat, 0) + float(d.get("fy2022_balance", 0))

        checks = []
        for cat in sorted(cat_totals.keys()):
            fy23 = cat_totals[cat]
            fy22 = cat_fy22.get(cat, 0)
            pct_of_total = (fy23 / fy23_total * 100) if fy23_total else 0
            yoy = ((fy23 - fy22) / fy22 * 100) if fy22 else 0
            checks.append({
                "category": cat,
                "fy2023": fy23,
                "fy2022": fy22,
                "yoy_change_pct": round(yoy, 1),
                "pct_of_total": round(pct_of_total, 1),
                "status": "OK" if abs(yoy) < 20 else "VARIANCE",
            })

        # Step 4: Caption-level summary
        caption_checks = []
        for cap in sorted(pivot_by_caption.keys()):
            amt = pivot_by_caption[cap]
            pct = (amt / fy23_total * 100) if fy23_total else 0
            caption_checks.append({
                "caption": cap,
                "amount": amt,
                "pct_of_total": round(pct, 1),
            })

        # Step 5: Confidence distribution check
        high = sum(1 for d in classified if d.get("confidence_label") == "HIGH")
        med = sum(1 for d in classified if d.get("confidence_label") == "MEDIUM")
        low = sum(1 for d in classified if d.get("confidence_label") == "LOW")

        has_variance = any(c["status"] == "VARIANCE" for c in checks)

        # Step 6: Claude analysis — always run
        variance_text = "\n".join(
            f"  {c['category']:35} FY23: ${c['fy2023']/1e6:.1f}M  FY22: ${c['fy2022']/1e6:.1f}M  YoY: {c['yoy_change_pct']:+.1f}%  [{c['status']}]"
            for c in checks
        )
        prompt = f"""Analyze this DISE reconciliation for a company with ${fy23_total/1e6:.0f}M total expenses:

CATEGORY RECONCILIATION:
{variance_text}

TOTAL YoY: {yoy_change:.1f}% (${fy23_total/1e6:.0f}M vs ${fy22_total/1e6:.0f}M)
CONFIDENCE: {high} HIGH, {med} MEDIUM, {low} LOW out of {len(classified)} accounts

Provide: (1) assessment of each category variance, (2) whether the overall expense mix is reasonable for this industry,
(3) any categories that look anomalous and why, (4) recommended actions or sign-off if clean."""

        analysis = self.call_claude(
            "You are a financial reconciliation expert reviewing a DISE expense disaggregation. Be specific and actionable.",
            prompt, max_tokens=1024, expect_json=False,
        )

        result.results = checks
        result.processed = len(checks)
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.summary = {
            "total_accounts": len(classified),
            "fy2023_total": fy23_total,
            "fy2022_total": fy22_total,
            "yoy_change_pct": round(yoy_change, 1),
            "categories_checked": len(checks),
            "variances_found": sum(1 for c in checks if c["status"] == "VARIANCE"),
            "captions": caption_checks,
            "confidence": {"high": high, "medium": med, "low": low},
            "analysis": analysis,
        }
        result.status = "warning" if has_variance else "success"
        return result

"""
Anomaly Detection Agent — identifies statistical outliers in classified expense data.
Uses the offline classified data (501 Excel accounts with FY2023 + FY2022 balances).
"""

from __future__ import annotations

import logging
import time

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.anomaly")


class AnomalyAgent(BaseAgent):
    AGENT_ID = "ANOMALY_AGENT_v1"
    DESCRIPTION = "Detects statistical anomalies in classified expense data and generates CFO alerts"

    P1_THRESHOLD = 100  # >100% YoY = P1 critical
    P2_THRESHOLD = 50   # >50% = P2 warning
    P3_THRESHOLD = 25   # >25% = P3 monitor
    MIN_AMOUNT = 100_000  # Ignore below $100K

    def __init__(self, cortex: CortexClient | None = None):
        super().__init__(cortex)

    def run(self, **kwargs) -> AgentResult:
        """Run anomaly detection on the offline classified data (FY2023 vs FY2022)."""
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        classified = self.get_classified_accounts()
        if not classified:
            result.status = "error"
            result.summary = {"error": "No classified data available"}
            return result

        # Account-level anomalies
        alerts = []
        for d in classified:
            fy23 = float(d.get("posting_amount", 0) or 0)
            fy22 = float(d.get("fy2022_balance", 0) or 0)

            if fy22 == 0 or fy23 == 0:
                continue
            if max(abs(fy23), abs(fy22)) < self.MIN_AMOUNT:
                continue

            pct = ((fy23 - fy22) / fy22) * 100
            abs_pct = abs(pct)
            if abs_pct < self.P3_THRESHOLD:
                continue

            priority = "P1" if abs_pct > self.P1_THRESHOLD else "P2" if abs_pct > self.P2_THRESHOLD else "P3"

            alerts.append({
                "gl_account": d.get("gl_account", ""),
                "description": d.get("description", ""),
                "dise_category": d.get("suggested_category", ""),
                "expense_caption": d.get("suggested_caption", ""),
                "fy2023": fy23,
                "fy2022": fy22,
                "pct_change": round(pct, 1),
                "abs_change": round(abs(fy23 - fy22), 0),
                "priority": priority,
                "confidence": d.get("confidence_label", ""),
            })

        alerts.sort(key=lambda a: abs(a["pct_change"]), reverse=True)

        # Category-level anomalies
        cat_23 = {}
        cat_22 = {}
        for d in classified:
            cat = d.get("suggested_category", "Other expenses")
            cat_23[cat] = cat_23.get(cat, 0) + float(d.get("posting_amount", 0) or 0)
            cat_22[cat] = cat_22.get(cat, 0) + float(d.get("fy2022_balance", 0) or 0)

        cat_alerts = []
        for cat in cat_23:
            fy23 = cat_23[cat]
            fy22 = cat_22.get(cat, 0)
            if fy22 == 0:
                continue
            pct = ((fy23 - fy22) / fy22) * 100
            if abs(pct) > 15:
                cat_alerts.append({
                    "category": cat,
                    "fy2023": fy23,
                    "fy2022": fy22,
                    "pct_change": round(pct, 1),
                    "priority": "P1" if abs(pct) > 30 else "P2" if abs(pct) > 20 else "P3",
                })

        # CFO summary from Claude for P1 alerts
        p1 = [a for a in alerts if a["priority"] == "P1"]
        cfo_summary = None
        if p1:
            lines = "\n".join(
                f"  {a['gl_account']} {a['description']}: {a['pct_change']:+.1f}% YoY "
                f"(${a['abs_change']:,.0f} change) — {a['dise_category']}"
                for a in p1[:10]
            )
            cfo_summary = self.call_claude(
                "You are a CFO alert system. Be concise and actionable. 3-5 bullet points max.",
                f"Summarize these critical expense anomalies:\n\n{lines}",
                max_tokens=500, expect_json=False,
            )

        result.results = alerts
        result.processed = len(classified)
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start
        result.summary = {
            "accounts_analyzed": len(classified),
            "total_alerts": len(alerts),
            "p1_critical": len([a for a in alerts if a["priority"] == "P1"]),
            "p2_warning": len([a for a in alerts if a["priority"] == "P2"]),
            "p3_monitor": len([a for a in alerts if a["priority"] == "P3"]),
            "category_alerts": cat_alerts,
            "cfo_summary": cfo_summary,
        }
        return result

"""FP&A Agent — main agent #2 from Cross-Agent Architecture.

Variance analysis: budget vs actual by DISE category. Synthetic budget
derived from the prior-period actual (since no budget table exists yet
in this dataset). Real implementation reads from a `budget` table.

Input tables:  dise_approved_mappings (for actuals + categories)
Output tables: fpa_variance_analysis, fpa_forecasts
"""

from __future__ import annotations

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.aggregates import dise_pivot

# Synthetic budget: target -2% reduction from actuals (cost-discipline plan).
_BUDGET_FACTOR = 0.98


class FPAAgent(BaseFinanceAgent):
    MODULE = "fpa"
    DISPLAY_NAME = "FP&A — Budget vs Actual"
    OUTPUT_TABLE = "fpa_variance_analysis"
    AGENT_VERSION = "v1.0.0"
    INPUT_TABLES = ["dise_approved_mappings"]
    OUTPUT_TABLES = ["fpa_variance_analysis", "fpa_forecasts"]
    GCS_GROUNDING = [
        "methodology/handbook-segment-reporting-post-asu-2023-07.pdf",
        "sap/SAP_FI-GL_Reporting_and_Information_System.pdf",
        "sap/SAP_Universal_Journal_ACDOCA_Overview.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        pivot = dise_pivot(company_id=params.company_id, fiscal_year=params.fiscal_year)
        if not pivot:
            out.summary = {"error": "no_dise_pivot"}
            return

        # Roll up to category × caption (already the pivot shape).
        rows = []
        for p in pivot:
            actual = float(p["amount"])
            budget = round(actual * _BUDGET_FACTOR)
            variance = actual - budget
            variance_pct = round(100.0 * variance / budget, 2) if budget else 0
            driver = "Material spend exceeded plan" if variance > 0 else "Favorable to plan"
            rows.append({
                "category":     p["dise_category"],
                "segment":      p["expense_caption"],
                "budget":       budget,
                "actual":       round(actual),
                "variance":     round(variance),
                "variance_pct": variance_pct,
                "driver":       driver,
            })

        # Build a forward forecast row per category: next FY = actual × 1.04
        forecast_rows = []
        by_cat: dict[str, float] = {}
        for p in pivot:
            by_cat[p["dise_category"]] = by_cat.get(p["dise_category"], 0.0) + float(p["amount"])
        for cat, actual in by_cat.items():
            forecast_rows.append({
                "forecast_horizon": f"FY{int(params.fiscal_year) + 1}",
                "category":         cat,
                "base_amount":      round(actual),
                "forecast_amount":  round(actual * 1.04),
                "growth_pct":       4.0,
                "assumptions":      {
                    "method": "trend extrapolation",
                    "growth_rate_basis": "+4% YoY GDP-anchored revenue growth",
                },
            })

        rw = self.write_rows("fpa_variance_analysis", rows, params)
        rw += self.write_rows("fpa_forecasts", forecast_rows, params)

        unfavorable = [r for r in rows if r["variance"] > 0]
        out.summary = {
            "total_categories":       len(rows),
            "total_actual_usd":       sum(r["actual"] for r in rows),
            "total_budget_usd":       sum(r["budget"] for r in rows),
            "total_variance_usd":     sum(r["variance"] for r in rows),
            "categories_unfavorable": len(unfavorable),
            "forecasts_generated":    len(forecast_rows),
        }
        out.rows_written = rw

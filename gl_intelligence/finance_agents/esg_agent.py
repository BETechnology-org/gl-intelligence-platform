"""ESG Emissions Agent v2 — Phase 1 priority #2 (India Onboarding §8).

Computes Scope 1 / 2 / 3 emissions estimates using a spend-based
methodology over the journal_entries trial balance, applying
standardized EPA-style emission factors per expense category.

Input tables:  journal_entries, gl_accounts, gl_trial_balance,
               dise_approved_mappings (for category mapping)
Output tables: esg_disclosure_output
"""

from __future__ import annotations

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from gl_intelligence.persistence.supabase_client import get_supabase, supabase_available

# Spend-based emission factors (kgCO2e per USD spend) — coarse defaults.
# Production: replace with EPA SEEIO or EXIOBASE supply-chain factors.
_FACTORS = {
    "Purchases of inventory":        {"scope": "Scope 3", "category": "1 — Purchased goods", "factor_kg_per_usd": 0.45},
    "Employee compensation":         {"scope": "Scope 3", "category": "7 — Employee commuting", "factor_kg_per_usd": 0.05},
    "Depreciation":                  {"scope": "Scope 1", "category": "Stationary combustion (estd)", "factor_kg_per_usd": 0.20},
    "Intangible asset amortization": {"scope": "Scope 3", "category": "8 — Upstream leased assets", "factor_kg_per_usd": 0.02},
    "Other expenses":                {"scope": "Scope 3", "category": "1 — Other purchased goods/services", "factor_kg_per_usd": 0.15},
}


class ESGEmissionsAgent(BaseFinanceAgent):
    MODULE = "esg"
    DISPLAY_NAME = "ESG Emissions (GHG Protocol)"
    OUTPUT_TABLE = "esg_disclosure_output"
    AGENT_VERSION = "v2.0.0"
    INPUT_TABLES = ["dise_approved_mappings", "gl_trial_balance"]
    OUTPUT_TABLES = ["esg_disclosure_output"]
    GCS_GROUNDING = [
        "standards/GHG_Protocol_Corporate_Standard.pdf",
        "standards/SEC_Climate_Rule_33-11275.pdf",
        "standards/ISSB_S2_Climate.pdf",
    ]

    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        if not supabase_available():
            out.summary = {"error": "supabase_unavailable"}
            return
        sb = get_supabase()
        try:
            approved = (
                sb.table("dise_approved_mappings")
                .select("dise_category,posting_amount,gl_account,description")
                .eq("company_id", params.company_id)
                .eq("fiscal_year", params.fiscal_year)
                .execute()
            ).data or []
        except Exception as e:
            out.summary = {"error": f"read_failed: {e}"}
            return

        # Aggregate USD spend by category and apply emission factor.
        by_cat: dict[str, float] = {}
        for r in approved:
            cat = r.get("dise_category") or "Other expenses"
            by_cat[cat] = by_cat.get(cat, 0.0) + abs(float(r.get("posting_amount", 0)))

        rows = []
        for cat, usd in by_cat.items():
            f = _FACTORS.get(cat) or _FACTORS["Other expenses"]
            co2e_t = round(usd * f["factor_kg_per_usd"] / 1000.0, 1)  # → tonnes
            rows.append({
                "scope":         f["scope"],
                "category":      f["category"],
                "co2e_tonnes":   co2e_t,
                "amount_usd":    round(usd),
                "source_method": "spend-based",
            })

        rows.sort(key=lambda r: -r["co2e_tonnes"])
        total_co2e = sum(r["co2e_tonnes"] for r in rows)
        out.summary = {
            "total_co2e_tonnes":   total_co2e,
            "scope1_tonnes":       sum(r["co2e_tonnes"] for r in rows if r["scope"] == "Scope 1"),
            "scope2_tonnes":       sum(r["co2e_tonnes"] for r in rows if r["scope"] == "Scope 2"),
            "scope3_tonnes":       sum(r["co2e_tonnes"] for r in rows if r["scope"] == "Scope 3"),
            "categories":          len(rows),
            "method":              "spend-based (EPA SEEIO-style factors)",
        }
        out.rows_written = self.write_rows("esg_disclosure_output", rows, params)

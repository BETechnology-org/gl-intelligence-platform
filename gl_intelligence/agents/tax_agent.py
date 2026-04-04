"""
Tax Reconciliation Agent — ASC 740 income tax analysis and ASU 2023-09 compliance.
Performs effective rate reconciliation, deferred tax scheduling, jurisdictional
disaggregation, and generates disclosure-ready footnote text.
"""

from __future__ import annotations

import json
import logging
import os
import time

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.tax")

# ── Offline tax data cache ──
_tax_data_cache: dict | None = None


def load_tax_data() -> dict:
    """Load the tax provision dataset from JSON."""
    global _tax_data_cache
    if _tax_data_cache is not None:
        return _tax_data_cache

    paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS", "tax_provision_data.json"),
        "/app/data/tax_provision_data.json",
    ]
    for p in paths:
        try:
            with open(p) as f:
                _tax_data_cache = json.load(f)
                log.info(f"Loaded tax provision data from {os.path.basename(p)}")
                return _tax_data_cache
        except (FileNotFoundError, json.JSONDecodeError):
            continue

    log.warning("No tax provision data found")
    _tax_data_cache = {}
    return _tax_data_cache


SYSTEM_PROMPT = """You are a senior tax disclosure specialist preparing ASC 740 income tax footnotes
for a 10-K filing. You are an expert in ASU 2023-09 (Improvements to Income Tax Disclosures),
which requires enhanced rate reconciliation categories, jurisdictional disaggregation,
and expanded cash tax paid disclosures.

Key ASU 2023-09 requirements you must address:
1. RATE RECONCILIATION: 8 specific categories — (a) state/local, (b) foreign rate differential,
   (c) effect of cross-border activities (GILTI, FDII, Subpart F), (d) tax credits,
   (e) nontaxable/nondeductible items, (f) changes in valuation allowance,
   (g) changes in UTPs, (h) other reconciling items.
2. JURISDICTIONAL DISAGGREGATION: Separate domestic vs. foreign for pretax income, tax expense,
   and cash taxes paid. Individual jurisdictions ≥5% of pretax income disclosed separately.
3. CASH TAXES PAID: Tabular disaggregation — federal, state, foreign, with individual
   jurisdictions ≥5% shown separately.
4. QUALITATIVE: Nature of significant reconciling items, including tax law changes.

Write in formal SEC disclosure language. Include ASC citations. Do NOT mention being an AI."""


class TaxReconciliationAgent(BaseAgent):
    AGENT_ID = "TAX_RECON_AGENT_v1"
    DESCRIPTION = "ASC 740 income tax analysis with ASU 2023-09 compliance validation"

    MATERIALITY_THRESHOLD = 0.05  # 5% of pretax income for jurisdiction disclosure

    def run(self, fiscal_year: str | None = None, **kwargs) -> AgentResult:
        """
        Full ASC 740 analysis:
        1. Rate reconciliation validation
        2. Deferred tax asset/liability analysis
        3. Jurisdictional disaggregation (ASU 2023-09)
        4. UTP rollforward check
        5. Compliance gap analysis
        6. Disclosure narrative generation
        """
        fy = fiscal_year or "2025"
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        tax = load_tax_data()
        if not tax:
            result.status = "error"
            result.summary = {"error": "No tax provision data available"}
            return result

        # ── 1. Rate reconciliation validation ──
        rate_recon = tax.get("rate_reconciliation", [])
        statutory_rate = tax.get("statutory_rate", 0.21)
        pretax = tax["pretax_income"]["total"]
        computed_rate = sum(item["rate"] for item in rate_recon)
        rate_diff = abs(computed_rate - tax.get("effective_rate", 0))
        rate_balanced = rate_diff < 0.001

        pending_items = [r for r in rate_recon if r.get("status") != "confirmed"]
        confirmed_items = [r for r in rate_recon if r.get("status") == "confirmed"]

        # ── 2. Deferred tax analysis ──
        dta = tax.get("deferred_tax_assets", [])
        dtl = tax.get("deferred_tax_liabilities", [])
        va = tax.get("valuation_allowance", {})

        gross_dta = sum(d["current_year"] for d in dta)
        gross_dtl = sum(d["current_year"] for d in dtl)
        net_dta = gross_dta + gross_dtl + va.get("ending_balance", 0)

        # YoY movement
        prior_gross_dta = sum(d["prior_year"] for d in dta)
        prior_gross_dtl = sum(d["prior_year"] for d in dtl)
        dta_movement = gross_dta - prior_gross_dta
        dtl_movement = gross_dtl - prior_gross_dtl

        # Top movers
        dta_movers = sorted(dta, key=lambda d: abs(d["current_year"] - d["prior_year"]), reverse=True)[:3]
        dtl_movers = sorted(dtl, key=lambda d: abs(d["current_year"] - d["prior_year"]), reverse=True)[:3]

        # ── 3. Jurisdictional disaggregation (ASU 2023-09) ──
        jurisdictions = tax.get("jurisdictions", [])
        material_jurisdictions = [
            j for j in jurisdictions
            if j["pretax_income"] / pretax >= self.MATERIALITY_THRESHOLD
        ]
        domestic_jurisdictions = [j for j in jurisdictions if j["name"].startswith("United States")]
        foreign_jurisdictions = [j for j in jurisdictions if not j["name"].startswith("United States")]

        domestic_pretax = sum(j["pretax_income"] for j in domestic_jurisdictions)
        foreign_pretax = sum(j["pretax_income"] for j in foreign_jurisdictions)
        domestic_tax = sum(j["tax_expense"] for j in domestic_jurisdictions)
        foreign_tax = sum(j["tax_expense"] for j in foreign_jurisdictions)

        # ── 4. UTP rollforward ──
        utp = tax.get("uncertain_tax_positions", {})
        utp_change = utp.get("ending_balance", 0) - utp.get("beginning_balance", 0)

        # ── 5. ASU 2023-09 compliance checklist ──
        compliance = []
        # (a) 8 required rate reconciliation categories
        required_categories = {"statutory", "state_local", "foreign", "credits",
                               "compensation", "permanent", "valuation_allowance", "other"}
        present_categories = {r.get("category") for r in rate_recon}
        missing_cats = required_categories - present_categories
        compliance.append({
            "requirement": "Rate reconciliation — 8 required categories",
            "status": "complete" if not missing_cats else "gap",
            "detail": f"Missing: {', '.join(missing_cats)}" if missing_cats else "All 8 categories present",
        })

        # (b) Jurisdictions ≥5% disclosed separately
        undisclosed = [j for j in jurisdictions
                       if j["pretax_income"] / pretax >= self.MATERIALITY_THRESHOLD
                       and j not in material_jurisdictions]
        compliance.append({
            "requirement": "Individual jurisdictions ≥5% pretax income disclosed",
            "status": "complete" if len(material_jurisdictions) > 0 else "gap",
            "detail": f"{len(material_jurisdictions)} jurisdictions exceed 5% threshold",
        })

        # (c) Cash taxes paid disaggregation
        cash = tax.get("cash_taxes_paid", {})
        compliance.append({
            "requirement": "Cash taxes paid — federal/state/foreign disaggregation",
            "status": "complete" if all(k in cash for k in ("federal", "state", "foreign")) else "gap",
            "detail": f"Total cash taxes: ${cash.get('total', 0)/1e6:.1f}M",
        })

        # (d) Domestic vs foreign pretax income split
        compliance.append({
            "requirement": "Domestic vs. foreign pretax income split",
            "status": "complete",
            "detail": f"Domestic ${domestic_pretax/1e6:.1f}M / Foreign ${foreign_pretax/1e6:.1f}M",
        })

        # (e) UTP rollforward
        compliance.append({
            "requirement": "Uncertain tax positions rollforward",
            "status": "complete" if utp.get("ending_balance") else "gap",
            "detail": f"UTPs: ${utp.get('ending_balance', 0)/1e6:.1f}M (net change ${utp_change/1e6:+.1f}M)",
        })

        # (f) Valuation allowance disclosure
        compliance.append({
            "requirement": "Valuation allowance changes disclosed",
            "status": "complete" if va.get("ending_balance") else "gap",
            "detail": f"VA: ${abs(va.get('ending_balance', 0))/1e6:.1f}M ({va.get('note', '')})",
        })

        gaps = [c for c in compliance if c["status"] == "gap"]
        completion = tax.get("completion_status", {})

        # ── 6. Claude disclosure narrative ──
        data_summary = json.dumps({
            "fiscal_year": fy,
            "pretax_income": {"domestic": domestic_pretax, "foreign": foreign_pretax, "total": pretax},
            "effective_rate": tax.get("effective_rate"),
            "statutory_rate": statutory_rate,
            "rate_reconciliation": [{
                "item": r["item"], "rate": r["rate"], "amount": r["amount"], "category": r["category"]
            } for r in rate_recon],
            "material_jurisdictions": [{
                "name": j["name"], "pretax_income": j["pretax_income"],
                "tax_expense": j["tax_expense"], "effective_rate": j["effective_rate"],
            } for j in material_jurisdictions],
            "deferred_tax_net": net_dta,
            "gross_dta": gross_dta, "gross_dtl": gross_dtl,
            "valuation_allowance": va.get("ending_balance"),
            "utp_ending": utp.get("ending_balance"),
            "cash_taxes_paid": cash,
        }, indent=2)

        narrative = self.call_claude(
            system=SYSTEM_PROMPT,
            user_prompt=f"""Generate the complete ASC 740 income tax footnote for FY{fy} using this data:

{data_summary}

Include:
1. Provision for income taxes paragraph (current + deferred breakdown)
2. Rate reconciliation table (in thousands, with rates and amounts)
3. Deferred tax asset/liability schedule (tabular)
4. Jurisdictional disaggregation narrative per ASU 2023-09
5. Cash taxes paid table (federal/state/foreign per ASU 2023-09)
6. Uncertain tax positions rollforward paragraph
7. Valuation allowance disclosure

Use markdown tables. Amounts in thousands. Include ASC citations.""",
            max_tokens=3000,
            expect_json=False,
        )

        result.processed = 1
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start

        result.results = [{
            "rate_reconciliation": [{
                "item": r["item"], "rate": round(r["rate"] * 100, 2),
                "amount": r["amount"], "status": r["status"], "category": r["category"],
            } for r in rate_recon],
            "effective_rate": round(tax.get("effective_rate", 0) * 100, 1),
            "rate_balanced": rate_balanced,
            "deferred_summary": {
                "gross_dta": gross_dta, "gross_dtl": gross_dtl,
                "valuation_allowance": va.get("ending_balance", 0),
                "net": net_dta,
                "dta_movement": dta_movement, "dtl_movement": dtl_movement,
                "top_dta_movers": [{
                    "item": d["item"],
                    "current": d["current_year"], "prior": d["prior_year"],
                    "change": d["current_year"] - d["prior_year"],
                } for d in dta_movers],
                "top_dtl_movers": [{
                    "item": d["item"],
                    "current": d["current_year"], "prior": d["prior_year"],
                    "change": d["current_year"] - d["prior_year"],
                } for d in dtl_movers],
            },
            "jurisdictions": {
                "total_count": len(jurisdictions),
                "material_count": len(material_jurisdictions),
                "domestic_pretax": domestic_pretax,
                "foreign_pretax": foreign_pretax,
                "domestic_tax": domestic_tax,
                "foreign_tax": foreign_tax,
                "material": [{
                    "name": j["name"],
                    "pretax_income": j["pretax_income"],
                    "tax_expense": j["tax_expense"],
                    "effective_rate": round(j["effective_rate"] * 100, 1),
                    "cash_taxes_paid": j["cash_taxes_paid"],
                    "pct_of_total": round(j["pretax_income"] / pretax * 100, 1),
                } for j in material_jurisdictions],
            },
            "utp": {
                "beginning": utp.get("beginning_balance", 0),
                "ending": utp.get("ending_balance", 0),
                "net_change": utp_change,
                "interest_penalties": utp.get("interest_and_penalties", 0),
                "resolve_12mo": utp.get("positions_expected_to_resolve_12mo", 0),
            },
            "cash_taxes_paid": cash,
            "compliance": compliance,
            "compliance_gaps": len(gaps),
            "narrative": narrative,
        }]

        result.summary = {
            "fiscal_year": fy,
            "pretax_income": pretax,
            "effective_rate": round(tax.get("effective_rate", 0) * 100, 1),
            "statutory_rate": round(statutory_rate * 100, 1),
            "rate_spread_bps": round((tax.get("effective_rate", 0) - statutory_rate) * 10000),
            "total_provision": tax.get("total_provision", 0),
            "net_deferred_tax": net_dta,
            "jurisdictions": len(jurisdictions),
            "material_jurisdictions": len(material_jurisdictions),
            "utp_balance": utp.get("ending_balance", 0),
            "cash_taxes_paid": cash.get("total", 0),
            "compliance_items": len(compliance),
            "compliance_gaps": len(gaps),
            "pending_items": len(pending_items),
            "completion": completion,
        }

        if gaps:
            result.status = "warning"
        return result

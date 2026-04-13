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
from datetime import datetime, timezone

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient
from gl_intelligence.agents.base import BaseAgent, AgentResult

log = logging.getLogger("agents.tax")

# ── BigQuery settings ──
_BQ_BILLING_PROJECT = "trufflesai-loans"   # SA lives here, jobs billed here
_BQ_DATA_PROJECT    = "diplomatic75"        # data project
_BQ_DATASET         = "dise_reporting"

# ── Caches ──
_tax_data_cache: dict | None = None


def _load_json_base() -> dict:
    """Load the curated JSON tax provision dataset (full demo data)."""
    paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS", "tax_provision_data.json"),
        "/app/data/tax_provision_data.json",
    ]
    for p in paths:
        try:
            with open(p) as f:
                data = json.load(f)
                log.info("Loaded JSON tax base from %s", os.path.basename(p))
                return data
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    return {}


def _q(client, sql: str) -> list[dict]:
    return [dict(row) for row in client.query(sql).result()]


def _load_from_bigquery(base: dict) -> dict:
    """
    Overlay live BigQuery numbers on top of the JSON base.

    Queries diplomatic75.dise_reporting for:
      • tax_provision_universe  — provision totals (current/deferred by jurisdiction)
      • etr_reconciliation_lines — ETR waterfall items
      • taxes_paid_fact          — cash taxes paid

    Any table that is empty or unreachable falls back to the JSON base values,
    so the response always has the full shape required by renderTaxModule().
    """
    from google.cloud import bigquery
    client = bigquery.Client(project=_BQ_BILLING_PROJECT)

    dp = f"`{_BQ_DATA_PROJECT}.{_BQ_DATASET}"

    # ── 1. Provision universe ────────────────────────────────────────────────
    rows = _q(client, f"""
        SELECT
            company_code, fiscal_year,
            SUM(COALESCE(current_tax_federal,  0)) AS cf,
            SUM(COALESCE(current_tax_state,    0)) AS cs,
            SUM(COALESCE(current_tax_foreign,  0)) AS cfor,
            SUM(COALESCE(current_tax_total,    0)) AS ct,
            SUM(COALESCE(deferred_tax_federal, 0)) AS df,
            SUM(COALESCE(deferred_tax_state,   0)) AS ds,
            SUM(COALESCE(deferred_tax_foreign, 0)) AS dfor,
            SUM(COALESCE(deferred_tax_total,   0)) AS dt,
            SUM(COALESCE(total_tax_expense,    0)) AS total,
            MAX(COALESCE(effective_tax_rate,   0)) AS etr
        FROM {dp}.tax_provision_universe`
        GROUP BY company_code, fiscal_year
        ORDER BY fiscal_year DESC
        LIMIT 1
    """)

    data = dict(base)  # shallow copy; nested dicts are references — overwrite keys, don't mutate

    if rows:
        m = rows[0]
        company  = m["company_code"]
        fy       = m["fiscal_year"]
        log.info("BQ provision data: company=%s fy=%s", company, fy)

        data["_source"]    = "bigquery"
        data["_bq_ts"]     = datetime.now(timezone.utc).isoformat()
        data["_bq_company"] = company
        data["_bq_fy"]     = fy

        # Override provision components
        data["income_tax_expense_components"] = {
            "current": {
                "federal": float(m["cf"]),
                "state":   float(m["cs"]),
                "foreign": float(m["cfor"]),
                "total":   float(m["ct"]),
            },
            "deferred": {
                "federal": float(m["df"]),
                "state":   float(m["ds"]),
                "foreign": float(m["dfor"]),
                "total":   float(m["dt"]),
            },
            "total": float(m["total"]),
        }
        data["total_provision"] = float(m["total"])
        if m["etr"] and m["etr"] != 0:
            data["effective_rate"] = float(m["etr"])

    # ── 2. ETR reconciliation lines ─────────────────────────────────────────
    etr_rows = _q(client, f"""
        SELECT line_sequence, etr_line_category, line_label,
               COALESCE(amount, 0) AS amount,
               COALESCE(rate_pct, 0) AS rate_pct,
               COALESCE(pretax_income, 0) AS pretax_income
        FROM {dp}.etr_reconciliation_lines`
        WHERE company_code = (
            SELECT company_code FROM {dp}.tax_provision_universe`
            ORDER BY fiscal_year DESC LIMIT 1
        )
        AND fiscal_year = (
            SELECT fiscal_year FROM {dp}.tax_provision_universe`
            ORDER BY fiscal_year DESC LIMIT 1
        )
        ORDER BY line_sequence
    """)

    if etr_rows:
        # Build flat rate_reconciliation compatible with flattenRateRecon()
        # Map BQ etr_line_category → ASU 2023-09 asu_category codes
        _cat_map = {
            "statutory":            "1_statutory",
            "state_local":          "2_state_local",
            "foreign":              "3_foreign",
            "tax_law_changes":      "4_tax_law_changes",
            "cross_border":         "5_cross_border",
            "credits":              "6_credits",
            "valuation_allowance":  "7_valuation_allowance",
            "nontaxable":           "8_nontaxable_nondeductible",
            "nondeductible":        "8_nontaxable_nondeductible",
            "other":                "8_nontaxable_nondeductible",
        }
        # Use first row's pretax_income as the statutory base
        pretax_bq = float(etr_rows[0]["pretax_income"]) if etr_rows[0]["pretax_income"] else None

        recon = []
        for r in etr_rows:
            cat_raw = (r["etr_line_category"] or "").lower()
            asu_cat = next(
                (v for k, v in _cat_map.items() if k in cat_raw),
                "8_nontaxable_nondeductible",
            )
            recon.append({
                "asu_category": asu_cat,
                "item":         r["line_label"] or r["etr_line_category"],
                "rate":         float(r["rate_pct"]) / 100.0,
                "amount":       float(r["amount"]),
                "prior_amount": 0,
                "status":       "confirmed",
                "citation":     "",
                "is_header":    False,
            })

        data["rate_reconciliation"] = recon
        if pretax_bq and pretax_bq > 0:
            pi = data.get("pretax_income", {})
            pi = dict(pi)
            pi["total"] = pretax_bq
            data["pretax_income"] = pi

    # ── 3. Cash taxes paid ───────────────────────────────────────────────────
    cash_rows = _q(client, f"""
        SELECT jurisdiction_type, jurisdiction_name,
               COALESCE(taxes_paid_abs, ABS(taxes_paid_amount), 0) AS amount
        FROM {dp}.taxes_paid_fact`
        WHERE company_code = (
            SELECT company_code FROM {dp}.tax_provision_universe`
            ORDER BY fiscal_year DESC LIMIT 1
        )
        AND fiscal_year = (
            SELECT fiscal_year FROM {dp}.tax_provision_universe`
            ORDER BY fiscal_year DESC LIMIT 1
        )
        ORDER BY jurisdiction_type, amount DESC
    """)

    if cash_rows:
        federal = next((float(r["amount"]) for r in cash_rows if r["jurisdiction_type"] == "federal"), 0.0)
        state   = next((float(r["amount"]) for r in cash_rows if r["jurisdiction_type"] == "state"),   0.0)
        foreign = [r for r in cash_rows if r["jurisdiction_type"] == "foreign"]
        foreign_total = sum(float(r["amount"]) for r in foreign)
        total = federal + state + foreign_total

        data["cash_taxes_paid"] = {
            "federal":       federal,
            "state":         state,
            "foreign_total": foreign_total,
            "foreign_detail": [
                {"jurisdiction": r["jurisdiction_name"] or "Foreign", "amount": float(r["amount"])}
                for r in foreign
            ],
            "total": total,
        }

    return data


def load_tax_data() -> dict:
    """
    Load tax provision data.

    Priority:
    1. Cache hit — return immediately.
    2. BigQuery (diplomatic75.dise_reporting) — overlay live numbers on JSON base.
    3. JSON fallback — serve the curated demo dataset as-is.
    """
    global _tax_data_cache
    if _tax_data_cache is not None:
        return _tax_data_cache

    base = _load_json_base()

    try:
        data = _load_from_bigquery(base)
        log.info("Tax data loaded from BigQuery (source=%s)", data.get("_source"))
    except Exception as exc:
        log.warning("BigQuery unavailable (%s), falling back to JSON", exc)
        data = base
        data["_source"] = "json"

    if not data:
        log.warning("No tax provision data found")
        data = {}

    _tax_data_cache = data
    return _tax_data_cache


def flatten_rate_recon(rate_recon: list[dict]) -> list[dict]:
    """Flatten hierarchical rate reconciliation into individual line items.

    Header items (is_header=True) with sub_items are expanded: each sub_item
    becomes a row. Non-header items pass through unchanged.
    Returns a flat list of dicts with keys: item, rate, amount, prior_amount,
    asu_category, status, citation, indent (0=top, 1=sub-item).
    """
    rows = []
    for entry in rate_recon:
        if entry.get("is_header") and entry.get("sub_items"):
            cat = entry.get("asu_category", "")
            citation = entry.get("citation", "")
            # For foreign (category 3), sub_items are grouped by jurisdiction
            if any("jurisdiction" in si for si in entry["sub_items"]):
                for jur_group in entry["sub_items"]:
                    for item in jur_group.get("items", []):
                        rows.append({
                            "item": item["item"],
                            "rate": item.get("rate", 0),
                            "amount": item.get("amount", 0),
                            "prior_amount": item.get("prior_amount", 0),
                            "asu_category": cat,
                            "status": item.get("status", "confirmed"),
                            "citation": citation,
                            "indent": 1,
                            "jurisdiction": jur_group.get("jurisdiction", ""),
                        })
            else:
                # Flat sub_items (credits, cross-border, nontaxable)
                for item in entry["sub_items"]:
                    rows.append({
                        "item": item["item"],
                        "rate": item.get("rate", 0),
                        "amount": item.get("amount", 0),
                        "prior_amount": item.get("prior_amount", 0),
                        "asu_category": cat,
                        "status": item.get("status", "confirmed"),
                        "citation": citation,
                        "indent": 1,
                    })
        else:
            rows.append({
                "item": entry["item"],
                "rate": entry.get("rate", 0) or 0,
                "amount": entry.get("amount", 0) or 0,
                "prior_amount": entry.get("prior_amount", 0) or 0,
                "asu_category": entry.get("asu_category", ""),
                "status": entry.get("status", "confirmed"),
                "citation": entry.get("citation", ""),
                "indent": 0,
                "note": entry.get("note", ""),
            })
    return rows


def compute_category_totals(rate_recon: list[dict]) -> dict:
    """Compute total rate and amount per ASU category from hierarchical data."""
    totals = {}
    for entry in rate_recon:
        cat = entry.get("asu_category", "unknown")
        if entry.get("is_header") and entry.get("sub_items"):
            rate_sum = 0
            amt_sum = 0
            if any("jurisdiction" in si for si in entry["sub_items"]):
                for jur_group in entry["sub_items"]:
                    for item in jur_group.get("items", []):
                        rate_sum += item.get("rate", 0)
                        amt_sum += item.get("amount", 0)
            else:
                for item in entry["sub_items"]:
                    rate_sum += item.get("rate", 0)
                    amt_sum += item.get("amount", 0)
            totals[cat] = {"rate": rate_sum, "amount": amt_sum}
        else:
            totals[cat] = {"rate": entry.get("rate", 0) or 0, "amount": entry.get("amount", 0) or 0}
    return totals


SYSTEM_PROMPT = """You are a senior tax disclosure specialist preparing ASC 740 income tax footnotes
for a 10-K filing. You are an expert in ASU 2023-09 (Improvements to Income Tax Disclosures),
which requires enhanced rate reconciliation categories, jurisdictional disaggregation,
and expanded cash tax paid disclosures.

Key ASU 2023-09 requirements you must address:
1. RATE RECONCILIATION (ASC 740-10-50-12 as amended): 8+ specific categories with BOTH
   percentages AND dollar amounts. Headers with sub-items for foreign, cross-border, credits,
   and nontaxable/nondeductible. 5% threshold = 5% of (pretax income x statutory rate).
2. INCOME TAX EXPENSE COMPONENTS (ASC 740-10-50-9/10): Current vs deferred breakdown
   by jurisdiction (federal, state, foreign) — tabular format.
3. JURISDICTIONAL DISAGGREGATION: Individual jurisdictions >= 5% of total pretax income
   disclosed separately with statutory rate, pretax income, total tax, effective rate.
4. CASH TAXES PAID (ASU 2023-09): Federal, state, foreign with individual foreign
   jurisdictions >= 5% of total cash taxes shown separately.
5. CARRYFORWARDS (ASC 740-10-50-3): NOL and credit carryforwards with expiration schedules,
   gross amounts, tax-effected amounts, and valuation allowance applied.
6. UNCERTAIN TAX POSITIONS (ASC 740-10-50-15): Full rollforward with open tax years by
   jurisdiction, interest/penalty policy, and amounts expected to resolve within 12 months.
7. UNREMITTED FOREIGN EARNINGS (ASC 740-30): Indefinitely reinvested earnings assertion.
8. QUALITATIVE: Nature of significant reconciling items, state identification where >50%.

Write in formal SEC disclosure language. Include ASC citations. Do NOT mention being an AI."""


class TaxReconciliationAgent(BaseAgent):
    AGENT_ID = "TAX_RECON_AGENT_v1"
    DESCRIPTION = "ASC 740 income tax analysis with ASU 2023-09 compliance validation"

    MATERIALITY_THRESHOLD = 0.05  # 5% of pretax income for jurisdiction disclosure

    def run(self, fiscal_year: str | None = None, **kwargs) -> AgentResult:
        """
        Full ASC 740 analysis:
        1. Income tax expense components (current/deferred x fed/state/foreign)
        2. Rate reconciliation validation (hierarchical with sub-items)
        3. Deferred tax asset/liability analysis
        4. Carryforward schedule analysis
        5. Jurisdictional disaggregation (ASU 2023-09)
        6. Cash taxes paid with foreign detail
        7. UTP rollforward with open tax years
        8. Compliance gap analysis
        9. Disclosure narrative generation
        """
        fy = fiscal_year or "2025"
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        tax = load_tax_data()
        if not tax:
            result.status = "error"
            result.summary = {"error": "No tax provision data available"}
            return result

        pretax = tax["pretax_income"]["total"]
        statutory_rate = tax.get("statutory_rate", 0.21)
        materiality_threshold_amt = tax.get("materiality_threshold_amount", pretax * statutory_rate * 0.05)

        # ── 1. Income tax expense components (ASC 740-10-50-9/10) ──
        expense = tax.get("income_tax_expense_components", {})
        prior_expense = tax.get("prior_income_tax_expense_components", {})
        expense_summary = {
            "current": expense.get("current", {}),
            "deferred": expense.get("deferred", {}),
            "total": expense.get("total", 0),
            "prior_current": prior_expense.get("current", {}),
            "prior_deferred": prior_expense.get("deferred", {}),
            "prior_total": prior_expense.get("total", 0),
        }

        # ── 2. Rate reconciliation validation (hierarchical) ──
        rate_recon = tax.get("rate_reconciliation", [])
        flat_items = flatten_rate_recon(rate_recon)
        category_totals = compute_category_totals(rate_recon)

        computed_rate = sum(row["rate"] for row in flat_items)
        computed_amount = sum(row["amount"] for row in flat_items)
        rate_diff = abs(computed_rate - tax.get("effective_rate", 0))
        rate_balanced = rate_diff < 0.002
        amount_diff = abs(computed_amount - tax.get("total_provision", 0))
        amount_balanced = amount_diff < 50000  # within $50K tolerance

        pending_items = [r for r in flat_items if r.get("status") not in ("confirmed", None)]
        confirmed_count = sum(1 for r in flat_items if r.get("status") == "confirmed")

        # Items exceeding 5% materiality threshold
        material_recon_items = [
            r for r in flat_items
            if abs(r["amount"]) >= materiality_threshold_amt and r.get("asu_category") != "1_statutory"
        ]

        # ── 3. Deferred tax analysis ──
        dta = tax.get("deferred_tax_assets", [])
        dtl = tax.get("deferred_tax_liabilities", [])
        va = tax.get("valuation_allowance", {})

        gross_dta = sum(d["current_year"] for d in dta)
        gross_dtl = sum(d["current_year"] for d in dtl)
        net_dta = gross_dta + gross_dtl + va.get("ending_balance", 0)

        prior_gross_dta = sum(d["prior_year"] for d in dta)
        prior_gross_dtl = sum(d["prior_year"] for d in dtl)
        dta_movement = gross_dta - prior_gross_dta
        dtl_movement = gross_dtl - prior_gross_dtl

        dta_movers = sorted(dta, key=lambda d: abs(d["current_year"] - d["prior_year"]), reverse=True)[:3]
        dtl_movers = sorted(dtl, key=lambda d: abs(d["current_year"] - d["prior_year"]), reverse=True)[:3]

        # ── 4. Carryforward schedules (ASC 740-10-50-3) ──
        carryforwards = tax.get("carryforwards", [])
        total_cf_tax_effected = sum(cf.get("tax_effected", 0) for cf in carryforwards)
        total_cf_va = sum(cf.get("va_applied", 0) for cf in carryforwards)

        # ── 5. Jurisdictional disaggregation (ASU 2023-09) ──
        jurisdictions = tax.get("jurisdictions", [])
        material_jurisdictions = [
            j for j in jurisdictions
            if j.get("pretax_income", 0) / pretax >= self.MATERIALITY_THRESHOLD
        ]
        domestic_pretax = tax["pretax_income"]["domestic"]
        foreign_pretax = tax["pretax_income"]["foreign"]
        domestic_tax = expense.get("current", {}).get("federal", 0) + expense.get("current", {}).get("state", 0) + expense.get("deferred", {}).get("federal", 0) + expense.get("deferred", {}).get("state", 0)
        foreign_tax = expense.get("current", {}).get("foreign", 0) + expense.get("deferred", {}).get("foreign", 0)

        # ── 6. Cash taxes paid with foreign detail ──
        cash = tax.get("cash_taxes_paid", {})
        prior_cash = tax.get("prior_cash_taxes_paid", {})
        foreign_detail = cash.get("foreign_detail", [])
        cash_threshold = cash.get("total", 0) * 0.05
        material_foreign_cash = [fd for fd in foreign_detail if fd.get("amount", 0) >= cash_threshold]

        # ── 7. UTP rollforward with open tax years ──
        utp = tax.get("uncertain_tax_positions", {})
        utp_change = utp.get("ending_balance", 0) - utp.get("beginning_balance", 0)
        open_tax_years = utp.get("open_tax_years", {})

        # ── 8. Unremitted foreign earnings ──
        unremitted = tax.get("unremitted_foreign_earnings", {})

        # ── 9. ASU 2023-09 compliance checklist ──
        compliance = []

        # (a) 8 required rate reconciliation categories
        required_asu_categories = {
            "1_statutory", "2_state_local", "3_foreign", "4_tax_law_changes",
            "5_cross_border", "6_credits", "7_valuation_allowance", "8_nontaxable_nondeductible"
        }
        present_categories = {r.get("asu_category") for r in rate_recon}
        missing_cats = required_asu_categories - present_categories
        compliance.append({
            "requirement": "Rate reconciliation — 8 required ASU 2023-09 categories",
            "status": "complete" if not missing_cats else "gap",
            "detail": f"Missing: {', '.join(missing_cats)}" if missing_cats else "All 8 categories present",
        })

        # (b) Dual format — both rates AND amounts
        compliance.append({
            "requirement": "Rate reconciliation — both % and $ amounts (ASU 2023-09)",
            "status": "complete",
            "detail": f"Rate total: {computed_rate*100:.2f}% | Amount total: ${computed_amount/1e6:.1f}M",
        })

        # (c) Income tax expense components (current/deferred x jurisdiction)
        has_expense_components = bool(expense.get("current")) and bool(expense.get("deferred"))
        compliance.append({
            "requirement": "Income tax expense — current/deferred by jurisdiction (ASC 740-10-50-9/10)",
            "status": "complete" if has_expense_components else "gap",
            "detail": f"Current: ${expense.get('current', {}).get('total', 0)/1e6:.1f}M | Deferred: ${expense.get('deferred', {}).get('total', 0)/1e6:.1f}M",
        })

        # (d) Jurisdictions >= 5% disclosed separately
        compliance.append({
            "requirement": "Individual jurisdictions ≥5% pretax income disclosed (ASU 2023-09)",
            "status": "complete" if len(material_jurisdictions) > 0 else "gap",
            "detail": f"{len(material_jurisdictions)} jurisdictions exceed 5% threshold ({', '.join(j['name'] for j in material_jurisdictions)})",
        })

        # (e) Cash taxes paid disaggregation with foreign detail
        has_foreign_detail = len(foreign_detail) > 0
        compliance.append({
            "requirement": "Cash taxes paid — fed/state/foreign with per-jurisdiction detail (ASU 2023-09)",
            "status": "complete" if has_foreign_detail else "gap",
            "detail": f"Total: ${cash.get('total', 0)/1e6:.1f}M | {len(material_foreign_cash)} foreign jurisdictions ≥5%",
        })

        # (f) Domestic vs foreign pretax income split
        compliance.append({
            "requirement": "Domestic vs. foreign pretax income split (ASC 740-10-50-6)",
            "status": "complete",
            "detail": f"Domestic ${domestic_pretax/1e6:.1f}M / Foreign ${foreign_pretax/1e6:.1f}M",
        })

        # (g) UTP rollforward with open tax years
        has_open_years = len(open_tax_years) > 0
        compliance.append({
            "requirement": "UTP rollforward with open tax years by jurisdiction",
            "status": "complete" if utp.get("ending_balance") and has_open_years else "gap",
            "detail": f"UTPs: ${utp.get('ending_balance', 0)/1e6:.1f}M | Open years: {len(open_tax_years)} jurisdictions",
        })

        # (h) Carryforward schedules
        compliance.append({
            "requirement": "NOL and credit carryforward schedules with expiration (ASC 740-10-50-3)",
            "status": "complete" if len(carryforwards) > 0 else "gap",
            "detail": f"{len(carryforwards)} carryforward categories | Tax-effected: ${total_cf_tax_effected/1e6:.1f}M | VA: ${total_cf_va/1e6:.1f}M",
        })

        # (i) Valuation allowance disclosure with rollforward
        va_has_rollforward = all(k in va for k in ("beginning_balance", "ending_balance", "charged_to_expense"))
        compliance.append({
            "requirement": "Valuation allowance rollforward disclosed",
            "status": "complete" if va_has_rollforward else "gap",
            "detail": f"VA: ${abs(va.get('ending_balance', 0))/1e6:.1f}M | Change: ${(va.get('ending_balance', 0) - va.get('beginning_balance', 0))/1e6:+.1f}M",
        })

        # (j) Unremitted foreign earnings
        compliance.append({
            "requirement": "Unremitted foreign earnings assertion (ASC 740-30)",
            "status": "complete" if unremitted.get("amount") else "gap",
            "detail": f"${unremitted.get('amount', 0)/1e6:.0f}M indefinitely reinvested" if unremitted.get("amount") else "Not disclosed",
        })

        gaps = [c for c in compliance if c["status"] == "gap"]
        completion = tax.get("completion_status", {})

        # ── 10. Claude disclosure narrative ──
        data_summary = json.dumps({
            "fiscal_year": fy,
            "pretax_income": tax["pretax_income"],
            "prior_pretax_income": tax.get("prior_pretax_income"),
            "effective_rate": tax.get("effective_rate"),
            "statutory_rate": statutory_rate,
            "total_provision": tax.get("total_provision"),
            "income_tax_expense_components": expense,
            "prior_income_tax_expense_components": prior_expense,
            "rate_reconciliation_by_category": {
                cat: totals for cat, totals in category_totals.items()
            },
            "rate_reconciliation_detail": [{
                "item": r["item"], "rate": r["rate"], "amount": r["amount"],
                "asu_category": r["asu_category"],
            } for r in flat_items],
            "material_jurisdictions": [{
                "name": j["name"], "statutory_rate": j.get("statutory_rate"),
                "pretax_income": j["pretax_income"], "total_tax": j.get("total_tax"),
                "effective_rate": j.get("effective_rate"), "note": j.get("note", ""),
            } for j in material_jurisdictions],
            "carryforwards": carryforwards,
            "deferred_tax_net": net_dta,
            "gross_dta": gross_dta, "gross_dtl": gross_dtl,
            "valuation_allowance": va,
            "cash_taxes_paid": cash,
            "prior_cash_taxes_paid": prior_cash,
            "uncertain_tax_positions": utp,
            "unremitted_foreign_earnings": unremitted,
        }, indent=2)

        narrative = self.call_claude(
            system=SYSTEM_PROMPT,
            user_prompt=f"""Generate the complete ASC 740 income tax footnote for FY{fy} using this data:

{data_summary}

Include ALL of the following sections in order:
1. Provision for income taxes paragraph — current vs deferred breakdown by jurisdiction (tabular)
2. Rate reconciliation table — hierarchical with sub-items, BOTH rates and amounts (in thousands)
3. Deferred tax asset/liability schedule (tabular, current year vs prior year)
4. Valuation allowance rollforward (tabular)
5. NOL and credit carryforward schedule with expiration dates
6. Jurisdictional disaggregation narrative per ASU 2023-09
7. Cash taxes paid table — federal/state/foreign with individual foreign jurisdictions (ASU 2023-09)
8. Uncertain tax positions rollforward (tabular) with open tax years by jurisdiction
9. Unremitted foreign earnings paragraph (ASC 740-30)

Use markdown tables. Amounts in thousands. Include ASC citations.""",
            max_tokens=4000,
            expect_json=False,
        )

        result.processed = 1
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start

        result.results = [{
            "income_tax_expense": expense_summary,
            "rate_reconciliation": [{
                "item": r["item"],
                "rate": round(r["rate"] * 100, 2),
                "amount": r["amount"],
                "prior_amount": r.get("prior_amount", 0),
                "status": r.get("status", "confirmed"),
                "asu_category": r["asu_category"],
                "indent": r.get("indent", 0),
            } for r in flat_items],
            "category_totals": {
                cat: {"rate_pct": round(t["rate"] * 100, 2), "amount": t["amount"]}
                for cat, t in category_totals.items()
            },
            "effective_rate": round(tax.get("effective_rate", 0) * 100, 1),
            "rate_balanced": rate_balanced,
            "amount_balanced": amount_balanced,
            "material_recon_items": len(material_recon_items),
            "materiality_threshold": materiality_threshold_amt,
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
            "carryforwards": [{
                "type": cf["type"],
                "gross_amount": cf["gross_amount"],
                "tax_effected": cf["tax_effected"],
                "expiration": cf["expiration"],
                "va_applied": cf.get("va_applied", 0),
            } for cf in carryforwards],
            "jurisdictions": {
                "total_count": len(jurisdictions),
                "material_count": len(material_jurisdictions),
                "domestic_pretax": domestic_pretax,
                "foreign_pretax": foreign_pretax,
                "domestic_tax": domestic_tax,
                "foreign_tax": foreign_tax,
                "material": [{
                    "name": j["name"],
                    "statutory_rate": round(j.get("statutory_rate", 0) * 100, 1),
                    "pretax_income": j["pretax_income"],
                    "current_tax": j.get("current_tax", 0),
                    "deferred_tax": j.get("deferred_tax", 0),
                    "total_tax": j.get("total_tax", 0),
                    "effective_rate": round(j.get("effective_rate", 0) * 100, 1),
                    "cash_taxes_paid": j.get("cash_taxes_paid", 0),
                    "pct_of_total": round(j["pretax_income"] / pretax * 100, 1),
                    "note": j.get("note", ""),
                } for j in material_jurisdictions],
            },
            "utp": {
                "beginning": utp.get("beginning_balance", 0),
                "ending": utp.get("ending_balance", 0),
                "net_change": utp_change,
                "increases_current": utp.get("increases_current_year", 0),
                "increases_prior": utp.get("increases_prior_years", 0),
                "decreases_settlements": utp.get("decreases_settlements", 0),
                "decreases_statute": utp.get("decreases_statute_expiry", 0),
                "amount_affecting_etr": utp.get("amount_affecting_etr", 0),
                "interest_penalties_expense": utp.get("interest_and_penalties_expense", 0),
                "interest_penalties_accrued": utp.get("interest_and_penalties_accrued", 0),
                "resolve_12mo": utp.get("positions_expected_to_resolve_12mo", 0),
                "open_tax_years": open_tax_years,
            },
            "cash_taxes_paid": {
                "federal": cash.get("federal", 0),
                "state": cash.get("state", 0),
                "foreign_total": cash.get("foreign_total", 0),
                "foreign_detail": foreign_detail,
                "total": cash.get("total", 0),
                "prior_total": prior_cash.get("total", 0),
            },
            "unremitted_foreign_earnings": unremitted,
            "compliance": compliance,
            "compliance_gaps": len(gaps),
            "narrative": narrative,
        }]

        result.summary = {
            "fiscal_year": fy,
            "pretax_income": pretax,
            "total_provision": tax.get("total_provision", 0),
            "effective_rate": round(tax.get("effective_rate", 0) * 100, 1),
            "statutory_rate": round(statutory_rate * 100, 1),
            "rate_spread_bps": round((tax.get("effective_rate", 0) - statutory_rate) * 10000),
            "rate_balanced": rate_balanced,
            "amount_balanced": amount_balanced,
            "current_tax": expense.get("current", {}).get("total", 0),
            "deferred_tax": expense.get("deferred", {}).get("total", 0),
            "net_deferred_tax": net_dta,
            "carryforwards": len(carryforwards),
            "jurisdictions": len(jurisdictions),
            "material_jurisdictions": len(material_jurisdictions),
            "utp_balance": utp.get("ending_balance", 0),
            "cash_taxes_paid": cash.get("total", 0),
            "unremitted_earnings": unremitted.get("amount", 0),
            "compliance_items": len(compliance),
            "compliance_gaps": len(gaps),
            "pending_items": len(pending_items),
            "completion": completion,
        }

        if gaps:
            result.status = "warning"
        return result

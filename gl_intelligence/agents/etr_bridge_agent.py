"""
ETR Bridge Agent — aggregates approved tax GL mappings into ASU 2023-09 disclosure tables.

Pipeline position: Step 4 of 5
  SAP GL Extract → Claude Classify → Human Review → [ETR Bridge] → 10-K Disclosure

Produces three tables required by ASU 2023-09 (amending ASC 740-10-50-12):
  Table A — Effective Tax Rate Reconciliation (waterfall from 21% statutory to effective rate)
  Table B — Cash Income Taxes Paid (federal / state / foreign by jurisdiction)
  Table C — Pre-tax Income Split (domestic vs. foreign)

Also produces the income tax expense components table (ASC 740-10-50-9/10):
  Current vs. deferred, by jurisdiction (federal / state / foreign)
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict

from gl_intelligence.config import cfg
from gl_intelligence.agents.base import BaseAgent, AgentResult
from gl_intelligence.agents.tax_classifier_agent import (
    TaxClassifierAgent, TAX_CATEGORY_LABELS, SAMPLE_TAX_GL_ACCOUNTS
)
from gl_intelligence.agents.tax_agent import load_tax_data

log = logging.getLogger("agents.etr_bridge")

STATUTORY_RATE = 0.21  # US federal statutory rate (post-TCJA)

SYSTEM_PROMPT = """You are a senior tax disclosure specialist validating an ETR bridge computation
for an ASU 2023-09 compliant income tax footnote.

Review the ETR waterfall data provided and:
1. Confirm the bridge ties: statutory rate × pretax income → through reconciling items → effective rate
2. Flag any item exceeding the 5% materiality threshold that requires separate disclosure
3. Identify any ASU 2023-09 category gaps
4. Provide a concise (3-sentence) CFO-level summary of the key drivers

Be precise. Use specific ASC 740 citations. Format clearly."""


class ETRBridgeAgent(BaseAgent):
    """
    Aggregates approved ASC 740 tax GL mappings into the ETR reconciliation waterfall
    and produces Tables A, B, C ready for 10-K footnote inclusion.

    Falls back to the comprehensive tax_provision_data.json when insufficient
    approved mappings exist (fewer than 6 mapped accounts).
    """

    AGENT_ID = "ETR_BRIDGE_AGENT_v1"
    DESCRIPTION = "Aggregates approved tax GL mappings into ASU 2023-09 Tables A, B, C"

    MATERIALITY_THRESHOLD_PCT = 0.05  # 5% of (pretax income × statutory rate)

    def run(self, fiscal_year: str | None = None, **kwargs) -> AgentResult:
        """
        Full ETR bridge run:
        1. Load approved tax GL mappings from TaxClassifierAgent
        2. Aggregate amounts by ASC 740 category
        3. Compute income tax expense components (current/deferred × fed/state/foreign)
        4. Build Table A — ETR reconciliation waterfall
        5. Build Table B — Cash taxes paid with foreign detail
        6. Build Table C — Pre-tax income domestic vs. foreign split
        7. Claude validation + CFO summary
        8. Return structured disclosure output
        """
        fy = fiscal_year or cfg.FISCAL_YEAR or "2022"
        start = time.time()
        result = AgentResult(agent_id=self.AGENT_ID, status="success", started_at=self.now_iso())

        # ── Load approved mappings ──────────────────────────────────────────
        classifier = TaxClassifierAgent(self.cx)
        approved = classifier.get_approved_tax_mappings()

        # If fewer than 6 approved mappings, use the full tax provision dataset
        # (allows the system to function before the classifier has been run)
        use_provision_fallback = len(approved) < 6
        provision_data = load_tax_data()

        if use_provision_fallback:
            log.info(f"Insufficient approved mappings ({len(approved)}); using tax_provision_data fallback")

        # ── Step 1: Aggregate by category ──────────────────────────────────
        category_totals: dict[str, float] = defaultdict(float)
        category_accounts: dict[str, list[dict]] = defaultdict(list)

        if approved and not use_provision_fallback:
            for m in approved:
                cat = m.get("tax_category", "not_tax_account")
                if cat == "not_tax_account":
                    continue
                amt = float(m.get("posting_amount", 0))
                category_totals[cat] += amt
                category_accounts[cat].append({
                    "gl_account": m["gl_account"],
                    "description": m.get("description", ""),
                    "amount": amt,
                    "confidence": m.get("confidence_score", 0),
                })
        else:
            # Bootstrap from the sample accounts (uses deck's C006/FY2022 amounts)
            for acc in SAMPLE_TAX_GL_ACCOUNTS:
                # We need the category — use description heuristics to assign
                desc = acc.get("description", "").lower()
                gl = acc["gl_account"]
                amt = float(acc.get("posting_amount", 0))

                if gl.startswith("00001600"):
                    if "federal" in desc:
                        cat = "current_federal"
                    elif "state" in desc or "local" in desc:
                        cat = "current_state"
                    else:
                        cat = "current_foreign"
                elif gl.startswith("00001610"):
                    if "federal" in desc:
                        cat = "deferred_federal"
                    elif "state" in desc or "local" in desc:
                        cat = "deferred_state"
                    else:
                        cat = "deferred_foreign"
                elif gl.startswith("00001620"):
                    cat = "deferred_tax_asset"
                elif gl.startswith("00001630"):
                    cat = "deferred_tax_liab"
                elif "domestic" in desc:
                    cat = "pretax_domestic"
                elif "foreign" in desc and "income before" in desc.lower():
                    cat = "pretax_foreign"
                else:
                    cat = "not_tax_account"

                if cat != "not_tax_account":
                    category_totals[cat] += amt
                    category_accounts[cat].append({
                        "gl_account": gl,
                        "description": acc.get("description", ""),
                        "amount": amt,
                        "confidence": 0.95,
                    })

        # ── Step 2: Income tax expense components ───────────────────────────
        if provision_data and use_provision_fallback:
            exp = provision_data.get("income_tax_expense_components", {})
            current = exp.get("current", {})
            deferred = exp.get("deferred", {})
        else:
            current = {
                "federal":  category_totals.get("current_federal", 0),
                "state":    category_totals.get("current_state", 0),
                "foreign":  category_totals.get("current_foreign", 0),
                "total":    (category_totals.get("current_federal", 0)
                             + category_totals.get("current_state", 0)
                             + category_totals.get("current_foreign", 0)),
            }
            deferred = {
                "federal":  category_totals.get("deferred_federal", 0),
                "state":    category_totals.get("deferred_state", 0),
                "foreign":  category_totals.get("deferred_foreign", 0),
                "total":    (category_totals.get("deferred_federal", 0)
                             + category_totals.get("deferred_state", 0)
                             + category_totals.get("deferred_foreign", 0)),
            }

        total_tax_expense = current["total"] + deferred["total"]

        # ── Step 3: Pre-tax income ───────────────────────────────────────────
        if provision_data and use_provision_fallback:
            pretax_dom   = provision_data["pretax_income"]["domestic"]
            pretax_for   = provision_data["pretax_income"]["foreign"]
        else:
            pretax_dom   = category_totals.get("pretax_domestic", 0)
            pretax_for   = category_totals.get("pretax_foreign", 0)

        pretax_total = pretax_dom + pretax_for

        if pretax_total == 0:
            result.status = "error"
            result.summary = {"error": "No pretax income accounts found in approved mappings"}
            return result

        statutory_tax_base = pretax_total * STATUTORY_RATE
        effective_rate = total_tax_expense / pretax_total if pretax_total else 0
        materiality_threshold = abs(statutory_tax_base) * self.MATERIALITY_THRESHOLD_PCT

        # ── Step 4: Table A — ETR Reconciliation Waterfall ──────────────────
        table_a = self._build_table_a(
            pretax_total, pretax_dom, pretax_for,
            current, deferred, total_tax_expense,
            effective_rate, materiality_threshold,
            provision_data if use_provision_fallback else None,
        )

        # ── Step 5: Table B — Cash Taxes Paid ───────────────────────────────
        table_b = self._build_table_b(provision_data)

        # ── Step 6: Table C — Pre-tax Income Split ───────────────────────────
        table_c = self._build_table_c(pretax_dom, pretax_for, pretax_total)

        # ── Step 7: Claude validation + CFO summary ───────────────────────────
        bridge_data = {
            "fiscal_year": fy,
            "pretax_total": pretax_total,
            "statutory_rate": STATUTORY_RATE,
            "statutory_tax_base": statutory_tax_base,
            "total_tax_expense": total_tax_expense,
            "effective_rate": round(effective_rate, 4),
            "table_a_items": [{
                "item": r["item"],
                "amount": r["amount"],
                "rate_pct": r["rate_pct"],
                "is_prescribed": r.get("is_prescribed", False),
            } for r in table_a],
            "table_b_summary": {"total": table_b[-1]["amount"] if table_b else 0},
            "table_c": {"domestic": pretax_dom, "foreign": pretax_for, "total": pretax_total},
            "accounts_used": len(approved) if not use_provision_fallback else "provision_data_fallback",
        }

        validation = self.call_claude(
            system=SYSTEM_PROMPT,
            user_prompt=f"""Validate this ETR bridge for FY{fy} ASU 2023-09 compliance:

{json.dumps(bridge_data, indent=2)}

Statutory rate: 21% × ${pretax_total/1e6:.1f}M = ${statutory_tax_base/1e6:.1f}M
Effective rate achieved: {effective_rate*100:.2f}%
Total tax expense: ${total_tax_expense/1e6:.2f}M
Materiality threshold (5%): ${materiality_threshold/1e6:.2f}M

Confirm the bridge ties, flag any prescribed items, and provide a 3-sentence CFO summary.""",
            max_tokens=800,
            expect_json=False,
        )

        result.processed = len(approved) if not use_provision_fallback else len(SAMPLE_TAX_GL_ACCOUNTS)
        result.completed_at = self.now_iso()
        result.elapsed_seconds = time.time() - start

        result.results = [{
            "fiscal_year": fy,
            "data_source": "provision_fallback" if use_provision_fallback else "approved_mappings",
            "accounts_processed": result.processed,
            "pretax_income": {
                "domestic": pretax_dom,
                "foreign":  pretax_for,
                "total":    pretax_total,
            },
            "income_tax_components": {
                "current":  current,
                "deferred": deferred,
                "total":    total_tax_expense,
            },
            "statutory_rate":       STATUTORY_RATE,
            "effective_rate":       round(effective_rate, 4),
            "effective_rate_pct":   round(effective_rate * 100, 2),
            "materiality_threshold": materiality_threshold,
            "table_a": table_a,
            "table_b": table_b,
            "table_c": table_c,
            "validation": validation,
            "category_detail": {
                cat: {
                    "total": total,
                    "label": TAX_CATEGORY_LABELS.get(cat, cat),
                    "accounts": category_accounts[cat],
                }
                for cat, total in category_totals.items()
                if cat != "not_tax_account"
            },
        }]

        result.summary = {
            "fiscal_year":        fy,
            "pretax_total":       pretax_total,
            "total_tax_expense":  total_tax_expense,
            "effective_rate_pct": round(effective_rate * 100, 2),
            "statutory_rate_pct": STATUTORY_RATE * 100,
            "spread_bps":         round((effective_rate - STATUTORY_RATE) * 10000),
            "table_a_lines":      len(table_a),
            "prescribed_items":   sum(1 for r in table_a if r.get("is_prescribed")),
            "materiality_threshold": materiality_threshold,
            "data_source":        "provision_fallback" if use_provision_fallback else "approved_mappings",
        }

        if abs(effective_rate - STATUTORY_RATE) > 0.10:
            result.status = "warning"

        return result

    # ── Table builders ───────────────────────────────────────────────────────

    def _build_table_a(
        self, pretax_total, pretax_dom, pretax_for,
        current, deferred, total_tax, effective_rate,
        materiality_threshold, provision_data=None,
    ) -> list[dict]:
        """Build Table A: ETR reconciliation waterfall per ASU 2023-09."""

        # If we have the full provision dataset, use its detailed rate reconciliation
        if provision_data:
            from gl_intelligence.agents.tax_agent import flatten_rate_recon
            rr = provision_data.get("rate_reconciliation", [])
            if rr:
                rows = []
                for item in flatten_rate_recon(rr):
                    amt = item["amount"]
                    rate_pct = item["rate"] * 100 if item["rate"] else 0
                    rows.append({
                        "item":         item["item"],
                        "amount":       amt,
                        "rate_pct":     round(rate_pct, 2),
                        "asu_category": item.get("asu_category", ""),
                        "citation":     item.get("citation", "ASC 740-10-50-12"),
                        "is_prescribed": abs(amt) >= materiality_threshold and item.get("asu_category") != "1_statutory",
                        "indent":       item.get("indent", 0),
                        "status":       item.get("status", "confirmed"),
                    })
                return rows

        # Compute from aggregated GL data
        statutory_amt   = pretax_total * STATUTORY_RATE
        state_local_amt = current.get("state", 0) + deferred.get("state", 0)
        foreign_total   = (current.get("foreign", 0) + deferred.get("foreign", 0))
        foreign_rate_diff = foreign_total - (pretax_for * STATUTORY_RATE)
        deferred_net    = deferred.get("federal", 0)
        other_adj       = total_tax - statutory_amt - state_local_amt - foreign_rate_diff - deferred_net

        rows = [
            {
                "item":         f"Income tax at US federal statutory rate ({STATUTORY_RATE*100:.0f}%)",
                "amount":       round(statutory_amt),
                "rate_pct":     STATUTORY_RATE * 100,
                "asu_category": "1_statutory",
                "citation":     "ASC 740-10-50-12(a)",
                "is_prescribed": False,
                "indent":       0,
                "status":       "confirmed",
            },
            {
                "item":         "State and local income taxes, net of federal benefit",
                "amount":       round(state_local_amt),
                "rate_pct":     round(state_local_amt / pretax_total * 100, 2) if pretax_total else 0,
                "asu_category": "2_state_local",
                "citation":     "ASC 740-10-50-12(b)",
                "is_prescribed": abs(state_local_amt) >= materiality_threshold,
                "indent":       0,
                "status":       "confirmed",
            },
            {
                "item":         "Foreign rate differential",
                "amount":       round(foreign_rate_diff),
                "rate_pct":     round(foreign_rate_diff / pretax_total * 100, 2) if pretax_total else 0,
                "asu_category": "3_foreign",
                "citation":     "ASC 740-10-50-12(c)",
                "is_prescribed": abs(foreign_rate_diff) >= materiality_threshold,
                "indent":       0,
                "status":       "confirmed",
            },
            {
                "item":         "Deferred tax expense",
                "amount":       round(deferred_net),
                "rate_pct":     round(deferred_net / pretax_total * 100, 2) if pretax_total else 0,
                "asu_category": "4_deferred",
                "citation":     "ASC 740-10-50-9",
                "is_prescribed": abs(deferred_net) >= materiality_threshold,
                "indent":       0,
                "status":       "confirmed",
            },
        ]

        if abs(other_adj) > 1000:
            rows.append({
                "item":         "Other, net",
                "amount":       round(other_adj),
                "rate_pct":     round(other_adj / pretax_total * 100, 2) if pretax_total else 0,
                "asu_category": "9_other",
                "citation":     "ASC 740-10-50-12",
                "is_prescribed": abs(other_adj) >= materiality_threshold,
                "indent":       0,
                "status":       "confirmed",
            })

        rows.append({
            "item":         "Total income tax expense",
            "amount":       round(total_tax),
            "rate_pct":     round(effective_rate * 100, 2),
            "asu_category": "total",
            "citation":     "ASC 740-10-50-9",
            "is_prescribed": False,
            "indent":       0,
            "status":       "confirmed",
        })
        return rows

    def _build_table_b(self, provision_data=None) -> list[dict]:
        """Build Table B: Cash income taxes paid per ASU 2023-09."""
        if provision_data:
            cash = provision_data.get("cash_taxes_paid", {})
            prior = provision_data.get("prior_cash_taxes_paid", {})
            total = cash.get("total", 0)
            cash_threshold = total * self.MATERIALITY_THRESHOLD_PCT

            rows = [
                {
                    "category":   "Federal income taxes paid",
                    "amount":     cash.get("federal", 0),
                    "prior":      prior.get("federal", 0),
                    "pct_of_total": round(cash.get("federal", 0) / total * 100, 1) if total else 0,
                    "jurisdiction": "Federal",
                },
                {
                    "category":   "State and local income taxes paid",
                    "amount":     cash.get("state", 0),
                    "prior":      prior.get("state", 0),
                    "pct_of_total": round(cash.get("state", 0) / total * 100, 1) if total else 0,
                    "jurisdiction": "State/Local",
                },
            ]

            # Foreign detail — jurisdictions ≥ 5% of total
            for fd in cash.get("foreign_detail", []):
                amt = fd.get("amount", 0)
                rows.append({
                    "category":   f"{fd.get('jurisdiction', 'Foreign')} income taxes paid",
                    "amount":     amt,
                    "prior":      fd.get("prior", 0),
                    "pct_of_total": round(amt / total * 100, 1) if total else 0,
                    "jurisdiction": fd.get("jurisdiction", "Foreign"),
                    "is_material_foreign": amt >= cash_threshold,
                })

            rows.append({
                "category":     "Total income taxes paid",
                "amount":       total,
                "prior":        prior.get("total", 0),
                "pct_of_total": 100.0,
                "jurisdiction": "Total",
                "is_total":     True,
            })
            return rows

        # Minimal fallback
        return [
            {"category": "Federal income taxes paid",       "amount": 0, "prior": 0, "pct_of_total": 0, "jurisdiction": "Federal"},
            {"category": "State and local income taxes paid","amount": 0, "prior": 0, "pct_of_total": 0, "jurisdiction": "State/Local"},
            {"category": "Foreign income taxes paid",        "amount": 0, "prior": 0, "pct_of_total": 0, "jurisdiction": "Foreign"},
            {"category": "Total income taxes paid",          "amount": 0, "prior": 0, "pct_of_total": 100.0, "jurisdiction": "Total", "is_total": True},
        ]

    def _build_table_c(self, pretax_dom, pretax_for, pretax_total) -> list[dict]:
        """Build Table C: Pre-tax income domestic vs. foreign split (ASC 740-10-50-6)."""
        return [
            {
                "segment":      "Domestic operations",
                "amount":       pretax_dom,
                "pct_of_total": round(pretax_dom / pretax_total * 100, 1) if pretax_total else 0,
                "jurisdiction": "Domestic",
            },
            {
                "segment":      "Foreign operations",
                "amount":       pretax_for,
                "pct_of_total": round(pretax_for / pretax_total * 100, 1) if pretax_total else 0,
                "jurisdiction": "Foreign",
            },
            {
                "segment":      "Income before provision for income taxes",
                "amount":       pretax_total,
                "pct_of_total": 100.0,
                "jurisdiction": "Total",
                "is_total":     True,
            },
        ]

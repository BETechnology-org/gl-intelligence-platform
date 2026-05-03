"""Live aggregate readers — power the legacy /app dashboard from Supabase.

Replaces the static `tax_provision_data.json` and `v_dise_pivot` reads
with live computations against the approved-mapping tables. When
Supabase is unavailable, returns None and callers fall back to the
legacy curated dataset.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .supabase_client import DEFAULT_COMPANY_ID, get_supabase

log = logging.getLogger("persistence.aggregates")


# ─── DISE pivot ─────────────────────────────────────────────────────────

def dise_pivot(*, company_id: str = DEFAULT_COMPANY_ID,
               fiscal_year: Optional[str] = None) -> Optional[list[dict]]:
    """Returns rows shaped like the legacy v_dise_pivot view:
    [{expense_caption, dise_category, amount}, ...]
    """
    sb = get_supabase()
    if sb is None:
        return None
    q = sb.table("dise_approved_mappings").select(
        "dise_category,expense_caption,posting_amount"
    ).eq("company_id", company_id)
    if fiscal_year:
        q = q.eq("fiscal_year", fiscal_year)
    try:
        rows = q.execute().data or []
    except Exception as e:  # noqa: BLE001
        log.error("dise_pivot read failed: %s", e)
        return None
    pivot: dict[tuple[str, str], float] = {}
    for r in rows:
        cap = r.get("expense_caption") or "SG&A"
        cat = r.get("dise_category") or "Other expenses"
        amt = float(r.get("posting_amount", 0))
        pivot[(cap, cat)] = pivot.get((cap, cat), 0.0) + amt
    return [
        {"expense_caption": k[0], "dise_category": k[1], "amount": round(v)}
        for k, v in sorted(pivot.items())
    ]


# ─── Tax provision (the big one — drives /api/tax/* dashboard) ────────

STATUTORY_RATE = 0.21


def tax_provision(*, company_id: str = DEFAULT_COMPANY_ID,
                  fiscal_year: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Compute the same shape as gl_intelligence/agents/tax_agent.load_tax_data()
    from approved tax mappings — so the legacy /app HTML renders without changes.
    """
    sb = get_supabase()
    if sb is None:
        return None
    q = sb.table("tax_approved_mappings").select(
        "tax_category,posting_amount,description,gl_account"
    ).eq("company_id", company_id)
    if fiscal_year:
        q = q.eq("fiscal_year", fiscal_year)
    try:
        rows = q.execute().data or []
    except Exception as e:  # noqa: BLE001
        log.error("tax_provision read failed: %s", e)
        return None
    if not rows:
        return None

    totals: dict[str, float] = {
        "current_federal": 0, "current_state": 0, "current_foreign": 0,
        "deferred_federal": 0, "deferred_state": 0, "deferred_foreign": 0,
        "deferred_tax_asset": 0, "deferred_tax_liab": 0,
        "pretax_domestic": 0, "pretax_foreign": 0,
    }
    foreign_detail: dict[str, float] = {}
    for r in rows:
        cat = r.get("tax_category", "not_tax_account")
        amt = float(r.get("posting_amount", 0))
        if cat in totals:
            totals[cat] += amt
        if cat == "current_foreign":
            jur = (r.get("description") or "Other").split("-")[1].strip().split("(")[0].strip() if " - " in (r.get("description") or "") else "Other"
            foreign_detail[jur] = foreign_detail.get(jur, 0) + amt

    pretax_dom = totals["pretax_domestic"]
    pretax_for = totals["pretax_foreign"]
    pretax = pretax_dom + pretax_for
    cur = {
        "federal": totals["current_federal"], "state": totals["current_state"],
        "foreign": totals["current_foreign"],
        "total": totals["current_federal"] + totals["current_state"] + totals["current_foreign"],
    }
    deferred = {
        "federal": totals["deferred_federal"], "state": totals["deferred_state"],
        "foreign": totals["deferred_foreign"],
        "total": totals["deferred_federal"] + totals["deferred_state"] + totals["deferred_foreign"],
    }
    total_provision = cur["total"] + deferred["total"]
    effective_rate = (total_provision / pretax) if pretax else 0.0

    statutory_amt = pretax * STATUTORY_RATE
    state_local = cur["state"] + deferred["state"]
    foreign_total = cur["foreign"] + deferred["foreign"]
    foreign_diff = foreign_total - (pretax_for * STATUTORY_RATE)
    deferred_fed = deferred["federal"]
    other_adj = total_provision - statutory_amt - state_local - foreign_diff - deferred_fed

    rate_recon = [
        {"asu_category": "1_statutory", "item": f"Income tax at US federal statutory rate ({int(STATUTORY_RATE*100)}%)",
         "rate": STATUTORY_RATE, "amount": round(statutory_amt), "prior_amount": 0,
         "status": "confirmed", "citation": "ASC 740-10-50-12(a)", "is_header": False},
        {"asu_category": "2_state_local", "item": "State and local income taxes, net of federal benefit",
         "rate": (state_local / pretax) if pretax else 0, "amount": round(state_local), "prior_amount": 0,
         "status": "confirmed", "citation": "ASC 740-10-50-12(b)", "is_header": False},
        {"asu_category": "3_foreign", "item": "Foreign rate differential",
         "rate": (foreign_diff / pretax) if pretax else 0, "amount": round(foreign_diff), "prior_amount": 0,
         "status": "confirmed", "citation": "ASC 740-10-50-12(c)", "is_header": False},
        {"asu_category": "4_deferred", "item": "Deferred tax expense — federal",
         "rate": (deferred_fed / pretax) if pretax else 0, "amount": round(deferred_fed), "prior_amount": 0,
         "status": "confirmed", "citation": "ASC 740-10-50-9", "is_header": False},
    ]
    if abs(other_adj) > 1000:
        rate_recon.append({
            "asu_category": "9_other", "item": "Other, net",
            "rate": (other_adj / pretax) if pretax else 0, "amount": round(other_adj), "prior_amount": 0,
            "status": "confirmed", "citation": "ASC 740-10-50-12", "is_header": False,
        })

    cash_taxes = {
        "federal": cur["federal"], "state": cur["state"],
        "foreign_total": cur["foreign"],
        "foreign_detail": [
            {"jurisdiction": jur, "amount": round(amt)}
            for jur, amt in sorted(foreign_detail.items(), key=lambda x: -x[1])
        ],
        "total": cur["total"],
    }

    return {
        "_source": "supabase",
        "fiscal_year": fiscal_year or "2024",
        "statutory_rate": STATUTORY_RATE,
        "effective_rate": round(effective_rate, 4),
        "total_provision": round(total_provision),
        "pretax_income": {
            "domestic": round(pretax_dom),
            "foreign": round(pretax_for),
            "total": round(pretax),
        },
        "income_tax_expense_components": {
            "current": cur, "deferred": deferred, "total": total_provision,
        },
        "rate_reconciliation": rate_recon,
        "cash_taxes_paid": cash_taxes,
        "materiality_threshold_amount": round(abs(statutory_amt) * 0.05),
        "approved_mapping_count": len(rows),
    }

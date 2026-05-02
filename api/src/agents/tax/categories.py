"""ASC 740 tax category constants and citation lookup.

Ported from gl_intelligence/agents/tax_classifier_agent.py:25-66.
Kept as a separate module so it can be imported by both the agent
strategy and the tools without circular dependencies.
"""

from __future__ import annotations

TAX_CATEGORIES = [
    "current_federal",
    "current_state",
    "current_foreign",
    "deferred_federal",
    "deferred_state",
    "deferred_foreign",
    "deferred_tax_asset",
    "deferred_tax_liab",
    "pretax_domestic",
    "pretax_foreign",
    "not_tax_account",
]

TAX_CATEGORY_LABELS = {
    "current_federal":    "Current Tax — Federal",
    "current_state":      "Current Tax — State/Local",
    "current_foreign":    "Current Tax — Foreign",
    "deferred_federal":   "Deferred Tax — Federal",
    "deferred_state":     "Deferred Tax — State/Local",
    "deferred_foreign":   "Deferred Tax — Foreign",
    "deferred_tax_asset": "Deferred Tax Asset (B/S)",
    "deferred_tax_liab":  "Deferred Tax Liability (B/S)",
    "pretax_domestic":    "Pre-tax Income — Domestic",
    "pretax_foreign":     "Pre-tax Income — Foreign",
    "not_tax_account":    "Not a Tax Account",
}

# ASU 2023-09 disclosure mapping: which ASC 740 table each category feeds
CATEGORY_TO_TABLE = {
    "current_federal":    "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "current_state":      "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "current_foreign":    "Table A — ETR Reconciliation / Table B — Cash Taxes",
    "deferred_federal":   "Table A — ETR Reconciliation",
    "deferred_state":     "Table A — ETR Reconciliation",
    "deferred_foreign":   "Table A — ETR Reconciliation",
    "deferred_tax_asset": "ASC 740-10-50-2 Deferred Schedule",
    "deferred_tax_liab":  "ASC 740-10-50-2 Deferred Schedule",
    "pretax_domestic":    "Table C — Pre-tax Income Split",
    "pretax_foreign":     "Table C — Pre-tax Income Split",
    "not_tax_account":    "Excluded",
}


# Deterministic citation table — used by lookup_asc_citation tool.
# Keyed by tax_category. The agent calls this rather than guessing
# citations, which removes a common hallucination class.
ASC_CITATIONS = {
    "current_federal":    "ASC 740-10-50-9(a)",
    "current_state":      "ASC 740-10-50-9(b)",
    "current_foreign":    "ASC 740-10-50-9(c)",
    "deferred_federal":   "ASC 740-10-50-10",
    "deferred_state":     "ASC 740-10-50-10",
    "deferred_foreign":   "ASC 740-10-50-10",
    "deferred_tax_asset": "ASC 740-10-50-2",
    "deferred_tax_liab":  "ASC 740-10-50-2",
    "pretax_domestic":    "ASC 740-10-50-6",
    "pretax_foreign":     "ASC 740-10-50-6",
    "not_tax_account":    "N/A",
}


# 8 ASU 2023-09 rate-reconciliation categories (must all be present in
# the final disclosure). Used by the compliance checklist surfaced in UI.
ASU_2023_09_RECON_CATEGORIES = [
    "1_statutory",
    "2_state_local",
    "3_foreign",
    "4_tax_law_changes",
    "5_cross_border",
    "6_credits",
    "7_valuation_allowance",
    "8_nontaxable_nondeductible",
]

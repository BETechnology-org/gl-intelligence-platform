/**
 * Mirror of api/src/agents/tax/categories.py — kept in sync by hand for v1.
 * Phase 2 will generate this from the OpenAPI schema.
 */

import type { TaxCategory } from "./api";

export const TAX_CATEGORIES: TaxCategory[] = [
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
];

export const TAX_CATEGORY_LABELS: Record<TaxCategory, string> = {
  current_federal:    "Current Tax — Federal",
  current_state:      "Current Tax — State/Local",
  current_foreign:    "Current Tax — Foreign",
  deferred_federal:   "Deferred Tax — Federal",
  deferred_state:     "Deferred Tax — State/Local",
  deferred_foreign:   "Deferred Tax — Foreign",
  deferred_tax_asset: "Deferred Tax Asset (B/S)",
  deferred_tax_liab:  "Deferred Tax Liability (B/S)",
  pretax_domestic:    "Pre-tax Income — Domestic",
  pretax_foreign:     "Pre-tax Income — Foreign",
  not_tax_account:    "Not a Tax Account",
};

export const ASC_CITATIONS_HINT: Partial<Record<TaxCategory, string>> = {
  current_federal:    "ASC 740-10-50-9(a)",
  current_state:      "ASC 740-10-50-9(b)",
  current_foreign:    "ASC 740-10-50-9(c)",
  deferred_federal:   "ASC 740-10-50-10",
  deferred_state:     "ASC 740-10-50-10",
  deferred_foreign:   "ASC 740-10-50-10",
  deferred_tax_asset: "ASC 740-10-50-2",
  deferred_tax_liab:  "ASC 740-10-50-2",
  pretax_domestic:    "ASC 740-10-50-6",
  pretax_foreign:     "ASC 740-10-50-6",
};

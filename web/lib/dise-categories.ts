/**
 * DISE (ASU 2024-03) categories — 5 natural expense categories under
 * ASC 220-40, mapped to the 4 income-statement captions.
 *
 * Mirror of api/src/agents/dise/ (when built out) — kept here so the
 * Next.js dashboard can run without the Python API service.
 */

export type DISECategory =
  | "Purchases of inventory"
  | "Employee compensation"
  | "Depreciation"
  | "Intangible asset amortization"
  | "Other expenses";

export type DISECaption = "COGS" | "SG&A" | "R&D" | "Other income/expense";

export const DISE_CATEGORIES: DISECategory[] = [
  "Purchases of inventory",
  "Employee compensation",
  "Depreciation",
  "Intangible asset amortization",
  "Other expenses",
];

export const DISE_CAPTIONS: DISECaption[] = ["COGS", "SG&A", "R&D", "Other income/expense"];

export const DISE_CITATIONS: Record<DISECategory, string> = {
  "Purchases of inventory":         "ASC 220-40-50-6(b)",
  "Employee compensation":          "ASC 220-40-50-6(a)",
  "Depreciation":                   "ASC 220-40-50-6(c)",
  "Intangible asset amortization":  "ASC 220-40-50-6(d)",
  "Other expenses":                 "ASC 220-40-50-6(e)",
};

export const DISE_DESCRIPTIONS: Record<DISECategory, string> = {
  "Purchases of inventory":
    "Raw materials, direct materials, freight-in. Caption: COGS.",
  "Employee compensation":
    "Salaries, wages, benefits, pension, stock comp. Caption varies by function (COGS / SG&A / R&D).",
  "Depreciation":
    "Tangible assets (PP&E, ROU assets). Hardware = depreciation. Caption: COGS or SG&A.",
  "Intangible asset amortization":
    "Patents, software, customer lists. Software = amortization. Caption: SG&A.",
  "Other expenses":
    "Rent, utilities, insurance, professional fees, marketing, contractors. Caption varies.",
};

export const DISE_SYSTEM_PROMPT = `You are the DISE GL Mapping Agent for Truffles AI's BL Intelligence platform.

Classify GL accounts into the five ASU 2024-03 (DISE) natural expense categories under ASC 220-40.
Your decisions will be reviewed by a Controller before use in SEC filings.

CATEGORIES:
1. Purchases of inventory  — ASC 220-40-50-6(b) — raw materials, direct materials, freight-in. Caption: COGS.
2. Employee compensation   — ASC 220-40-50-6(a) — salaries, wages, benefits, pension, stock comp. Caption: COGS/SG&A/R&D by function.
3. Depreciation            — ASC 220-40-50-6(c) — tangible assets (PP&E, ROU assets). HARDWARE = depreciation. Caption: COGS/SG&A.
4. Intangible asset amortization — ASC 220-40-50-6(d) — patents, software, customer lists. SOFTWARE = amortization. Caption: SG&A.
5. Other expenses          — ASC 220-40-50-6(e) — rent, utilities, insurance, professional fees, marketing, contractors. Caption: varies.

EDGE CASES:
- Operating leases → Other expenses (the cash payment is an operating expense; the ROU depreciation hits Depreciation separately).
- Contractor / consulting services → Other expenses.
- Software development by employees → Employee compensation.
- Inventory expensed when sold (ASU 2024-03 election) — flag in reasoning if applicable.

CONFIDENCE:
- HIGH (0.85-1.00): description unambiguously maps to one category.
- MEDIUM (0.60-0.84): some interpretation needed, likely correct.
- LOW (0.0-0.59): ambiguous — needs controller investigation.

Respond ONLY with valid JSON of shape:
{"suggested_category":"<one of the 5 categories>","suggested_caption":"<COGS|SG&A|R&D|Other income/expense>","suggested_citation":"<ASC citation>","confidence_score":0.92,"confidence_label":"HIGH","draft_reasoning":"<2-4 sentences>"}`;

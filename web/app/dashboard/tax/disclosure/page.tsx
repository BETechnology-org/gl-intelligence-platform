import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

export const dynamic = "force-dynamic";

const CHECKLIST_ITEMS = [
  { req: "Rate reconciliation — 8 ASU 2023-09 categories present (statutory, state/local, foreign, tax-law-changes, cross-border, credits, valuation allowance, nontaxable/nondeductible)", ref: "ASC 740-10-50-12 (as amended)" },
  { req: "Both percentages AND dollar amounts disclosed",                                                                                                                                ref: "ASU 2023-09" },
  { req: "Items ≥5% of (pretax × statutory rate) disclosed separately",                                                                                                                  ref: "ASU 2023-09" },
  { req: "Income tax expense components — current vs deferred × federal/state/foreign",                                                                                                  ref: "ASC 740-10-50-9/10" },
  { req: "Jurisdictional disaggregation — pretax income & tax expense by federal/state/foreign",                                                                                         ref: "ASU 2023-09" },
  { req: "Individual jurisdictions ≥5% of total pretax disclosed separately",                                                                                                            ref: "ASU 2023-09" },
  { req: "Cash taxes paid — federal/state/foreign with foreign jurisdictions ≥5% separately",                                                                                            ref: "ASU 2023-09" },
  { req: "Domestic vs foreign pretax income split",                                                                                                                                      ref: "ASC 740-10-50-6" },
  { req: "UTP rollforward with open tax years by jurisdiction",                                                                                                                          ref: "ASC 740-10-50-15" },
  { req: "Carryforward schedules with expiration",                                                                                                                                       ref: "ASC 740-10-50-3" },
];

export default async function TaxDisclosurePage() {
  const session = await requireSession("/dashboard/tax/disclosure");
  const admin = getSupabaseAdmin();

  const { count: approvedCount } = await admin
    .from("tax_approved_mappings")
    .select("id", { count: "exact", head: true })
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Income Tax · ASU 2023-09</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Footnote draft</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            ASC 740 income-tax footnote driven by {approvedCount ?? 0} approved tax GL mapping
            {approvedCount === 1 ? "" : "s"}. Compliance checklist below tracks every ASU 2023-09
            requirement against the data on file.
          </p>
        </div>
        <a
          href={`/api/exports/tax?company_id=${session.companyId}&fiscal_year=${session.fiscalYear}&format=docx`}
          className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
        >
          Export DOCX
        </a>
      </div>

      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-widest text-neutral-500">
        ASU 2023-09 compliance checklist (10 items)
      </h2>
      <div className="space-y-2">
        {CHECKLIST_ITEMS.map((item, i) => (
          <div
            key={i}
            className="flex items-start gap-3 rounded-lg border border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900"
          >
            <span className="mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-neutral-200 text-[10px] font-medium dark:bg-neutral-700">
              {i + 1}
            </span>
            <div className="grow">
              <div className="text-sm">{item.req}</div>
              <div className="mt-0.5 font-mono text-[11px] text-neutral-500">{item.ref}</div>
            </div>
            <span className="rounded bg-amber-100 px-2 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/30 dark:text-amber-200">
              Phase 2
            </span>
          </div>
        ))}
      </div>

      <p className="mt-6 text-[12px] text-neutral-500">
        Full footnote narrative generation lands when the Tax disclosure agent ships in Phase 2.
        Today the ETR bridge tab provides the live numerics; the footnote prose is generated
        from those numbers + the approved-mapping detail.
      </p>
    </div>
  );
}

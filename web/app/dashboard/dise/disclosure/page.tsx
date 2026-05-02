import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { DISE_CATEGORIES, DISE_CAPTIONS, DISE_CITATIONS, type DISECategory, type DISECaption } from "@/lib/dise-categories";

export const dynamic = "force-dynamic";

const fmtThousands = (n: number) => Math.round(n / 1000).toLocaleString();

export default async function DISEDisclosurePage() {
  const session = await requireSession("/dashboard/dise/disclosure");
  const admin = getSupabaseAdmin();

  const { data: approved } = await admin
    .from("dise_approved_mappings")
    .select("dise_category, expense_caption, posting_amount, gl_account, description")
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear);

  // Build pivot: rows = categories, cols = captions
  const pivot: Record<DISECategory, Record<DISECaption, number>> = {} as Record<DISECategory, Record<DISECaption, number>>;
  DISE_CATEGORIES.forEach((c) => {
    pivot[c] = {} as Record<DISECaption, number>;
    DISE_CAPTIONS.forEach((cap) => { pivot[c][cap] = 0; });
  });

  let grandTotal = 0;
  for (const row of approved ?? []) {
    const cat = row.dise_category as DISECategory;
    const cap = row.expense_caption as DISECaption;
    const amt = Number(row.posting_amount ?? 0);
    if (!pivot[cat] || pivot[cat][cap] === undefined) continue;
    pivot[cat][cap] += amt;
    grandTotal += amt;
  }

  const colTotals: Record<DISECaption, number> = {} as Record<DISECaption, number>;
  DISE_CAPTIONS.forEach((cap) => {
    colTotals[cap] = DISE_CATEGORIES.reduce((s, c) => s + pivot[c][cap], 0);
  });

  const approvedCount = approved?.length ?? 0;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">DISE · ASU 2024-03</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Footnote draft</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Live tabular disclosure built from {approvedCount} approved mapping
            {approvedCount === 1 ? "" : "s"}. Updates as soon as a controller
            approves new rows. Export below feeds straight into Workiva.
          </p>
        </div>
        <div className="flex gap-2">
          <a
            href={`/api/exports/dise?company_id=${session.companyId}&fiscal_year=${session.fiscalYear}&format=csv`}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800"
          >
            Export CSV
          </a>
          <a
            href={`/api/exports/dise?company_id=${session.companyId}&fiscal_year=${session.fiscalYear}&format=json`}
            className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800"
          >
            Export JSON
          </a>
          <a
            href={`/api/exports/dise?company_id=${session.companyId}&fiscal_year=${session.fiscalYear}&format=docx`}
            className="rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-neutral-800 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
          >
            Export DOCX
          </a>
        </div>
      </div>

      <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table className="w-full text-sm tabular-nums">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-widest text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Natural expense category</th>
              <th className="px-3 py-2 text-left font-medium">ASC citation</th>
              {DISE_CAPTIONS.map((cap) => (
                <th key={cap} className="px-3 py-2 text-right font-medium">{cap}</th>
              ))}
              <th className="px-3 py-2 text-right font-medium">Total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {DISE_CATEGORIES.map((cat) => {
              const rowTotal = DISE_CAPTIONS.reduce((s, cap) => s + pivot[cat][cap], 0);
              return (
                <tr key={cat}>
                  <td className="px-3 py-2 font-medium">{cat}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-neutral-500">{DISE_CITATIONS[cat]}</td>
                  {DISE_CAPTIONS.map((cap) => (
                    <td key={cap} className="px-3 py-2 text-right">
                      {pivot[cat][cap] ? fmtThousands(pivot[cat][cap]) : "—"}
                    </td>
                  ))}
                  <td className="px-3 py-2 text-right font-medium">{rowTotal ? fmtThousands(rowTotal) : "—"}</td>
                </tr>
              );
            })}
            <tr className="border-t-2 border-neutral-300 bg-neutral-50 font-semibold dark:border-neutral-700 dark:bg-neutral-950">
              <td className="px-3 py-2">Total</td>
              <td className="px-3 py-2"></td>
              {DISE_CAPTIONS.map((cap) => (
                <td key={cap} className="px-3 py-2 text-right">{colTotals[cap] ? fmtThousands(colTotals[cap]) : "—"}</td>
              ))}
              <td className="px-3 py-2 text-right">{grandTotal ? fmtThousands(grandTotal) : "—"}</td>
            </tr>
          </tbody>
        </table>
        <div className="border-t border-neutral-200 px-3 py-2 text-[11px] text-neutral-500 dark:border-neutral-800">
          Amounts in thousands. FY{session.fiscalYear}.
        </div>
      </div>

      <section className="mt-8 space-y-4 rounded-lg border border-neutral-200 bg-white p-6 dark:border-neutral-800 dark:bg-neutral-900">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-neutral-500">
          Required narrative sections (ASU 2024-03)
        </h2>
        <Section title="Methodology">
          The Company classified its income statement expenses into the natural
          expense categories prescribed by ASC 220-40 using a controller-reviewed
          AI classification of source GL accounts. Each classification is
          supported by the underlying GL detail and was approved by the
          Controller prior to inclusion in this disclosure. Reasonable estimates
          and methods that approximate the prescribed categories were used where
          source detail was not directly available, as permitted by ASC 220-40.
        </Section>
        <Section title="Selling expenses definition">
          For purposes of this disclosure, selling expenses include direct sales
          force compensation and benefits, advertising and marketing programs,
          third-party sales commissions, sales support technology, and travel
          incurred in pursuit of new and existing customer relationships. The
          Company applied this definition consistently across the periods
          presented.
        </Section>
        <Section title="Inventory expensed when sold">
          Amounts of inventory expensed when sold are included in the
          &quot;Purchases of inventory&quot; row when those amounts are recognized in
          cost of revenues. Capitalized inventory is excluded from this
          disclosure until expensed.
        </Section>
        <Section title="Election change">
          No election changes were made during the period presented. If an
          election is changed in a future period, the reason for the change
          will be disclosed and prior periods recast for comparative purposes,
          unless impracticable.
        </Section>
      </section>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-widest text-neutral-500">{title}</div>
      <p className="mt-1 text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">{children}</p>
    </div>
  );
}

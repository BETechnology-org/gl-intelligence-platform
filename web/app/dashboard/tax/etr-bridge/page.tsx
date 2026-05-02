import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import type { TaxCategory } from "@/lib/api";

export const dynamic = "force-dynamic";

const STATUTORY_RATE = 0.21;
const MATERIALITY_PCT = 0.05;

const fmtMillions = (n: number) =>
  `$${(n / 1_000_000).toFixed(1)}M`;
const fmtPct = (n: number) =>
  `${(n * 100).toFixed(2)}%`;

interface Approved {
  tax_category: TaxCategory;
  posting_amount: number | string;
  gl_account: string;
  description: string;
  jurisdiction_hint: string | null;
}

export default async function ETRBridgePage() {
  const session = await requireSession("/dashboard/tax/etr-bridge");
  const admin = getSupabaseAdmin();

  const { data } = await admin
    .from("tax_approved_mappings")
    .select("tax_category,posting_amount,gl_account,description,jurisdiction_hint")
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear);

  const approved = (data ?? []) as unknown as Approved[];

  const totals: Record<TaxCategory, number> = {
    current_federal: 0, current_state: 0, current_foreign: 0,
    deferred_federal: 0, deferred_state: 0, deferred_foreign: 0,
    deferred_tax_asset: 0, deferred_tax_liab: 0,
    pretax_domestic: 0, pretax_foreign: 0,
    not_tax_account: 0,
  };
  for (const r of approved) totals[r.tax_category] += Number(r.posting_amount ?? 0);

  const currentTotal = totals.current_federal + totals.current_state + totals.current_foreign;
  const deferredTotal = totals.deferred_federal + totals.deferred_state + totals.deferred_foreign;
  const totalProvision = currentTotal + deferredTotal;
  const pretax = totals.pretax_domestic + totals.pretax_foreign;
  const statutoryAtRate = pretax * STATUTORY_RATE;
  const effectiveRate = pretax > 0 ? totalProvision / pretax : 0;
  const materialityThreshold = Math.abs(statutoryAtRate * MATERIALITY_PCT);

  // Table A — ETR reconciliation waterfall (simplified — full ASU 2023-09 8-cat will land
  // when ETR bridge agent ships in Phase 2).
  const stateLocalAmt = totals.current_state + totals.deferred_state;
  const foreignTotal = totals.current_foreign + totals.deferred_foreign;
  const foreignRateDiff = foreignTotal - (totals.pretax_foreign * STATUTORY_RATE);
  const deferredFederal = totals.deferred_federal;
  const otherAdj = totalProvision - statutoryAtRate - stateLocalAmt - foreignRateDiff - deferredFederal;

  const tableA = [
    { item: `Income tax at US federal statutory rate (${(STATUTORY_RATE * 100).toFixed(0)}%)`, amount: statutoryAtRate, asu_cat: "1_statutory", citation: "ASC 740-10-50-12(a)" },
    { item: "State and local income taxes, net of federal benefit",       amount: stateLocalAmt,    asu_cat: "2_state_local", citation: "ASC 740-10-50-12(b)" },
    { item: "Foreign rate differential",                                   amount: foreignRateDiff,  asu_cat: "3_foreign",     citation: "ASC 740-10-50-12(c)" },
    { item: "Deferred tax expense — federal",                              amount: deferredFederal,  asu_cat: "4_deferred",    citation: "ASC 740-10-50-9" },
    { item: "Other, net",                                                  amount: otherAdj,         asu_cat: "9_other",       citation: "ASC 740-10-50-12" },
  ].filter((r) => Math.abs(r.amount) > 1);

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Income Tax · ASU 2023-09</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">ETR bridge</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Tables A (rate reconciliation), B (cash taxes paid), C (pre-tax split) computed live
            from {approved.length} approved tax mappings. Items ≥5% of statutory base are flagged
            for separate disclosure per ASU 2023-09.
          </p>
        </div>
        <a
          href={`/api/exports/tax?company_id=${session.companyId}&fiscal_year=${session.fiscalYear}&format=csv`}
          className="rounded-md border border-neutral-300 bg-white px-3 py-1.5 text-sm font-medium hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:hover:bg-neutral-800"
        >
          Export CSV
        </a>
      </div>

      <div className="mb-6 grid grid-cols-4 gap-4">
        <KPI label="Pretax income (total)"  value={fmtMillions(pretax)} subtitle={`${fmtMillions(totals.pretax_domestic)} dom + ${fmtMillions(totals.pretax_foreign)} for`} />
        <KPI label="Total tax provision"    value={fmtMillions(totalProvision)} subtitle={`${fmtMillions(currentTotal)} cur + ${fmtMillions(deferredTotal)} def`} />
        <KPI label="Effective tax rate"     value={fmtPct(effectiveRate)} subtitle={`vs ${(STATUTORY_RATE * 100).toFixed(0)}% statutory · ${Math.round((effectiveRate - STATUTORY_RATE) * 10000)} bps`} />
        <KPI label="5% materiality threshold" value={fmtMillions(materialityThreshold)} subtitle="Items above are separately disclosed" />
      </div>

      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-widest text-neutral-500">
        Table A — Rate reconciliation (simplified)
      </h2>
      <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table className="w-full text-sm tabular-nums">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-widest text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Reconciling item</th>
              <th className="px-3 py-2 text-left font-medium">ASU cat</th>
              <th className="px-3 py-2 text-left font-medium">Citation</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2 text-right font-medium">% of pretax</th>
              <th className="px-3 py-2 text-center font-medium">≥5%</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {tableA.map((r) => {
              const isMaterial = Math.abs(r.amount) >= materialityThreshold && r.asu_cat !== "1_statutory";
              return (
                <tr key={r.asu_cat}>
                  <td className="px-3 py-2">{r.item}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-neutral-500">{r.asu_cat}</td>
                  <td className="px-3 py-2 font-mono text-[11px] text-neutral-500">{r.citation}</td>
                  <td className="px-3 py-2 text-right">{fmtMillions(r.amount)}</td>
                  <td className="px-3 py-2 text-right">{pretax > 0 ? fmtPct(r.amount / pretax) : "—"}</td>
                  <td className="px-3 py-2 text-center">
                    {isMaterial ? <span className="rounded bg-rose-100 px-1.5 py-0.5 text-[10px] font-medium text-rose-800 dark:bg-rose-900/30 dark:text-rose-200">DISCLOSE</span> : ""}
                  </td>
                </tr>
              );
            })}
            <tr className="border-t-2 border-neutral-300 bg-neutral-50 font-semibold dark:border-neutral-700 dark:bg-neutral-950">
              <td className="px-3 py-2">Total income tax expense</td>
              <td colSpan={2}></td>
              <td className="px-3 py-2 text-right">{fmtMillions(totalProvision)}</td>
              <td className="px-3 py-2 text-right">{fmtPct(effectiveRate)}</td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>

      <h2 className="mb-2 mt-8 text-sm font-semibold uppercase tracking-widest text-neutral-500">
        Table C — Pre-tax income split
      </h2>
      <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table className="w-full text-sm tabular-nums">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-widest text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Segment</th>
              <th className="px-3 py-2 text-right font-medium">Amount</th>
              <th className="px-3 py-2 text-right font-medium">% of total</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
            <tr><td className="px-3 py-2">Domestic operations</td><td className="px-3 py-2 text-right">{fmtMillions(totals.pretax_domestic)}</td><td className="px-3 py-2 text-right">{pretax > 0 ? fmtPct(totals.pretax_domestic / pretax) : "—"}</td></tr>
            <tr><td className="px-3 py-2">Foreign operations</td><td className="px-3 py-2 text-right">{fmtMillions(totals.pretax_foreign)}</td><td className="px-3 py-2 text-right">{pretax > 0 ? fmtPct(totals.pretax_foreign / pretax) : "—"}</td></tr>
            <tr className="border-t-2 border-neutral-300 bg-neutral-50 font-semibold dark:border-neutral-700 dark:bg-neutral-950">
              <td className="px-3 py-2">Income before provision for income taxes</td>
              <td className="px-3 py-2 text-right">{fmtMillions(pretax)}</td>
              <td className="px-3 py-2 text-right">100.0%</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KPI({ label, value, subtitle }: { label: string; value: string; subtitle?: string }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white p-4 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="text-[11px] font-semibold uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="mt-1 font-mono text-xl tabular-nums">{value}</div>
      {subtitle && <div className="mt-1 text-[11px] text-neutral-500">{subtitle}</div>}
    </div>
  );
}

import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

export const dynamic = "force-dynamic";

const PRIORITY_BADGE: Record<string, string> = {
  P1: "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200",
  P2: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  P3: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
};

const STATUS_BADGE: Record<string, string> = {
  open:         "bg-rose-50 text-rose-700 ring-1 ring-rose-200 dark:bg-rose-900/30 dark:text-rose-200 dark:ring-rose-900",
  acknowledged: "bg-amber-50 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-900",
  resolved:     "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-200 dark:ring-emerald-900",
  dismissed:    "bg-neutral-50 text-neutral-700 ring-1 ring-neutral-200 dark:bg-neutral-900/30 dark:text-neutral-300 dark:ring-neutral-800",
};

const fmt = (n: number) => new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(n);
const fmtPct = (n: number) => `${n > 0 ? "+" : ""}${n.toFixed(1)}%`;

export default async function DISEAnomaliesPage() {
  const session = await requireSession("/dashboard/dise/anomalies");
  const admin = getSupabaseAdmin();

  const { data: alerts } = await admin
    .from("dise_anomaly_alerts")
    .select("*")
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear)
    .order("priority")
    .order("detected_at", { ascending: false })
    .limit(200);

  const rows = alerts ?? [];
  const counts = {
    P1: rows.filter((r) => r.priority === "P1" && r.status === "open").length,
    P2: rows.filter((r) => r.priority === "P2" && r.status === "open").length,
    P3: rows.filter((r) => r.priority === "P3" && r.status === "open").length,
  };

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6">
        <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">DISE</div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Anomalies</h1>
        <p className="mt-1 max-w-2xl text-sm text-neutral-500">
          YoY variances at the GL-account level (P1 &gt; 100%, P2 &gt; 50%, P3 &gt; 25%, min $100K).
          Triage and resolve before close sign-off.
        </p>
      </div>

      <div className="mb-6 grid grid-cols-3 gap-4">
        <KPI label="Open P1 (critical)" value={counts.P1} className="border-rose-200" />
        <KPI label="Open P2 (warning)" value={counts.P2} className="border-amber-200" />
        <KPI label="Open P3 (monitor)" value={counts.P3} />
      </div>

      <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table className="w-full text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-widest text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Pri.</th>
              <th className="px-3 py-2 text-left font-medium">GL</th>
              <th className="px-3 py-2 text-left font-medium">Description</th>
              <th className="px-3 py-2 text-left font-medium">Category</th>
              <th className="px-3 py-2 text-right font-medium">FY current</th>
              <th className="px-3 py-2 text-right font-medium">FY prior</th>
              <th className="px-3 py-2 text-right font-medium">YoY</th>
              <th className="px-3 py-2 text-left font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {rows.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-12 text-center text-sm text-neutral-500">
                  No anomalies detected. Runs the anomaly agent (DISE module → Phase 3) to scan.
                </td>
              </tr>
            )}
            {rows.map((a) => (
              <tr key={a.id as string}>
                <td className="px-3 py-2">
                  <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${PRIORITY_BADGE[a.priority as string]}`}>
                    {a.priority as string}
                  </span>
                </td>
                <td className="px-3 py-2 font-mono text-[12px]">{a.gl_account as string}</td>
                <td className="px-3 py-2">{a.description as string}</td>
                <td className="px-3 py-2 text-[12px] text-neutral-500">{a.dise_category as string}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(Number(a.fy_current ?? 0))}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{fmt(Number(a.fy_prior ?? 0))}</td>
                <td className="px-3 py-2 text-right font-mono tabular-nums">{fmtPct(Number(a.pct_change ?? 0))}</td>
                <td className="px-3 py-2">
                  <span className={`inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium ${STATUS_BADGE[a.status as string]}`}>
                    {a.status as string}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KPI({ label, value, className = "" }: { label: string; value: number; className?: string }) {
  return (
    <div className={`rounded-lg border bg-white p-4 dark:bg-neutral-900 dark:border-neutral-800 ${className}`}>
      <div className="text-[11px] font-semibold uppercase tracking-widest text-neutral-500">{label}</div>
      <div className="mt-1 font-mono text-2xl tabular-nums">{value}</div>
    </div>
  );
}

import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

export const dynamic = "force-dynamic";

const MODULE_BADGE: Record<string, string> = {
  tax:      "bg-violet-100 text-violet-800 dark:bg-violet-900/30 dark:text-violet-200",
  dise:     "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
  platform: "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
};

const ACTOR_BADGE: Record<string, string> = {
  AGENT:  "text-violet-700 dark:text-violet-300",
  HUMAN:  "text-emerald-700 dark:text-emerald-300",
  SYSTEM: "text-neutral-500",
};

export default async function AuditLogPage() {
  const session = await requireSession("/dashboard/audit-log");
  const admin = getSupabaseAdmin();

  const { data: events } = await admin
    .from("audit_log")
    .select("*")
    .eq("company_id", session.companyId)
    .order("event_timestamp", { ascending: false })
    .limit(200);

  const rows = events ?? [];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6">
        <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
          Platform · Append-only
        </div>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="mt-1 max-w-2xl text-sm text-neutral-500">
          Immutable record of every agent action and human review decision.
          DB triggers block UPDATE / DELETE — this is the audit-defensible
          evidence package for your external auditor.
        </p>
      </div>

      <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
        <table className="w-full text-sm">
          <thead className="border-b border-neutral-200 bg-neutral-50 text-[11px] uppercase tracking-widest text-neutral-500 dark:border-neutral-800 dark:bg-neutral-950">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Timestamp</th>
              <th className="px-3 py-2 text-left font-medium">Module</th>
              <th className="px-3 py-2 text-left font-medium">Event</th>
              <th className="px-3 py-2 text-left font-medium">GL</th>
              <th className="px-3 py-2 text-left font-medium">Actor</th>
              <th className="px-3 py-2 text-left font-medium">Tool / detail</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neutral-200 dark:divide-neutral-800">
            {rows.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-8 text-center text-neutral-500">
                  No audit events yet. Run the classifier or approve a row to see entries here.
                </td>
              </tr>
            )}
            {rows.map((e) => {
              const ts = new Date(e.event_timestamp as string);
              const detail = e.tool_name
                ? `${e.tool_name}`
                : (e.payload as Record<string, unknown> | null)?.reason
                  ? String((e.payload as Record<string, unknown>).reason).slice(0, 80)
                  : "";
              return (
                <tr key={e.event_id as string} className="hover:bg-neutral-50/60 dark:hover:bg-neutral-800/40">
                  <td className="whitespace-nowrap px-3 py-2 font-mono text-[11px] text-neutral-500">
                    {ts.toLocaleString()}
                  </td>
                  <td className="px-3 py-2">
                    <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${MODULE_BADGE[e.module as string] ?? MODULE_BADGE.platform}`}>
                      {e.module as string}
                    </span>
                  </td>
                  <td className="px-3 py-2 font-mono text-[12px]">{e.event_type as string}</td>
                  <td className="px-3 py-2 font-mono text-[12px] text-neutral-700 dark:text-neutral-300">
                    {(e.gl_account as string) ?? "—"}
                  </td>
                  <td className={`px-3 py-2 text-[12px] ${ACTOR_BADGE[e.actor_type as string] ?? "text-neutral-500"}`}>
                    <span className="font-mono">{(e.actor as string).slice(0, 12)}</span>
                    <span className="ml-1 text-[10px] opacity-60">{e.actor_type as string}</span>
                  </td>
                  <td className="px-3 py-2 text-[12px] text-neutral-600 dark:text-neutral-400">
                    {detail}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 text-[11px] text-neutral-500">
        Showing the most recent 200 events. Older events are nightly-exported to BigQuery
        (<code className="font-mono">audit_log_mirror</code>) for SOX retention.
      </p>
    </div>
  );
}

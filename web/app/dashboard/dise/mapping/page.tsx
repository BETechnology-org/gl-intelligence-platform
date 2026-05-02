import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { AgentRunButton } from "@/components/dashboard/AgentRunButton";
import { DISEReviewQueueRow, type DISEPendingRow } from "@/components/dashboard/DISEReviewQueueRow";

export const dynamic = "force-dynamic";

export default async function DISEMappingPage() {
  const session = await requireSession("/dashboard/dise/mapping");
  const admin = getSupabaseAdmin();

  const { data: pending } = await admin
    .from("dise_pending_mappings")
    .select("*")
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear)
    .eq("status", "PENDING")
    .order("posting_amount", { ascending: false })
    .limit(100);

  const rows = (pending ?? []) as unknown as DISEPendingRow[];

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
            DISE · ASU 2024-03
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Mapping review</h1>
          <p className="mt-1 max-w-2xl text-sm text-neutral-500">
            Pending agent classifications of GL expense accounts into the five
            ASC 220-40 natural categories. Approve, override, or reject. Approved
            rows feed the DISE footnote and the YoY anomaly detector.
          </p>
        </div>
        <div className="text-right text-xs text-neutral-500">
          <div className="font-mono text-sm text-neutral-700 dark:text-neutral-200">
            {rows.length} pending
          </div>
        </div>
      </div>

      <div className="mb-6">
        <AgentRunButton
          endpoint="/api/agents/dise/classify"
          body={{ company_id: session.companyId, fiscal_year: session.fiscalYear, batch_size: 20 }}
          label="Run mapping agent on next batch"
          successFormat={({ classified, errors }) =>
            `Drafted ${classified} mapping${classified === 1 ? "" : "s"}` + (errors > 0 ? ` · ${errors} errors` : "")
          }
        />
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 px-6 py-12 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No pending DISE mappings. Run the agent above to draft a new batch.
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <DISEReviewQueueRow key={row.id} row={row} />
          ))}
        </div>
      )}
    </div>
  );
}

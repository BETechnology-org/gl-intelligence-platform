import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { ReviewQueueRow } from "@/components/dashboard/ReviewQueueRow";
import { AgentRunButton } from "@/components/dashboard/AgentRunButton";
import {
  ASC_CITATIONS_HINT,
  TAX_CATEGORIES,
  TAX_CATEGORY_LABELS,
} from "@/lib/tax-categories";
import type { TaxPendingMapping } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function TaxClassifierPage() {
  const session = await requireSession("/dashboard/tax/classifier");
  const admin = getSupabaseAdmin();

  const { data: pending } = await admin
    .from("tax_pending_mappings")
    .select("*")
    .eq("company_id", session.companyId)
    .eq("fiscal_year", session.fiscalYear)
    .eq("status", "PENDING")
    .order("posting_amount", { ascending: false })
    .limit(50);

  const rows = (pending ?? []) as unknown as TaxPendingMapping[];

  const categories = TAX_CATEGORIES.map((key) => ({
    key,
    label: TAX_CATEGORY_LABELS[key],
    citation: ASC_CITATIONS_HINT[key] ?? "",
  }));

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
            Income Tax · ASU 2023-09
          </div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Tax classifier review</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Pending agent classifications for SAP GL accounts in the tax range
            (160000–199999). Approve, override, or reject. Approved rows feed the ETR
            bridge automatically.
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
          endpoint="/api/agents/tax/classify"
          body={{ company_id: session.companyId, fiscal_year: session.fiscalYear, batch_size: 18 }}
          label="Run classifier on next batch"
        />
      </div>

      {rows.length === 0 ? (
        <div className="rounded-lg border border-dashed border-neutral-300 px-6 py-12 text-center text-sm text-neutral-500 dark:border-neutral-700">
          No pending tax mappings. Run the classifier above to draft a new batch.
        </div>
      ) : (
        <div className="space-y-2">
          {rows.map((row) => (
            <ReviewQueueRow key={row.id} row={row} categories={categories} />
          ))}
        </div>
      )}
    </div>
  );
}

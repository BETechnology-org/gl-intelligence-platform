import { requireSession } from "@/lib/auth-helpers";
import { getSupabaseAdmin } from "@/lib/supabase-admin";

export const dynamic = "force-dynamic";

const STATUS_BADGE: Record<string, string> = {
  pending:     "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  in_progress: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  complete:    "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/30 dark:text-emerald-200",
  blocked:     "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200",
};

const DEFAULT_TASKS = [
  { task_id: "T001", task_name: "GL account ingest from SAP/Oracle/finance-datasets", detail: "501 accounts loaded · sources verified" },
  { task_id: "T002", task_name: "DISE mapping coverage ≥ 95%", detail: "All material expense captions classified by agent + reviewed by controller" },
  { task_id: "T003", task_name: "DISE pivot footing", detail: "Caption × category sums tie to income statement face within $1K tolerance" },
  { task_id: "T004", task_name: "ASU 2023-09 8-category rate reconciliation", detail: "All 8 categories present with both % and $; items ≥5% disclosed separately" },
  { task_id: "T005", task_name: "Cash taxes paid disaggregation (federal/state/foreign)", detail: "Foreign jurisdictions ≥5% of total separately disclosed" },
  { task_id: "T006", task_name: "Anomaly review (P1)", detail: "All P1 alerts (>100% YoY) acknowledged with resolution notes" },
  { task_id: "T007", task_name: "Controller sign-off — DISE", detail: "Controller approves footnote draft" },
  { task_id: "T008", task_name: "Tax Director sign-off — ASU 2023-09", detail: "Tax Director approves rate-rec, jurisdictional disagg" },
  { task_id: "T009", task_name: "External audit evidence package export", detail: "Audit log + approved mappings + source GL drilled down — exported for Big-4 review" },
  { task_id: "T010", task_name: "10-K filing drop-in", detail: "DISE pivot + footnote ready for Workiva 10-K assembly" },
];

export default async function CloseTrackerPage() {
  const session = await requireSession("/dashboard/close-tracker");
  const admin = getSupabaseAdmin();

  const { data: tasks } = await admin
    .from("close_tracker_tasks")
    .select("*")
    .eq("company_id", session.companyId)
    .order("sort_order");

  const rows = tasks && tasks.length > 0
    ? tasks
    : DEFAULT_TASKS.map((t, i) => ({
        ...t,
        id: `default-${i}`,
        company_id: session.companyId,
        fiscal_period: `${session.fiscalYear}-12`,
        status: "pending",
        sort_order: i,
      }));

  const completed = rows.filter((r) => (r as { status: string }).status === "complete").length;

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6 flex items-end justify-between">
        <div>
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Platform</div>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight">Close tracker</h1>
          <p className="mt-1 text-sm text-neutral-500">
            Sign-off chain for FY{session.fiscalYear}.
          </p>
        </div>
        <div className="text-right">
          <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">Progress</div>
          <div className="mt-1 font-mono text-2xl tabular-nums">{completed}/{rows.length}</div>
        </div>
      </div>

      <div className="space-y-2">
        {rows.map((t) => {
          const status = (t as { status: string }).status;
          return (
            <div
              key={(t as { id: string }).id}
              className="flex items-center gap-4 rounded-lg border border-neutral-200 bg-white px-4 py-3 dark:border-neutral-800 dark:bg-neutral-900"
            >
              <span className="w-12 shrink-0 font-mono text-[11px] text-neutral-500">{(t as { task_id: string }).task_id}</span>
              <div className="grow">
                <div className="text-sm font-medium">{(t as { task_name: string }).task_name}</div>
                {(t as { detail: string }).detail && (
                  <div className="mt-0.5 text-[12px] text-neutral-500">{(t as { detail: string }).detail}</div>
                )}
              </div>
              <span className={`rounded px-2 py-0.5 text-[11px] font-medium ${STATUS_BADGE[status] ?? STATUS_BADGE.pending}`}>
                {status}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, X, ChevronDown, ChevronRight } from "lucide-react";

import { ConfidenceBadge } from "./ConfidenceBadge";
import { approveTax, rejectTax, type TaxPendingMapping } from "@/lib/api";
import { createClient } from "@/utils/supabase/client";

interface Props {
  row: TaxPendingMapping;
  categories: Array<{ key: string; label: string; citation: string }>;
}

const formatUSD = (amount: number) =>
  new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(amount);

export function ReviewQueueRow({ row, categories }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [overrideCategory, setOverrideCategory] = useState<string>("");
  const [overrideReason, setOverrideReason] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const router = useRouter();

  const getToken = async (): Promise<string | null> => {
    const supabase = createClient();
    const { data } = await supabase.auth.getSession();
    return data.session?.access_token ?? null;
  };

  const onApprove = async () => {
    setBusy("approve");
    setErr(null);
    try {
      const token = await getToken();
      const body: { pending_id: string; override_category?: string; override_reason?: string } = {
        pending_id: row.id,
      };
      if (overrideCategory && overrideCategory !== row.tax_category) {
        body.override_category = overrideCategory;
        body.override_reason = overrideReason || "Reviewer override";
      }
      await approveTax(body, token);
      startTransition(() => router.refresh());
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const onReject = async () => {
    if (!rejectReason.trim()) {
      setErr("Rejection reason required");
      return;
    }
    setBusy("reject");
    setErr(null);
    try {
      const token = await getToken();
      await rejectTax({ pending_id: row.id, reason: rejectReason }, token);
      startTransition(() => router.refresh());
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors hover:bg-neutral-50 dark:hover:bg-neutral-800/50"
      >
        {expanded ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
        <span className="w-32 shrink-0 font-mono text-[12px] text-neutral-700 dark:text-neutral-300">
          {row.gl_account}
        </span>
        <span className="grow truncate text-sm">{row.description ?? "—"}</span>
        <span className="w-32 shrink-0 text-right font-mono text-sm tabular-nums">
          {formatUSD(row.posting_amount)}
        </span>
        <span className="w-44 shrink-0 text-xs text-neutral-700 dark:text-neutral-300">
          {row.tax_category_label}
        </span>
        <ConfidenceBadge label={row.confidence_label} score={row.confidence_score} />
      </button>

      {expanded && (
        <div className="border-t border-neutral-200 bg-neutral-50/40 px-6 py-4 text-sm dark:border-neutral-800 dark:bg-neutral-950/40">
          {row.draft_reasoning && (
            <div className="mb-4">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
                Agent reasoning
              </div>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
                {row.draft_reasoning}
              </p>
            </div>
          )}

          {Array.isArray(row.similar_accounts) && row.similar_accounts.length > 0 && (
            <div className="mb-4">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
                Similar approved
              </div>
              <ul className="space-y-1 text-[12px]">
                {row.similar_accounts.slice(0, 5).map((s: Record<string, unknown>, i: number) => (
                  <li key={i} className="font-mono">
                    {String(s.gl_account ?? "?")} — {String(s.description ?? "")} →{" "}
                    {String(s.tax_category ?? "")}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mb-4">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
              Citation
            </div>
            <div className="font-mono text-[12px]">{row.asc_citation ?? "—"}</div>
          </div>

          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <div className="rounded-md border border-neutral-200 p-3 dark:border-neutral-800">
              <label className="block text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
                Override category (optional)
              </label>
              <select
                value={overrideCategory}
                onChange={(e) => setOverrideCategory(e.target.value)}
                className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
              >
                <option value="">— keep agent suggestion —</option>
                {categories.map((c) => (
                  <option key={c.key} value={c.key}>
                    {c.label}
                  </option>
                ))}
              </select>
              {overrideCategory && (
                <input
                  value={overrideReason}
                  onChange={(e) => setOverrideReason(e.target.value)}
                  placeholder="Override reason (required)"
                  className="mt-2 w-full rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
                />
              )}
              <button
                type="button"
                disabled={busy !== null}
                onClick={onApprove}
                className="mt-3 inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
              >
                <Check size={14} />
                {busy === "approve" ? "Approving…" : overrideCategory ? "Override & approve" : "Approve"}
              </button>
            </div>

            <div className="rounded-md border border-neutral-200 p-3 dark:border-neutral-800">
              <label className="block text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
                Reject (reason required)
              </label>
              <input
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Why is this not classifiable?"
                className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
              />
              <button
                type="button"
                disabled={busy !== null}
                onClick={onReject}
                className="mt-3 inline-flex items-center gap-2 rounded-md bg-rose-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-rose-700 disabled:opacity-50"
              >
                <X size={14} />
                {busy === "reject" ? "Rejecting…" : "Reject"}
              </button>
            </div>
          </div>

          {err && (
            <div className="mt-3 rounded border border-rose-200 bg-rose-50 px-3 py-2 text-[12px] text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300">
              {err}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, X, ChevronDown, ChevronRight } from "lucide-react";

import { ConfidenceBadge } from "./ConfidenceBadge";
import { DISE_CATEGORIES, DISE_CAPTIONS, type DISECategory, type DISECaption } from "@/lib/dise-categories";
import type { ConfidenceLabel, MappingStatus } from "@/lib/api";

export interface DISEPendingRow {
  id: string;
  gl_account: string;
  description: string | null;
  posting_amount: number;
  fiscal_year: string;
  suggested_category: DISECategory;
  suggested_caption: DISECaption;
  suggested_citation: string | null;
  draft_reasoning: string | null;
  confidence_score: number;
  confidence_label: ConfidenceLabel;
  similar_accounts: Array<Record<string, unknown>>;
  materiality_flag: "HIGH" | "MEDIUM" | "LOW" | null;
  status: MappingStatus;
}

const formatUSD = (a: number) =>
  new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(a);

const MATERIALITY_BADGE: Record<"HIGH" | "MEDIUM" | "LOW", string> = {
  HIGH:   "bg-rose-100 text-rose-800 dark:bg-rose-900/30 dark:text-rose-200",
  MEDIUM: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-200",
  LOW:    "bg-neutral-100 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-400",
};

export function DISEReviewQueueRow({ row }: { row: DISEPendingRow }) {
  const [expanded, setExpanded] = useState(false);
  const [overrideCategory, setOverrideCategory] = useState<string>("");
  const [overrideCaption, setOverrideCaption] = useState<string>("");
  const [overrideReason, setOverrideReason] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [busy, setBusy] = useState<"approve" | "reject" | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const router = useRouter();

  const post = async (path: string, payload: object) => {
    const res = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error((await res.text()) || res.statusText);
    return res.json();
  };

  const onApprove = async () => {
    setBusy("approve");
    setErr(null);
    try {
      const payload: Record<string, unknown> = { pending_id: row.id };
      if (overrideCategory && overrideCategory !== row.suggested_category) {
        payload.override_category = overrideCategory;
      }
      if (overrideCaption && overrideCaption !== row.suggested_caption) {
        payload.override_caption = overrideCaption;
      }
      if (payload.override_category || payload.override_caption) {
        payload.override_reason = overrideReason || "Reviewer override";
      }
      await post("/api/dise/approve", payload);
      startTransition(() => router.refresh());
    } catch (e) {
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
      await post("/api/dise/reject", { pending_id: row.id, reason: rejectReason });
      startTransition(() => router.refresh());
    } catch (e) {
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
        <span className="w-32 shrink-0 text-right font-mono text-sm tabular-nums">{formatUSD(row.posting_amount)}</span>
        <span className="w-44 shrink-0 truncate text-xs text-neutral-700 dark:text-neutral-300">
          {row.suggested_category}
        </span>
        <span className="w-16 shrink-0 text-[11px] text-neutral-500">{row.suggested_caption}</span>
        {row.materiality_flag && (
          <span className={`rounded px-1.5 py-0.5 text-[10px] font-medium ${MATERIALITY_BADGE[row.materiality_flag]}`}>
            {row.materiality_flag}
          </span>
        )}
        <ConfidenceBadge label={row.confidence_label} score={row.confidence_score} />
      </button>

      {expanded && (
        <div className="border-t border-neutral-200 bg-neutral-50/40 px-6 py-4 text-sm dark:border-neutral-800 dark:bg-neutral-950/40">
          {row.draft_reasoning && (
            <div className="mb-4">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">Agent reasoning</div>
              <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-neutral-700 dark:text-neutral-300">
                {row.draft_reasoning}
              </p>
            </div>
          )}

          {Array.isArray(row.similar_accounts) && row.similar_accounts.length > 0 && (
            <div className="mb-4">
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">Similar approved</div>
              <ul className="space-y-1 text-[12px]">
                {row.similar_accounts.slice(0, 5).map((s: Record<string, unknown>, i: number) => (
                  <li key={i} className="font-mono">
                    {String(s.gl_account ?? "?")} — {String(s.description ?? "")} → {String(s.dise_category ?? "")}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="mb-4">
            <div className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-neutral-500">Citation</div>
            <div className="font-mono text-[12px]">{row.suggested_citation ?? "—"}</div>
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
                {DISE_CATEGORIES.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>

              <label className="mt-3 block text-[11px] font-semibold uppercase tracking-widest text-neutral-500">
                Override caption (optional)
              </label>
              <select
                value={overrideCaption}
                onChange={(e) => setOverrideCaption(e.target.value)}
                className="mt-1 w-full rounded border border-neutral-300 bg-white px-2 py-1 text-sm dark:border-neutral-700 dark:bg-neutral-900"
              >
                <option value="">— keep agent suggestion —</option>
                {DISE_CAPTIONS.map((c) => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>

              {(overrideCategory || overrideCaption) && (
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
                {busy === "approve" ? "Approving…" : (overrideCategory || overrideCaption) ? "Override & approve" : "Approve"}
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

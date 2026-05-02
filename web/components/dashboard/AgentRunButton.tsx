"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Play } from "lucide-react";

interface Props {
  endpoint: string;          // e.g. /api/agents/tax/classify
  body: Record<string, unknown>;
  label: string;             // e.g. "Run classifier on next batch"
  successFormat?: (data: { classified: number; errors: number }) => string;
}

export function AgentRunButton({ endpoint, body, label, successFormat }: Props) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [, startTransition] = useTransition();
  const router = useRouter();

  const run = async () => {
    setBusy(true);
    setMsg(null);
    setErr(null);
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? res.statusText);
      const classified = Number(data.classified ?? 0);
      const errors = Number(data.errors ?? 0);
      setMsg(
        successFormat
          ? successFormat({ classified, errors })
          : `Drafted ${classified} pending mapping${classified === 1 ? "" : "s"}` + (errors > 0 ? ` · ${errors} errors` : ""),
      );
      startTransition(() => router.refresh());
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="rounded-lg border border-neutral-200 bg-white dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-center justify-between px-4 py-3">
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-violet-500" />
          <span className="text-sm font-medium">{label}</span>
        </div>
        <button
          type="button"
          onClick={run}
          disabled={busy}
          className="inline-flex items-center gap-2 rounded-md bg-neutral-900 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-50 dark:bg-white dark:text-neutral-900 dark:hover:bg-neutral-100"
        >
          <Play size={14} />
          {busy ? "Running…" : "Start"}
        </button>
      </div>
      {(msg || err) && (
        <div className="border-t border-neutral-200 px-4 py-2 text-[12px] dark:border-neutral-800">
          {msg && <span className="text-emerald-700 dark:text-emerald-300">{msg}</span>}
          {err && <span className="text-rose-700 dark:text-rose-300">error: {err}</span>}
        </div>
      )}
    </section>
  );
}

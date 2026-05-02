import type { ConfidenceLabel } from "@/lib/api";

const CLS: Record<ConfidenceLabel, string> = {
  HIGH:
    "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200 dark:bg-emerald-900/30 dark:text-emerald-300 dark:ring-emerald-900",
  MEDIUM:
    "bg-amber-50 text-amber-800 ring-1 ring-amber-200 dark:bg-amber-900/30 dark:text-amber-200 dark:ring-amber-900",
  LOW:
    "bg-rose-50 text-rose-700 ring-1 ring-rose-200 dark:bg-rose-900/30 dark:text-rose-300 dark:ring-rose-900",
};

export function ConfidenceBadge({ label, score }: { label: ConfidenceLabel; score: number }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-medium tabular-nums ${CLS[label]}`}
      title={`${label} confidence (${Math.round(score * 100)}%)`}
    >
      {label}
      <span className="opacity-70">{Math.round(score * 100)}%</span>
    </span>
  );
}

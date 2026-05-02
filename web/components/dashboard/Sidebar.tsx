import Link from "next/link";
import { BarChart3, FileCheck, Inbox, ScrollText, Workflow, type LucideIcon } from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
  group: "Income Tax" | "DISE" | "Platform";
  badgeKey?: string;
}

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Overview", icon: BarChart3, group: "Platform" },
  { href: "/dashboard/audit-log", label: "Audit log", icon: ScrollText, group: "Platform" },
  { href: "/dashboard/close-tracker", label: "Close tracker", icon: Workflow, group: "Platform" },

  { href: "/dashboard/tax/classifier", label: "Classifier review", icon: Inbox, group: "Income Tax", badgeKey: "tax_pending" },
  { href: "/dashboard/tax/etr-bridge", label: "ETR bridge (A/B/C)", icon: BarChart3, group: "Income Tax" },
  { href: "/dashboard/tax/disclosure", label: "Footnote draft", icon: FileCheck, group: "Income Tax" },

  { href: "/dashboard/dise/mapping", label: "Mapping review", icon: Inbox, group: "DISE", badgeKey: "dise_pending" },
  { href: "/dashboard/dise/anomalies", label: "Anomalies", icon: BarChart3, group: "DISE", badgeKey: "dise_anomalies_open" },
  { href: "/dashboard/dise/disclosure", label: "DISE footnote", icon: FileCheck, group: "DISE" },
];

export function Sidebar({ counts }: { counts?: Record<string, number> }) {
  const groups = ["Income Tax", "DISE", "Platform"] as const;
  return (
    <aside className="w-64 shrink-0 border-r border-neutral-200 bg-neutral-50/50 px-4 py-6 dark:border-neutral-800 dark:bg-neutral-900/40">
      <Link href="/" className="mb-8 flex items-center gap-2">
        <span className="text-lg font-semibold tracking-tight">BL Intelligence</span>
      </Link>

      <nav className="flex flex-col gap-6 text-sm">
        {groups.map((group) => (
          <div key={group}>
            <div className="mb-2 text-xs font-semibold uppercase tracking-widest text-neutral-500">
              {group}
            </div>
            <ul className="flex flex-col gap-0.5">
              {NAV.filter((n) => n.group === group).map((n) => {
                const Icon = n.icon;
                const count = n.badgeKey ? counts?.[n.badgeKey] ?? 0 : 0;
                return (
                  <li key={n.href}>
                    <Link
                      href={n.href}
                      className="flex items-center gap-2 rounded-md px-2 py-1.5 text-neutral-700 transition-colors hover:bg-neutral-100 hover:text-neutral-900 dark:text-neutral-300 dark:hover:bg-neutral-800 dark:hover:text-neutral-50"
                    >
                      <Icon size={16} className="opacity-70" />
                      <span className="grow">{n.label}</span>
                      {count > 0 && (
                        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[10px] font-medium text-amber-900 dark:bg-amber-900/40 dark:text-amber-100">
                          {count}
                        </span>
                      )}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>
    </aside>
  );
}

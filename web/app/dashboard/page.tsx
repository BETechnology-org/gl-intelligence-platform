import { cookies } from "next/headers";
import { createClient } from "@/utils/supabase/server";

export default async function DashboardOverview() {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="mx-auto max-w-6xl">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">Overview</h1>
        <p className="mt-1 text-sm text-neutral-500">
          Welcome back{user?.email ? `, ${user.email}` : ""} — close cycle status, KPIs, and pending reviews.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card title="Tax classifier — pending" subtitle="ASU 2023-09" href="/dashboard/tax/classifier" />
        <Card title="DISE mapping — pending" subtitle="ASU 2024-03" href="/dashboard/dise/mapping" />
        <Card title="Open anomalies (P1)" subtitle="DISE" href="/dashboard/dise/anomalies" />
      </div>

      <div className="mt-8 rounded-lg border border-neutral-200 p-6 dark:border-neutral-800">
        <h2 className="text-sm font-semibold uppercase tracking-widest text-neutral-500">
          Compliance posture
        </h2>
        <ul className="mt-3 space-y-2 text-sm">
          <li>
            <span className="font-medium">ASU 2023-09 (Income Tax)</span> — effective for CY 2025
            10-K. <a className="underline" href="/dashboard/tax/disclosure">View footnote draft →</a>
          </li>
          <li>
            <span className="font-medium">ASU 2024-03 (DISE)</span> — effective annual periods after
            Dec 15, 2026. <a className="underline" href="/dashboard/dise/disclosure">View footnote draft →</a>
          </li>
        </ul>
      </div>
    </div>
  );
}

function Card({ title, subtitle, href }: { title: string; subtitle: string; href: string }) {
  return (
    <a
      href={href}
      className="rounded-lg border border-neutral-200 bg-white p-5 transition-colors hover:border-neutral-300 dark:border-neutral-800 dark:bg-neutral-900 dark:hover:border-neutral-700"
    >
      <div className="text-xs font-semibold uppercase tracking-widest text-neutral-500">
        {subtitle}
      </div>
      <div className="mt-1 text-base font-medium">{title}</div>
      <div className="mt-3 text-xs text-neutral-500">Open queue →</div>
    </a>
  );
}

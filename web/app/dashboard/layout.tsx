import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { Sidebar } from "@/components/dashboard/Sidebar";
import { TopBar } from "@/components/dashboard/TopBar";
import { createClient } from "@/utils/supabase/server";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    redirect("/login?redirect=/dashboard");
  }

  // Pull current company + fiscal year from the user's role assignments.
  // For v1 we pick the first assignment; the TopBar lets the user switch.
  const { data: role } = await supabase
    .from("role_assignments")
    .select("company_id, role, companies(code, fiscal_year)")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();

  const company = (role?.companies as unknown) as { code?: string; fiscal_year?: string } | null;
  const companyCode = company?.code ?? "C006";
  const fiscalYear = company?.fiscal_year ?? "2025";

  // Cheap badge counts — surface on the sidebar so reviewers know what's queued.
  const [{ count: taxPending }, { count: disePending }, { count: anomaliesOpen }] = await Promise.all([
    supabase
      .from("tax_pending_mappings")
      .select("id", { count: "exact", head: true })
      .eq("status", "PENDING"),
    supabase
      .from("dise_pending_mappings")
      .select("id", { count: "exact", head: true })
      .eq("status", "PENDING"),
    supabase
      .from("dise_anomaly_alerts")
      .select("id", { count: "exact", head: true })
      .eq("status", "open"),
  ]);

  return (
    <div className="flex min-h-screen bg-white text-neutral-900 dark:bg-neutral-950 dark:text-neutral-100">
      <Sidebar
        counts={{
          tax_pending: taxPending ?? 0,
          dise_pending: disePending ?? 0,
          dise_anomalies_open: anomaliesOpen ?? 0,
        }}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar fiscalYear={fiscalYear} companyCode={companyCode} userEmail={user.email} />
        <main className="min-w-0 flex-1 overflow-y-auto px-8 py-6">{children}</main>
      </div>
    </div>
  );
}

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { createClient } from "@/utils/supabase/server";

export interface SessionContext {
  userId: string;
  email: string | null;
  companyId: string;
  companyCode: string;
  fiscalYear: string;
}

/**
 * Resolve the current authenticated user's session + first company assignment.
 * Redirects to /login if not authenticated. Throws if no role assignment.
 */
export async function requireSession(redirectPath?: string): Promise<SessionContext> {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) {
    redirect(`/login${redirectPath ? `?redirect=${encodeURIComponent(redirectPath)}` : ""}`);
  }

  const { data: role } = await supabase
    .from("role_assignments")
    .select("company_id, companies(code, fiscal_year)")
    .eq("user_id", user.id)
    .limit(1)
    .maybeSingle();

  const company = (role?.companies as unknown) as
    | { code?: string; fiscal_year?: string } | null;

  return {
    userId: user.id,
    email: user.email ?? null,
    companyId: (role?.company_id as string) ?? "00000000-0000-0000-0000-000000000c06",
    companyCode: company?.code ?? "C006",
    fiscalYear: company?.fiscal_year ?? "2024",
  };
}

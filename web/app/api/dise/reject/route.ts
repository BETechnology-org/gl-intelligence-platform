import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { writeAudit } from "@/lib/audit";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as { pending_id?: string; reason?: string };
  if (!body.pending_id || !body.reason) {
    return NextResponse.json({ error: "pending_id + reason required" }, { status: 400 });
  }

  const admin = getSupabaseAdmin();
  const { data: pending } = await admin
    .from("dise_pending_mappings")
    .select("*")
    .eq("id", body.pending_id)
    .single();
  if (!pending) return NextResponse.json({ error: "not found" }, { status: 404 });
  if (pending.status !== "PENDING") {
    return NextResponse.json({ error: `already ${pending.status}` }, { status: 409 });
  }

  await admin
    .from("dise_pending_mappings")
    .update({
      status: "REJECTED",
      reviewer: user.id,
      reviewed_at: new Date().toISOString(),
      override_reason: body.reason,
    })
    .eq("id", body.pending_id);

  await writeAudit({
    company_id: pending.company_id,
    module: "dise",
    event_type: "HUMAN_REJECTED",
    actor: user.id,
    actor_type: "HUMAN",
    user_id: user.id,
    gl_account: pending.gl_account,
    fiscal_year: pending.fiscal_year,
    pending_id: pending.id,
    payload: {
      reason: body.reason,
      agent_category: pending.suggested_category,
      agent_caption: pending.suggested_caption,
    },
  });

  return NextResponse.json({ ok: true, status: "REJECTED" });
}

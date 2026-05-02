import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { writeAudit } from "@/lib/audit";
import { DISE_CATEGORIES, DISE_CAPTIONS, DISE_CITATIONS, type DISECategory, type DISECaption } from "@/lib/dise-categories";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as {
    pending_id?: string;
    override_category?: string;
    override_caption?: string;
    override_reason?: string;
  };
  if (!body.pending_id) {
    return NextResponse.json({ error: "pending_id required" }, { status: 400 });
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

  const finalCategory = (body.override_category || pending.suggested_category) as DISECategory;
  const finalCaption = (body.override_caption || pending.suggested_caption) as DISECaption;
  if (!DISE_CATEGORIES.includes(finalCategory)) {
    return NextResponse.json({ error: `invalid category: ${finalCategory}` }, { status: 400 });
  }
  if (!DISE_CAPTIONS.includes(finalCaption)) {
    return NextResponse.json({ error: `invalid caption: ${finalCaption}` }, { status: 400 });
  }
  if ((body.override_category || body.override_caption) && !body.override_reason) {
    return NextResponse.json({ error: "override_reason required" }, { status: 400 });
  }

  const { data: approved, error: insertErr } = await admin
    .from("dise_approved_mappings")
    .insert({
      company_id: pending.company_id,
      pending_id: pending.id,
      gl_account: pending.gl_account,
      description: pending.description,
      posting_amount: pending.posting_amount,
      fiscal_year: pending.fiscal_year,
      dise_category: finalCategory,
      expense_caption: finalCaption,
      asc_citation: pending.suggested_citation ?? DISE_CITATIONS[finalCategory],
      override_reason: body.override_reason ?? null,
      reviewer: user.id,
    })
    .select("id")
    .single();
  if (insertErr) {
    return NextResponse.json({ error: insertErr.message }, { status: 500 });
  }

  const overridden = !!(body.override_category || body.override_caption);
  const newStatus = overridden ? "OVERRIDDEN" : "APPROVED";

  await admin
    .from("dise_pending_mappings")
    .update({
      status: newStatus,
      reviewer: user.id,
      reviewed_at: new Date().toISOString(),
      reviewed_category: finalCategory,
      reviewed_caption: finalCaption,
      reviewed_citation: pending.suggested_citation ?? DISE_CITATIONS[finalCategory],
      override_reason: body.override_reason ?? null,
    })
    .eq("id", body.pending_id);

  await writeAudit({
    company_id: pending.company_id,
    module: "dise",
    event_type: overridden ? "HUMAN_OVERRIDDEN" : "HUMAN_APPROVED",
    actor: user.id,
    actor_type: "HUMAN",
    user_id: user.id,
    gl_account: pending.gl_account,
    fiscal_year: pending.fiscal_year,
    pending_id: pending.id,
    approved_id: approved?.id as string,
    payload: {
      agent_category: pending.suggested_category,
      agent_caption: pending.suggested_caption,
      final_category: finalCategory,
      final_caption: finalCaption,
      override_reason: body.override_reason ?? null,
    },
  });

  return NextResponse.json({
    ok: true,
    approved_id: approved?.id,
    status: newStatus,
    dise_category: finalCategory,
    expense_caption: finalCaption,
  });
}

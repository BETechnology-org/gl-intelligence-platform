import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { writeAudit } from "@/lib/audit";
import { TAX_CATEGORIES, TAX_CATEGORY_LABELS, ASC_CITATIONS_HINT } from "@/lib/tax-categories";
import type { TaxCategory } from "@/lib/api";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supabase = createClient(cookieStore);
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as {
    pending_id?: string;
    override_category?: string;
    override_reason?: string;
  };
  if (!body.pending_id) {
    return NextResponse.json({ error: "pending_id required" }, { status: 400 });
  }

  const admin = getSupabaseAdmin();

  const { data: pending, error: fetchErr } = await admin
    .from("tax_pending_mappings")
    .select("*")
    .eq("id", body.pending_id)
    .single();
  if (fetchErr || !pending) {
    return NextResponse.json({ error: "pending not found" }, { status: 404 });
  }
  if (pending.status !== "PENDING") {
    return NextResponse.json({ error: `already ${pending.status}` }, { status: 409 });
  }

  const finalCategory = (body.override_category || pending.tax_category) as TaxCategory;
  if (!TAX_CATEGORIES.includes(finalCategory)) {
    return NextResponse.json({ error: `invalid category: ${finalCategory}` }, { status: 400 });
  }
  if (body.override_category && !body.override_reason) {
    return NextResponse.json(
      { error: "override_reason required when override_category set" },
      { status: 400 },
    );
  }

  const { data: approved, error: insertErr } = await admin
    .from("tax_approved_mappings")
    .insert({
      company_id: pending.company_id,
      pending_id: pending.id,
      gl_account: pending.gl_account,
      description: pending.description,
      posting_amount: pending.posting_amount,
      fiscal_year: pending.fiscal_year,
      account_type: pending.account_type,
      jurisdiction_hint: pending.jurisdiction_hint,
      tax_category: finalCategory,
      tax_category_label: TAX_CATEGORY_LABELS[finalCategory],
      asc_citation: ASC_CITATIONS_HINT[finalCategory] ?? null,
      override_reason: body.override_reason ?? null,
      reviewer: user.id,
    })
    .select("id")
    .single();
  if (insertErr) {
    return NextResponse.json({ error: insertErr.message }, { status: 500 });
  }

  const newStatus = body.override_category ? "OVERRIDDEN" : "APPROVED";
  await admin
    .from("tax_pending_mappings")
    .update({
      status: newStatus,
      reviewer: user.id,
      reviewed_at: new Date().toISOString(),
      reviewed_category: finalCategory,
      override_reason: body.override_reason ?? null,
    })
    .eq("id", body.pending_id);

  await writeAudit({
    company_id: pending.company_id,
    module: "tax",
    event_type: body.override_category ? "HUMAN_OVERRIDDEN" : "HUMAN_APPROVED",
    actor: user.id,
    actor_type: "HUMAN",
    user_id: user.id,
    gl_account: pending.gl_account,
    fiscal_year: pending.fiscal_year,
    pending_id: pending.id,
    approved_id: approved?.id as string,
    payload: {
      agent_category: pending.tax_category,
      final_category: finalCategory,
      override_reason: body.override_reason ?? null,
    },
  });

  return NextResponse.json({
    ok: true,
    approved_id: approved?.id,
    status: newStatus,
    tax_category: finalCategory,
  });
}

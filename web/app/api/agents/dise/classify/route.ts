import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { classifyJSON, ANTHROPIC_MODEL } from "@/lib/anthropic";
import { writeAudit } from "@/lib/audit";
import {
  DISE_CATEGORIES,
  DISE_CAPTIONS,
  DISE_CITATIONS,
  DISE_SYSTEM_PROMPT,
  type DISECategory,
  type DISECaption,
} from "@/lib/dise-categories";

export const runtime = "nodejs";
export const maxDuration = 300;

const PROMPT_VERSION = "v2.0";
const AGENT_ID = "DISE_MAPPING_AGENT_v2_next";

interface AgentDecision {
  suggested_category: string;
  suggested_caption: string;
  suggested_citation?: string;
  confidence_score: number;
  confidence_label: "HIGH" | "MEDIUM" | "LOW";
  draft_reasoning: string;
}

interface UnmappedAccount {
  gl_account: string;
  description: string;
  posting_amount: number | string;
  fiscal_year: string;
  company_code: string;
  account_type: string | null;
  sub_type: string | null;
}

function materialityFlag(amount: number): "HIGH" | "MEDIUM" | "LOW" {
  if (amount >= 500_000) return "HIGH";
  if (amount >= 100_000) return "MEDIUM";
  return "LOW";
}

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supabaseUser = createClient(cookieStore);
  const { data: { user } } = await supabaseUser.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = (await req.json().catch(() => ({}))) as {
    company_id?: string;
    fiscal_year?: string;
    batch_size?: number;
  };
  if (!body.company_id || !body.fiscal_year) {
    return NextResponse.json({ error: "company_id and fiscal_year required" }, { status: 400 });
  }
  const batchSize = Math.min(Math.max(body.batch_size ?? 20, 1), 100);

  const admin = getSupabaseAdmin();

  const { data: accounts, error } = await admin.rpc("get_unmapped_dise_accounts", {
    p_company_id: body.company_id,
    p_fiscal_year: body.fiscal_year,
    p_limit: batchSize,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  const queue = (accounts as UnmappedAccount[]) ?? [];
  if (queue.length === 0) {
    return NextResponse.json({ ok: true, classified: 0, message: "no unmapped expense accounts" });
  }

  const results: Array<{ gl_account: string; suggested_category: string; confidence_label: string }> = [];
  let processed = 0;
  let errors = 0;

  for (const a of queue) {
    const { data: similar } = await admin.rpc("find_similar_dise_mappings", {
      p_company_id: body.company_id,
      p_fiscal_year: body.fiscal_year,
      p_query: a.description ?? "",
      p_limit: 5,
    });
    const similarRows = (similar as Array<Record<string, unknown>>) ?? [];

    const simBlock = similarRows.length
      ? "SIMILAR APPROVED:\n" + similarRows
          .map((s, i) => `${i + 1}. ${s.gl_account} — "${s.description}" → ${s.dise_category} / ${s.expense_caption}`)
          .join("\n")
      : "No similar approved mappings found — classify from first principles.";

    const amount = Number(a.posting_amount ?? 0);
    const userPrompt = `Classify this GL account:
GL: ${a.gl_account}
Description: ${(a.description ?? "").slice(0, 500)}
Account type: ${a.account_type ?? "unknown"}
Sub-type: ${a.sub_type ?? "unknown"}
FY ${a.fiscal_year} amount: $${amount.toLocaleString()}

${simBlock}

Respond with JSON only.`;

    let decision: AgentDecision | null = null;
    try {
      decision = await classifyJSON<AgentDecision>({
        system: DISE_SYSTEM_PROMPT,
        prompt: userPrompt,
        maxTokens: 800,
      });
    } catch (e) {
      console.error("DISE classify error:", e);
    }

    if (
      !decision
      || !DISE_CATEGORIES.includes(decision.suggested_category as DISECategory)
      || !DISE_CAPTIONS.includes(decision.suggested_caption as DISECaption)
    ) {
      errors += 1;
      continue;
    }

    const cat = decision.suggested_category as DISECategory;
    const cap = decision.suggested_caption as DISECaption;

    const inserted = await admin
      .from("dise_pending_mappings")
      .insert({
        company_id: body.company_id,
        gl_account: a.gl_account,
        description: a.description,
        posting_amount: amount,
        fiscal_year: a.fiscal_year,
        suggested_category: cat,
        suggested_caption: cap,
        suggested_citation: decision.suggested_citation ?? DISE_CITATIONS[cat],
        draft_reasoning: decision.draft_reasoning?.slice(0, 5000) ?? "",
        confidence_score: decision.confidence_score,
        confidence_label: decision.confidence_label,
        similar_accounts: similarRows.slice(0, 5),
        materiality_flag: materialityFlag(amount),
        status: "PENDING",
        drafted_by: AGENT_ID,
        model_version: ANTHROPIC_MODEL,
        prompt_version: PROMPT_VERSION,
      })
      .select("id")
      .single();

    if (inserted.error) {
      console.warn("insert dise pending failed:", inserted.error.message);
      errors += 1;
      continue;
    }

    await writeAudit({
      company_id: body.company_id,
      module: "dise",
      event_type: "AGENT_DRAFT",
      actor: AGENT_ID,
      actor_type: "AGENT",
      user_id: user.id,
      gl_account: a.gl_account,
      fiscal_year: a.fiscal_year,
      pending_id: inserted.data?.id as string,
      model_version: ANTHROPIC_MODEL,
      prompt_version: PROMPT_VERSION,
      tool_name: "classifyJSON",
      tool_input: { description: a.description, posting_amount: amount },
      tool_result: {
        suggested_category: cat,
        suggested_caption: cap,
        confidence_score: decision.confidence_score,
        confidence_label: decision.confidence_label,
      },
      payload: { batch_size: batchSize, materiality: materialityFlag(amount) },
    });

    results.push({
      gl_account: a.gl_account,
      suggested_category: cat,
      confidence_label: decision.confidence_label,
    });
    processed += 1;
  }

  return NextResponse.json({
    ok: true,
    classified: processed,
    errors,
    results,
    queue_size: queue.length,
  });
}

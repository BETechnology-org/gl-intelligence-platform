import { NextRequest, NextResponse } from "next/server";
import { cookies } from "next/headers";

import { createClient } from "@/utils/supabase/server";
import { getSupabaseAdmin } from "@/lib/supabase-admin";
import { classifyJSON, ANTHROPIC_MODEL } from "@/lib/anthropic";
import { writeAudit } from "@/lib/audit";
import { TAX_CATEGORIES, TAX_CATEGORY_LABELS, ASC_CITATIONS_HINT } from "@/lib/tax-categories";
import type { TaxCategory } from "@/lib/api";

export const runtime = "nodejs";
export const maxDuration = 300; // 5 min cap

const PROMPT_VERSION = "v2.0";
const AGENT_ID = "TAX_CLASSIFIER_AGENT_v2_next";

const SYSTEM_PROMPT = `You are the Tax GL Classifier for Truffles AI's BL Intelligence platform.

Classify SAP GL accounts (range 160000-199999) into ASC 740 income tax categories
for ASU 2023-09 disclosure (rate reconciliation, jurisdictional disagg, cash taxes).

VALID TAX CATEGORIES (return exactly one):
- current_federal     | current_state     | current_foreign
- deferred_federal    | deferred_state    | deferred_foreign
- deferred_tax_asset  | deferred_tax_liab
- pretax_domestic     | pretax_foreign
- not_tax_account

ACCOUNT RANGE RULES:
- 160000-160299 = current tax expense
- 161000-161299 = deferred tax expense
- 162000-162999 = balance-sheet DTA
- 163000-163999 = balance-sheet DTL
- 164000-164999 = pretax income
- "non-deductible" / "M&E" / "§162(m)" alone = not_tax_account

CONFIDENCE: HIGH (0.85-1.00) | MEDIUM (0.60-0.84) | LOW (<0.60).

Respond ONLY with valid JSON:
{"tax_category":"...","confidence_score":0.92,"confidence_label":"HIGH","draft_reasoning":"<2-4 sentences>"}`;

interface AgentDecision {
  tax_category: string;
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

export async function POST(req: NextRequest) {
  const cookieStore = await cookies();
  const supabaseUser = createClient(cookieStore);
  const { data: { user } } = await supabaseUser.auth.getUser();
  if (!user) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  const body = await req.json().catch(() => ({})) as {
    company_id?: string;
    fiscal_year?: string;
    batch_size?: number;
  };
  if (!body.company_id || !body.fiscal_year) {
    return NextResponse.json({ error: "company_id and fiscal_year required" }, { status: 400 });
  }
  const batchSize = Math.min(Math.max(body.batch_size ?? 18, 1), 50);

  const admin = getSupabaseAdmin();

  const { data: accounts, error } = await admin.rpc("get_unmapped_tax_accounts", {
    p_company_id: body.company_id,
    p_fiscal_year: body.fiscal_year,
    p_limit: batchSize,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  const queue = (accounts as UnmappedAccount[]) ?? [];
  if (queue.length === 0) {
    return NextResponse.json({ ok: true, classified: 0, message: "no unmapped tax accounts" });
  }

  const results: Array<{ gl_account: string; tax_category: string; confidence_label: string }> = [];
  let processed = 0;
  let errors = 0;

  for (const a of queue) {
    const { data: similar } = await admin.rpc("find_similar_tax_mappings", {
      p_company_id: body.company_id,
      p_fiscal_year: body.fiscal_year,
      p_query: a.description ?? "",
      p_limit: 5,
    });
    const similarRows = (similar as Array<Record<string, unknown>>) ?? [];

    const simBlock = similarRows.length
      ? "SIMILAR APPROVED:\n" + similarRows
          .map((s, i) => `${i + 1}. ${s.gl_account} — "${s.description}" → ${s.tax_category} (${s.confidence_label ?? "?"})`)
          .join("\n")
      : "No similar approved mappings found — classify from first principles.";

    const userPrompt = `Classify this GL account:
GL: ${a.gl_account}
Description: ${(a.description ?? "").slice(0, 500)}
SAP Account Type: ${a.account_type ?? "unknown"}
Sub-type: ${a.sub_type ?? "unknown"}
FY ${a.fiscal_year} amount: $${Number(a.posting_amount ?? 0).toLocaleString()}

${simBlock}

Respond with JSON only.`;

    let decision: AgentDecision | null = null;
    try {
      decision = await classifyJSON<AgentDecision>({
        system: SYSTEM_PROMPT,
        prompt: userPrompt,
        maxTokens: 600,
      });
    } catch (e) {
      console.error("classify error:", e);
    }

    if (!decision || !TAX_CATEGORIES.includes(decision.tax_category as TaxCategory)) {
      errors += 1;
      continue;
    }

    const cat = decision.tax_category as TaxCategory;
    const inserted = await admin
      .from("tax_pending_mappings")
      .insert({
        company_id: body.company_id,
        gl_account: a.gl_account,
        description: a.description,
        posting_amount: Number(a.posting_amount ?? 0),
        fiscal_year: a.fiscal_year,
        account_type: a.account_type,
        jurisdiction_hint: null,
        tax_category: cat,
        tax_category_label: TAX_CATEGORY_LABELS[cat],
        asc_citation: ASC_CITATIONS_HINT[cat] ?? null,
        disclosure_table: null,
        draft_reasoning: decision.draft_reasoning?.slice(0, 5000) ?? "",
        confidence_score: decision.confidence_score,
        confidence_label: decision.confidence_label,
        similar_accounts: similarRows.slice(0, 5),
        status: "PENDING",
        drafted_by: AGENT_ID,
        model_version: ANTHROPIC_MODEL,
        prompt_version: PROMPT_VERSION,
      })
      .select("id")
      .single();

    if (inserted.error) {
      // most common cause: duplicate (company_id, gl_account, fiscal_year, drafted_at)
      console.warn("insert pending failed:", inserted.error.message);
      errors += 1;
      continue;
    }

    await writeAudit({
      company_id: body.company_id,
      module: "tax",
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
      tool_input: { description: a.description, posting_amount: a.posting_amount },
      tool_result: {
        tax_category: cat,
        confidence_score: decision.confidence_score,
        confidence_label: decision.confidence_label,
      },
      payload: { batch_size: batchSize },
    });

    results.push({
      gl_account: a.gl_account,
      tax_category: cat,
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

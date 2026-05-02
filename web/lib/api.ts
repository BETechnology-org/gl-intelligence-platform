/**
 * Typed API client.
 *
 * v1 (Vercel-only deploy): targets the Next.js route handlers under
 * `app/api/*` — same Supabase + Anthropic from the server, no separate
 * FastAPI process required.
 *
 * v2 (Cloud Run FastAPI deploy): set NEXT_PUBLIC_API_BASE_URL to the
 * deployed FastAPI URL and the same code path works.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

export type TaxCategory =
  | "current_federal" | "current_state" | "current_foreign"
  | "deferred_federal" | "deferred_state" | "deferred_foreign"
  | "deferred_tax_asset" | "deferred_tax_liab"
  | "pretax_domestic" | "pretax_foreign"
  | "not_tax_account";

export type ConfidenceLabel = "HIGH" | "MEDIUM" | "LOW";
export type MappingStatus = "PENDING" | "APPROVED" | "REJECTED" | "OVERRIDDEN";

export interface TaxPendingMapping {
  id: string;
  company_id: string;
  gl_account: string;
  description: string | null;
  posting_amount: number;
  fiscal_year: string;
  account_type: string | null;
  jurisdiction_hint: string | null;
  tax_category: TaxCategory;
  tax_category_label: string;
  asc_citation: string | null;
  disclosure_table: string | null;
  draft_reasoning: string | null;
  confidence_score: number;
  confidence_label: ConfidenceLabel;
  similar_accounts: Array<Record<string, unknown>>;
  status: MappingStatus;
  drafted_by: string;
  drafted_at: string;
  model_version: string;
  prompt_version: string;
}

export interface TaxApprovedMapping extends TaxPendingMapping {
  reviewer: string | null;
  reviewed_at: string;
  override_reason: string | null;
  promoted_to_bq_at: string | null;
}

async function authHeaders(token: string | null): Promise<HeadersInit> {
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

async function apiFetch<T>(
  path: string,
  init: RequestInit & { token?: string | null } = {},
): Promise<T> {
  const { token = null, ...rest } = init;
  const res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: { ...(await authHeaders(token)), ...(rest.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return (await res.json()) as T;
}

// ── Tax module ────────────────────────────────────────────────────────

export async function listPendingTax(
  params: { companyId: string; fiscalYear: string; limit?: number; token: string | null },
): Promise<{ count: number; pending: TaxPendingMapping[] }> {
  const q = new URLSearchParams({
    company_id: params.companyId,
    fiscal_year: params.fiscalYear,
    limit: String(params.limit ?? 50),
  });
  return apiFetch(`/api/tax/pending?${q}`, { token: params.token });
}

export async function listApprovedTax(
  params: { companyId: string; fiscalYear: string; token: string | null },
): Promise<{ count: number; approved: TaxApprovedMapping[] }> {
  const q = new URLSearchParams({
    company_id: params.companyId,
    fiscal_year: params.fiscalYear,
  });
  return apiFetch(`/api/tax/approved?${q}`, { token: params.token });
}

export async function approveTax(
  body: { pending_id: string; override_category?: string; override_reason?: string },
  _token: string | null,
): Promise<{ ok: boolean; approved_id: string; status: string; tax_category: string }> {
  return apiFetch(`/api/tax/approve`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function rejectTax(
  body: { pending_id: string; reason: string },
  _token: string | null,
): Promise<{ ok: boolean; status: string }> {
  return apiFetch(`/api/tax/reject`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// SSE streaming — used only when NEXT_PUBLIC_API_BASE_URL points to the
// FastAPI deployment. v1 Vercel deploy uses synchronous AgentRunButton instead.

export interface AgentEvent {
  type: "system" | "assistant" | "tool_use" | "tool_result" | "result" | "done" | "error" | "cancelled" | string;
  [key: string]: unknown;
}

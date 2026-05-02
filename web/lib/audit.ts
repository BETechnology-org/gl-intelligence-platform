/**
 * Audit log writer — TS counterpart to api/src/db/audit.py.
 * Always called from server-side code (route handlers / server actions).
 */

import { getSupabaseAdmin } from "./supabase-admin";

export type AuditModule = "tax" | "dise" | "platform";

export interface AuditEvent {
  company_id: string;
  module: AuditModule;
  event_type: string;
  actor: string;
  actor_type: "AGENT" | "HUMAN" | "SYSTEM";
  user_id?: string | null;
  gl_account?: string | null;
  fiscal_year?: string | null;
  pending_id?: string | null;
  approved_id?: string | null;
  model_version?: string | null;
  prompt_version?: string | null;
  tool_name?: string | null;
  tool_input?: Record<string, unknown> | null;
  tool_result?: Record<string, unknown> | null;
  payload?: Record<string, unknown>;
}

export async function writeAudit(event: AuditEvent): Promise<void> {
  try {
    await getSupabaseAdmin()
      .from("audit_log")
      .insert({ ...event, payload: event.payload ?? {} });
  } catch (e) {
    console.error("audit_log insert failed (non-fatal):", e);
  }
}

/**
 * Supabase service-role client for server-side mutations that bypass RLS.
 *
 * NEVER import this from a Client Component or expose to the browser. It
 * uses the SERVICE_ROLE key. Only safe in server-side route handlers and
 * server actions.
 *
 * Typed `any` so TypeScript doesn't complain about our custom RPCs
 * (`get_unmapped_*`, `find_similar_*`, etc.) — those don't exist in
 * the default generated types. When we run `supabase gen types
 * typescript`, drop the `any` and wire the Database generic.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
import { createClient, type SupabaseClient } from "@supabase/supabase-js";

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const serviceRole = process.env.SUPABASE_SERVICE_ROLE_KEY;

let _admin: SupabaseClient<any, "public", any> | null = null;

export function getSupabaseAdmin(): SupabaseClient<any, "public", any> {
  if (!url) throw new Error("NEXT_PUBLIC_SUPABASE_URL not set");
  if (!serviceRole) throw new Error("SUPABASE_SERVICE_ROLE_KEY not set");
  if (!_admin) {
    _admin = createClient<any, "public", any>(url, serviceRole, {
      auth: { autoRefreshToken: false, persistSession: false },
    });
  }
  return _admin;
}

"""Helpers used by agent hooks/tools to read Supabase state.

Kept thin — the agents call these from within tool implementations or
hooks; the tools themselves are the canonical interface presented to
the model.
"""

from __future__ import annotations

import logging
from typing import Any

from ..db import get_supabase_admin

log = logging.getLogger(__name__)


# Cap on bytes injected into the user prompt per turn. Keeps the prompt
# cache hit rate high — the system prompt stays constant, and the user
# message stays small + bounded.
STATE_PREFIX_MAX_CHARS = 8000


async def build_state_prefix(
    *, company_id: str, fiscal_year: str, module: str = "tax"
) -> str:
    """Return a CURRENT STATE block for the given company × fiscal year × module.

    For tax: list the most recent approved tax mappings (gl_account →
    tax_category) so the agent doesn't re-suggest already-decided rows.
    For DISE: same idea with dise_approved_mappings.
    """
    table = f"{module}_approved_mappings"
    try:
        supabase = get_supabase_admin()
        rows = (
            supabase.table(table)
            .select("gl_account,description,tax_category,dise_category,expense_caption,reviewed_at")
            .eq("company_id", company_id)
            .eq("fiscal_year", fiscal_year)
            .order("reviewed_at", desc=True)
            .limit(50)
            .execute()
        ).data
    except Exception as e:
        log.warning("build_state_prefix failed: %s", e)
        return ""

    if not rows:
        return ""

    lines = [f"## CURRENT STATE — approved {module.upper()} mappings (most recent 50)\n"]
    for r in rows:
        cat = r.get("tax_category") or r.get("dise_category") or "?"
        cap = r.get("expense_caption") or ""
        desc = (r.get("description") or "")[:80]
        suffix = f" → {cat}" + (f" / {cap}" if cap else "")
        lines.append(f"- {r['gl_account']:<12} {desc:<80}{suffix}")

    block = "\n".join(lines)
    if len(block) > STATE_PREFIX_MAX_CHARS:
        block = block[:STATE_PREFIX_MAX_CHARS] + "\n... (truncated)"
    return block + "\n"


async def find_similar_descriptions(
    *,
    company_id: str,
    fiscal_year: str,
    description: str,
    table: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Trigram similarity search against approved descriptions.

    Uses the `gin_trgm_ops` indexes from migration 0001. Returns rows
    ordered by similarity descending.
    """
    if not description:
        return []
    sql = f"""
    select *, similarity(description, %(q)s) as similarity_score
    from public.{table}
    where company_id = %(cid)s
      and fiscal_year = %(fy)s
      and description %% %(q)s
    order by similarity_score desc
    limit %(lim)s
    """
    try:
        supabase = get_supabase_admin()
        # Supabase Python client doesn't support raw SQL via postgrest; route
        # through an RPC function or asyncpg. Stub via RPC for now.
        result = supabase.rpc(
            "find_similar_mappings",
            {"p_table": table, "p_company_id": company_id,
             "p_fiscal_year": fiscal_year, "p_query": description, "p_limit": limit},
        ).execute()
        return result.data or []
    except Exception as e:
        log.warning("find_similar_descriptions failed: %s", e)
        return []

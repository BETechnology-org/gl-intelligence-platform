"""Decomposed tools for the Tax module agents.

Each tool is a deterministic, pure-as-possible function exposed to the
model via an in-process MCP server (claude-code-sdk's create_sdk_mcp_server).
Tests can call these directly without the LLM.

Tools shipped in Phase 1 (TaxClassifierAgent):
- get_unmapped_tax_accounts(fiscal_year, company_code, batch_size)
- lookup_similar_approved_mappings(description, limit)
- lookup_asc_citation(tax_category)
- write_pending_mapping(decision)

Phase 2 (ETRBridgeAgent / TaxDisclosureAgent) will add:
- get_approved_tax_mappings, compute_pretax_split,
  compute_rate_recon_line, check_jurisdictional_threshold,
  compute_state_majority, generate_disclosure_section.
"""

from __future__ import annotations

import logging
from typing import Any

from ...config import settings
from ...db import get_supabase_admin
from ...db.cortex import get_cortex
from .categories import ASC_CITATIONS, CATEGORY_TO_TABLE, TAX_CATEGORIES, TAX_CATEGORY_LABELS

log = logging.getLogger(__name__)


def _ok(data: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": _to_text(data)}]}


def _to_text(data: Any) -> str:
    import json
    if isinstance(data, str):
        return data
    return json.dumps(data, indent=2, default=str)


# ── Tool implementations (sync helpers — wrapped by SDK adapter) ──────


def impl_get_unmapped_tax_accounts(
    *, company_id: str, fiscal_year: str, batch_size: int = 18
) -> dict[str, Any]:
    """Return GL accounts in the tax range that are NOT yet approved.

    v1 source: Supabase `get_unmapped_tax_accounts` RPC, which reads
    `gl_trial_balance` (computed from finance-datasets/ ingest) and
    excludes rows already in tax_approved_mappings.

    v2 path: same RPC but backed by live SAP/Oracle Cortex via the
    BigQuery client in api/src/db/cortex.py — no agent change needed.
    """
    try:
        rows = (
            get_supabase_admin()
            .rpc("get_unmapped_tax_accounts", {
                "p_company_id": company_id,
                "p_fiscal_year": fiscal_year,
                "p_limit": int(batch_size),
            })
            .execute()
        ).data or []
        return {"accounts": rows, "count": len(rows), "source": "supabase"}
    except Exception as e:
        log.warning("get_unmapped_tax_accounts failed: %s", e)
        return {"accounts": [], "count": 0, "source": "error", "error": str(e)}


def impl_lookup_similar_approved_mappings(
    *, company_id: str, fiscal_year: str, description: str, limit: int = 5
) -> dict[str, Any]:
    """Trigram similarity over Supabase tax_approved_mappings."""
    if not description.strip():
        return {"similar": [], "count": 0}
    try:
        supabase = get_supabase_admin()
        # Try the RPC first (if create-rpc migration is applied); fall back
        # to a simple equality-on-tokens approach.
        try:
            rows = supabase.rpc("find_similar_tax_mappings", {
                "p_company_id": company_id,
                "p_fiscal_year": fiscal_year,
                "p_query": description,
                "p_limit": limit,
            }).execute().data or []
        except Exception:
            # Fallback: ilike on description (less precise)
            rows = (
                supabase.table("tax_approved_mappings")
                .select("gl_account,description,tax_category,asc_citation")
                .eq("company_id", company_id)
                .eq("fiscal_year", fiscal_year)
                .ilike("description", f"%{description.split()[0]}%")
                .limit(limit)
                .execute()
            ).data or []
        return {"similar": rows, "count": len(rows)}
    except Exception as e:
        log.warning("lookup_similar_approved_mappings failed: %s", e)
        return {"similar": [], "count": 0, "error": str(e)}


def impl_lookup_asc_citation(*, tax_category: str) -> dict[str, Any]:
    """Return the canonical ASC citation for a tax category."""
    if tax_category not in TAX_CATEGORIES:
        return {
            "ok": False,
            "error": f"unknown tax_category: {tax_category}",
            "valid_categories": TAX_CATEGORIES,
        }
    return {
        "ok": True,
        "tax_category": tax_category,
        "label": TAX_CATEGORY_LABELS[tax_category],
        "citation": ASC_CITATIONS[tax_category],
        "disclosure_table": CATEGORY_TO_TABLE[tax_category],
    }


def impl_write_pending_mapping(
    *,
    company_id: str,
    user_id: str,
    fiscal_year: str,
    gl_account: str,
    description: str,
    posting_amount: float,
    account_type: str | None,
    jurisdiction_hint: str | None,
    tax_category: str,
    confidence_score: float,
    confidence_label: str,
    draft_reasoning: str,
    similar_accounts: list[dict] | None,
    drafted_by: str,
    model_version: str,
    prompt_version: str,
) -> dict[str, Any]:
    """Insert a row into tax_pending_mappings and return its id."""
    if tax_category not in TAX_CATEGORIES:
        return {"ok": False, "error": f"invalid tax_category: {tax_category}"}
    if not 0.0 <= confidence_score <= 1.0:
        return {"ok": False, "error": "confidence_score must be in [0,1]"}
    if confidence_label not in ("HIGH", "MEDIUM", "LOW"):
        return {"ok": False, "error": "confidence_label must be HIGH|MEDIUM|LOW"}

    row = {
        "company_id": company_id,
        "gl_account": gl_account,
        "description": description,
        "posting_amount": posting_amount,
        "fiscal_year": fiscal_year,
        "account_type": account_type,
        "jurisdiction_hint": jurisdiction_hint,
        "tax_category": tax_category,
        "tax_category_label": TAX_CATEGORY_LABELS[tax_category],
        "asc_citation": ASC_CITATIONS[tax_category],
        "disclosure_table": CATEGORY_TO_TABLE[tax_category],
        "draft_reasoning": draft_reasoning[:5000],
        "confidence_score": confidence_score,
        "confidence_label": confidence_label,
        "similar_accounts": similar_accounts or [],
        "status": "PENDING",
        "drafted_by": drafted_by,
        "model_version": model_version,
        "prompt_version": prompt_version,
    }
    try:
        result = get_supabase_admin().table("tax_pending_mappings").insert(row).execute()
        inserted = result.data[0] if result.data else None
        return {"ok": True, "pending_id": inserted["id"] if inserted else None, "row": inserted}
    except Exception as e:
        log.exception("write_pending_mapping failed: %s", e)
        return {"ok": False, "error": str(e)}


# ── SDK MCP server wiring ─────────────────────────────────────────────


def build_tax_classifier_mcp_server(*, company_id: str, user_id: str):
    """Return an in-process MCP server exposing the four classifier tools.

    `company_id` and `user_id` are bound at server construction time so
    the model can't pass them — eliminates a tenant-isolation footgun.
    """
    from claude_agent_sdk import create_sdk_mcp_server, tool  # type: ignore

    @tool(
        "get_unmapped_tax_accounts",
        "Fetch unmapped GL accounts in the tax range (160000-199999 SAP convention, plus any account whose description contains 'tax') that are NOT yet in the approved mappings table. Returns up to `batch_size` accounts ordered by absolute posting amount (= materiality).",
        {"fiscal_year": str, "batch_size": int},
    )
    async def _t1(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(impl_get_unmapped_tax_accounts(
            company_id=company_id,
            fiscal_year=args["fiscal_year"],
            batch_size=int(args.get("batch_size", 18)),
        ))

    @tool(
        "lookup_similar_approved_mappings",
        "Find approved tax mappings whose description is similar to the input. Returns up to `limit` rows ordered by similarity.",
        {"description": str, "limit": int},
    )
    async def _t2(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(impl_lookup_similar_approved_mappings(
            company_id=company_id,
            fiscal_year=args.get("fiscal_year") or "",
            description=args["description"],
            limit=int(args.get("limit", 5)),
        ))

    @tool(
        "lookup_asc_citation",
        "Return the canonical ASC 740 citation and disclosure-table assignment for a tax category. Use this instead of guessing citations.",
        {"tax_category": str},
    )
    async def _t3(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(impl_lookup_asc_citation(tax_category=args["tax_category"]))

    @tool(
        "write_pending_mapping",
        "Persist a draft tax classification to tax_pending_mappings. Returns the inserted row id.",
        {
            "fiscal_year": str,
            "gl_account": str,
            "description": str,
            "posting_amount": float,
            "account_type": str,
            "jurisdiction_hint": str,
            "tax_category": str,
            "confidence_score": float,
            "confidence_label": str,
            "draft_reasoning": str,
            "similar_accounts": list,
            "model_version": str,
            "prompt_version": str,
        },
    )
    async def _t4(args: dict[str, Any]) -> dict[str, Any]:
        return _ok(impl_write_pending_mapping(
            company_id=company_id,
            user_id=user_id,
            fiscal_year=args["fiscal_year"],
            gl_account=args["gl_account"],
            description=args.get("description", ""),
            posting_amount=float(args.get("posting_amount", 0)),
            account_type=args.get("account_type"),
            jurisdiction_hint=args.get("jurisdiction_hint"),
            tax_category=args["tax_category"],
            confidence_score=float(args["confidence_score"]),
            confidence_label=args["confidence_label"],
            draft_reasoning=args.get("draft_reasoning", ""),
            similar_accounts=args.get("similar_accounts") or [],
            drafted_by="TAX_CLASSIFIER_AGENT_v2",
            model_version=args.get("model_version", "unknown"),
            prompt_version=args.get("prompt_version", "v2.0"),
        ))

    return create_sdk_mcp_server(
        name="tax_classifier_tools",
        version="1.0.0",
        tools=[_t1, _t2, _t3, _t4],
    )

"""Supabase-backed store for tax classifier mappings.

Drop-in replacement for the module-level lists in
gl_intelligence/agents/tax_classifier_agent.py. Same shapes, same
method semantics — just durable.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from .audit import write_audit_event
from .supabase_client import DEFAULT_COMPANY_ID, get_supabase

log = logging.getLogger("persistence.tax_store")


_PENDING_TABLE = "tax_pending_mappings"
_APPROVED_TABLE = "tax_approved_mappings"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_for_supabase(entry: dict) -> dict:
    """Strip / map legacy entry fields to the Supabase tax_pending_mappings columns."""
    return {
        "company_id":          entry.get("company_id") or DEFAULT_COMPANY_ID,
        "gl_account":          entry["gl_account"],
        "description":         (entry.get("description") or "")[:500],
        "posting_amount":      float(entry.get("posting_amount", 0)),
        "fiscal_year":         str(entry.get("fiscal_year", "")),
        "account_type":        entry.get("account_type"),
        "jurisdiction_hint":   entry.get("jurisdiction_hint"),
        "tax_category":        entry["tax_category"],
        "tax_category_label":  entry.get("tax_category_label"),
        "asc_citation":        entry.get("asc_citation"),
        "disclosure_table":    entry.get("disclosure_table"),
        "draft_reasoning":     (entry.get("draft_reasoning") or "")[:5000],
        "confidence_score":    float(entry.get("confidence_score", 0)),
        "confidence_label":    entry.get("confidence_label", "MEDIUM"),
        "similar_accounts":    entry.get("similar_accounts") or [],
        "status":              "PENDING",
        "drafted_by":          entry.get("drafted_by", "TAX_CLASSIFIER_AGENT_v1"),
        "model_version":       entry.get("model_version", "unknown"),
        "prompt_version":      entry.get("prompt_version", "v1.1"),
    }


def write_pending(entry: dict) -> Optional[str]:
    """Insert a pending mapping. Returns inserted id, or None on failure."""
    sb = get_supabase()
    if sb is None:
        return None
    row = _row_for_supabase(entry)
    try:
        result = sb.table(_PENDING_TABLE).insert(row).execute()
        new_id = result.data[0]["id"] if result.data else None
        write_audit_event(
            module="tax",
            event_type="AGENT_DRAFT",
            actor=row["drafted_by"],
            actor_type="AGENT",
            company_id=row["company_id"],
            gl_account=row["gl_account"],
            fiscal_year=row["fiscal_year"],
            pending_id=new_id,
            model_version=row["model_version"],
            prompt_version=row["prompt_version"],
            tool_input={"description": row["description"]},
            tool_result={
                "tax_category": row["tax_category"],
                "confidence_score": row["confidence_score"],
                "confidence_label": row["confidence_label"],
            },
        )
        return new_id
    except Exception as e:  # noqa: BLE001
        log.error("tax_pending insert failed: %s", e)
        return None


def get_pending(*, company_id: str = DEFAULT_COMPANY_ID, fiscal_year: Optional[str] = None,
                limit: int = 50) -> list[dict]:
    sb = get_supabase()
    if sb is None:
        return []
    q = (
        sb.table(_PENDING_TABLE).select("*")
        .eq("company_id", company_id)
        .eq("status", "PENDING")
        .order("posting_amount", desc=True)
        .limit(limit)
    )
    if fiscal_year:
        q = q.eq("fiscal_year", fiscal_year)
    try:
        return q.execute().data or []
    except Exception as e:  # noqa: BLE001
        log.error("get_pending failed: %s", e)
        return []


def get_approved(*, company_id: str = DEFAULT_COMPANY_ID, fiscal_year: Optional[str] = None,
                 limit: int = 200) -> list[dict]:
    sb = get_supabase()
    if sb is None:
        return []
    q = (
        sb.table(_APPROVED_TABLE).select("*")
        .eq("company_id", company_id)
        .order("gl_account")
        .limit(limit)
    )
    if fiscal_year:
        q = q.eq("fiscal_year", fiscal_year)
    try:
        return q.execute().data or []
    except Exception as e:  # noqa: BLE001
        log.error("get_approved failed: %s", e)
        return []


def approve(gl_account: str, *, company_id: str = DEFAULT_COMPANY_ID,
            reviewer: str = "controller",
            override_category: Optional[str] = None,
            override_reason: Optional[str] = None) -> bool:
    sb = get_supabase()
    if sb is None:
        return False
    try:
        pending = (
            sb.table(_PENDING_TABLE).select("*")
            .eq("company_id", company_id)
            .eq("gl_account", gl_account)
            .eq("status", "PENDING")
            .order("drafted_at", desc=True)
            .limit(1)
            .execute()
        ).data
        if not pending:
            return False
        p = pending[0]

        final_cat = override_category or p["tax_category"]
        from gl_intelligence.agents.tax_classifier_agent import (
            CATEGORY_TO_TABLE,
            TAX_CATEGORIES,
            TAX_CATEGORY_LABELS,
        )
        if final_cat not in TAX_CATEGORIES:
            log.warning("approve: invalid override_category %s", final_cat)
            return False

        approved_row = {
            "company_id":         p["company_id"],
            "pending_id":         p["id"],
            "gl_account":         p["gl_account"],
            "description":        p.get("description"),
            "posting_amount":     p["posting_amount"],
            "fiscal_year":        p["fiscal_year"],
            "account_type":       p.get("account_type"),
            "jurisdiction_hint":  p.get("jurisdiction_hint"),
            "tax_category":       final_cat,
            "tax_category_label": TAX_CATEGORY_LABELS.get(final_cat, final_cat),
            "asc_citation":       p.get("asc_citation"),
            "disclosure_table":   CATEGORY_TO_TABLE.get(final_cat, p.get("disclosure_table")),
            "override_reason":    override_reason,
        }
        ins = sb.table(_APPROVED_TABLE).insert(approved_row).execute()
        new_approved_id = ins.data[0]["id"] if ins.data else None

        new_status = "OVERRIDDEN" if override_category else "APPROVED"
        sb.table(_PENDING_TABLE).update({
            "status": new_status,
            "reviewed_at": _now_iso(),
            "reviewed_category": final_cat,
            "override_reason": override_reason,
        }).eq("id", p["id"]).execute()

        write_audit_event(
            module="tax",
            event_type="HUMAN_OVERRIDDEN" if override_category else "HUMAN_APPROVED",
            actor=reviewer,
            actor_type="HUMAN",
            company_id=p["company_id"],
            gl_account=p["gl_account"],
            fiscal_year=p["fiscal_year"],
            pending_id=p["id"],
            approved_id=new_approved_id,
            payload={
                "agent_category": p["tax_category"],
                "final_category": final_cat,
                "override_reason": override_reason,
            },
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.error("approve failed: %s", e)
        return False


def reject(gl_account: str, *, company_id: str = DEFAULT_COMPANY_ID,
           reviewer: str = "controller", reason: str = "") -> bool:
    sb = get_supabase()
    if sb is None:
        return False
    try:
        pending = (
            sb.table(_PENDING_TABLE).select("*")
            .eq("company_id", company_id)
            .eq("gl_account", gl_account)
            .eq("status", "PENDING")
            .order("drafted_at", desc=True)
            .limit(1)
            .execute()
        ).data
        if not pending:
            return False
        p = pending[0]
        sb.table(_PENDING_TABLE).update({
            "status": "REJECTED",
            "reviewed_at": _now_iso(),
            "override_reason": reason,
        }).eq("id", p["id"]).execute()
        write_audit_event(
            module="tax",
            event_type="HUMAN_REJECTED",
            actor=reviewer,
            actor_type="HUMAN",
            company_id=p["company_id"],
            gl_account=p["gl_account"],
            fiscal_year=p["fiscal_year"],
            pending_id=p["id"],
            payload={"reason": reason, "agent_category": p["tax_category"]},
        )
        return True
    except Exception as e:  # noqa: BLE001
        log.error("reject failed: %s", e)
        return False


def list_audit_events(*, company_id: str = DEFAULT_COMPANY_ID,
                      module: Optional[str] = None, limit: int = 200) -> list[dict]:
    sb = get_supabase()
    if sb is None:
        return []
    q = (
        sb.table("audit_log").select("*")
        .eq("company_id", company_id)
        .order("event_timestamp", desc=True)
        .limit(limit)
    )
    if module:
        q = q.eq("module", module)
    try:
        return q.execute().data or []
    except Exception as e:  # noqa: BLE001
        log.error("list_audit_events failed: %s", e)
        return []

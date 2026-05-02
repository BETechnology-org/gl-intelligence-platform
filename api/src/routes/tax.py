"""Tax module routes — review queue + approve/reject + classifier kick-off."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..agents.tax.categories import (
    ASC_CITATIONS,
    CATEGORY_TO_TABLE,
    TAX_CATEGORIES,
    TAX_CATEGORY_LABELS,
)
from ..auth import CurrentUser
from ..db import audit, get_supabase_admin

log = logging.getLogger(__name__)
router = APIRouter()


# ── Read endpoints ────────────────────────────────────────────────────


@router.get("/pending")
async def list_pending(
    user: CurrentUser,
    company_id: str = Query(...),
    fiscal_year: str = Query(...),
    limit: int = Query(default=50, ge=1, le=200),
):
    rows = (
        get_supabase_admin()
        .table("tax_pending_mappings")
        .select("*")
        .eq("company_id", company_id)
        .eq("fiscal_year", fiscal_year)
        .eq("status", "PENDING")
        .order("posting_amount", desc=True)
        .limit(limit)
        .execute()
    ).data
    return {"count": len(rows), "pending": rows}


@router.get("/approved")
async def list_approved(
    user: CurrentUser,
    company_id: str = Query(...),
    fiscal_year: str = Query(...),
):
    rows = (
        get_supabase_admin()
        .table("tax_approved_mappings")
        .select("*")
        .eq("company_id", company_id)
        .eq("fiscal_year", fiscal_year)
        .order("gl_account")
        .execute()
    ).data
    return {"count": len(rows), "approved": rows}


@router.get("/categories")
async def list_categories(user: CurrentUser):
    """Return all 11 ASC 740 categories with labels and citations."""
    return {
        "categories": [
            {
                "key": cat,
                "label": TAX_CATEGORY_LABELS[cat],
                "citation": ASC_CITATIONS[cat],
                "disclosure_table": CATEGORY_TO_TABLE[cat],
            }
            for cat in TAX_CATEGORIES
        ]
    }


# ── Review endpoints ──────────────────────────────────────────────────


class ReviewBody(BaseModel):
    pending_id: str = Field(..., description="UUID of the pending row")
    override_category: str | None = Field(default=None, description="If set, override the agent's suggestion")
    override_reason: str | None = None


@router.post("/approve")
async def approve(body: ReviewBody, user: CurrentUser) -> dict[str, Any]:
    """Approve a pending tax mapping. Optionally override the AI category."""
    supabase = get_supabase_admin()
    pending = (
        supabase.table("tax_pending_mappings")
        .select("*")
        .eq("id", body.pending_id)
        .single()
        .execute()
    ).data
    if not pending:
        raise HTTPException(status_code=404, detail="pending row not found")
    if pending["status"] != "PENDING":
        raise HTTPException(status_code=409, detail=f"row already {pending['status']}")

    # Resolve final category
    final_category = body.override_category or pending["tax_category"]
    if final_category not in TAX_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"invalid category: {final_category}")
    if body.override_category and not body.override_reason:
        raise HTTPException(status_code=400, detail="override_reason required when override_category set")

    # Insert into approved
    approved_row = {
        "id": str(uuid.uuid4()),
        "company_id": pending["company_id"],
        "pending_id": pending["id"],
        "gl_account": pending["gl_account"],
        "description": pending["description"],
        "posting_amount": pending["posting_amount"],
        "fiscal_year": pending["fiscal_year"],
        "account_type": pending.get("account_type"),
        "jurisdiction_hint": pending.get("jurisdiction_hint"),
        "tax_category": final_category,
        "tax_category_label": TAX_CATEGORY_LABELS[final_category],
        "asc_citation": ASC_CITATIONS[final_category],
        "disclosure_table": CATEGORY_TO_TABLE[final_category],
        "override_reason": body.override_reason,
        "reviewer": user.user_id,
    }
    supabase.table("tax_approved_mappings").insert(approved_row).execute()

    # Mark pending row as approved/overridden
    new_status = "OVERRIDDEN" if body.override_category else "APPROVED"
    supabase.table("tax_pending_mappings").update(
        {
            "status": new_status,
            "reviewer": user.user_id,
            "reviewed_at": "now()",
            "reviewed_category": final_category,
            "override_reason": body.override_reason,
        }
    ).eq("id", body.pending_id).execute()

    # Audit
    await audit.write(
        company_id=pending["company_id"],
        module="tax",
        event_type="HUMAN_APPROVED" if not body.override_category else "HUMAN_OVERRIDDEN",
        actor=user.user_id,
        actor_type="HUMAN",
        user_id=user.user_id,
        gl_account=pending["gl_account"],
        fiscal_year=pending["fiscal_year"],
        pending_id=pending["id"],
        approved_id=approved_row["id"],
        payload={
            "agent_category": pending["tax_category"],
            "final_category": final_category,
            "override_reason": body.override_reason,
        },
    )

    return {
        "ok": True,
        "approved_id": approved_row["id"],
        "status": new_status,
        "tax_category": final_category,
    }


class RejectBody(BaseModel):
    pending_id: str
    reason: str = Field(..., min_length=1, max_length=2000)


@router.post("/reject")
async def reject(body: RejectBody, user: CurrentUser) -> dict[str, Any]:
    """Reject a pending tax mapping."""
    supabase = get_supabase_admin()
    pending = (
        supabase.table("tax_pending_mappings")
        .select("*")
        .eq("id", body.pending_id)
        .single()
        .execute()
    ).data
    if not pending:
        raise HTTPException(status_code=404, detail="pending row not found")
    if pending["status"] != "PENDING":
        raise HTTPException(status_code=409, detail=f"row already {pending['status']}")

    supabase.table("tax_pending_mappings").update(
        {
            "status": "REJECTED",
            "reviewer": user.user_id,
            "reviewed_at": "now()",
            "override_reason": body.reason,
        }
    ).eq("id", body.pending_id).execute()

    await audit.write(
        company_id=pending["company_id"],
        module="tax",
        event_type="HUMAN_REJECTED",
        actor=user.user_id,
        actor_type="HUMAN",
        user_id=user.user_id,
        gl_account=pending["gl_account"],
        fiscal_year=pending["fiscal_year"],
        pending_id=pending["id"],
        payload={"reason": body.reason, "agent_category": pending["tax_category"]},
    )
    return {"ok": True, "status": "REJECTED"}


# ── Classifier kick-off ───────────────────────────────────────────────


class ClassifyBody(BaseModel):
    company_id: str
    fiscal_year: str
    company_code: str = Field(default="C006")
    batch_size: int = Field(default=18, ge=1, le=50)
    job_id: str | None = None


@router.post("/classify")
async def kick_off_classify(body: ClassifyBody, user: CurrentUser) -> dict[str, Any]:
    """Create a job_id for a classifier run. Client then opens SSE at
    `POST /api/sessions/{job_id}/stream` with body
    `{"agent_type": "tax_classifier", "prompt": "..."}` to drive the run."""
    job_id = body.job_id or str(uuid.uuid4())
    prompt = (
        f"Classify the next batch of unmapped tax GL accounts for "
        f"fiscal_year={body.fiscal_year}. Use batch_size={body.batch_size}. "
        f"For each account: lookup similar approved mappings, lookup the canonical "
        f"ASC citation for your chosen category, then write a pending mapping. "
        f"Stop after the batch and summarize what you classified."
    )
    return {
        "job_id": job_id,
        "agent_type": "tax_classifier",
        "prompt": prompt,
        "stream_url": f"/api/sessions/{job_id}/stream",
    }

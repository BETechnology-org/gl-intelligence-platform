"""DISE (ASU 2024-03) routes — Phase 3 placeholder.

Active routes will be added when the DISE module is built out.
For now, only the read-side queries against Supabase are exposed so
the Phase 1 dashboard can show DISE state alongside Tax.
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..auth import CurrentUser
from ..db import get_supabase_admin

router = APIRouter()


@router.get("/pending")
async def list_pending(user: CurrentUser, company_id: str = Query(...), fiscal_year: str = Query(...)):
    supabase = get_supabase_admin()
    rows = (
        supabase.table("dise_pending_mappings")
        .select("*")
        .eq("company_id", company_id)
        .eq("fiscal_year", fiscal_year)
        .eq("status", "PENDING")
        .order("posting_amount", desc=True)
        .execute()
    ).data
    return {"count": len(rows), "pending": rows}


@router.get("/approved")
async def list_approved(user: CurrentUser, company_id: str = Query(...), fiscal_year: str = Query(...)):
    supabase = get_supabase_admin()
    rows = (
        supabase.table("dise_approved_mappings")
        .select("*")
        .eq("company_id", company_id)
        .eq("fiscal_year", fiscal_year)
        .order("gl_account")
        .execute()
    ).data
    return {"count": len(rows), "approved": rows}


@router.get("/anomalies")
async def list_anomalies(
    user: CurrentUser,
    company_id: str = Query(...),
    fiscal_year: str = Query(...),
    status: str = Query(default="open"),
):
    supabase = get_supabase_admin()
    rows = (
        supabase.table("dise_anomaly_alerts")
        .select("*")
        .eq("company_id", company_id)
        .eq("fiscal_year", fiscal_year)
        .eq("status", status)
        .order("priority")
        .order("detected_at", desc=True)
        .execute()
    ).data
    return {"count": len(rows), "alerts": rows}

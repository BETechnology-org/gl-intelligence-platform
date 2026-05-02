"""Cortex (BigQuery) routes — ported from gl_intelligence/api/server.py.

Read-only endpoints over the Cortex SAP / Oracle EBS / Salesforce datasets.
All gated on a valid Supabase JWT (so a leaked anon key can't query GL data
without an authenticated session).
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from ..auth import CurrentUser
from ..config import settings
from ..db.cortex import get_cortex

router = APIRouter()


# ── SAP ────────────────────────────────────────────────────────────────
@router.get("/sap/gl-accounts")
async def sap_gl_accounts(
    user: CurrentUser,
    fiscal_year: str = Query(default="2023"),
    company_code: str = Query(default="C006"),
):
    cx = get_cortex()
    sql = f"""
    SELECT
      b.HKONT AS gl_account,
      a.BKTXT AS description,
      SUM(b.WRBTR) AS posting_amount,
      a.GJAHR AS fiscal_year,
      a.BUKRS AS company_code
    FROM `{cx.data_project}.{settings.bq_sap_cdc_dataset}.bkpf` a
    JOIN `{cx.data_project}.{settings.bq_sap_cdc_dataset}.bseg` b
      ON a.MANDT = b.MANDT AND a.BUKRS = b.BUKRS
      AND a.BELNR = b.BELNR AND a.GJAHR = b.GJAHR
    WHERE a.BUKRS = @company_code AND a.GJAHR = @fiscal_year
    GROUP BY b.HKONT, a.BKTXT, a.GJAHR, a.BUKRS
    ORDER BY ABS(SUM(b.WRBTR)) DESC
    """
    accounts = cx.query(sql, [
        cx.param("company_code", "STRING", company_code),
        cx.param("fiscal_year", "STRING", fiscal_year),
    ])
    return {"count": len(accounts), "accounts": accounts}


@router.get("/sap/trial-balance")
async def sap_trial_balance(
    user: CurrentUser,
    fiscal_year: str = Query(default="2023"),
    company_code: str = Query(default="C006"),
):
    cx = get_cortex()
    sql = f"""
    SELECT b.HKONT AS gl_account,
           SUM(b.WRBTR) AS balance,
           a.GJAHR AS fiscal_year
    FROM `{cx.data_project}.{settings.bq_sap_cdc_dataset}.bkpf` a
    JOIN `{cx.data_project}.{settings.bq_sap_cdc_dataset}.bseg` b
      ON a.MANDT = b.MANDT AND a.BUKRS = b.BUKRS
      AND a.BELNR = b.BELNR AND a.GJAHR = b.GJAHR
    WHERE a.BUKRS = @company_code AND a.GJAHR = @fiscal_year
    GROUP BY b.HKONT, a.GJAHR
    ORDER BY ABS(SUM(b.WRBTR)) DESC
    LIMIT 200
    """
    rows = cx.query(sql, [
        cx.param("company_code", "STRING", company_code),
        cx.param("fiscal_year", "STRING", fiscal_year),
    ])
    return {"count": len(rows), "data": rows}


# ── Oracle EBS ─────────────────────────────────────────────────────────
@router.get("/oracle/chart-of-accounts")
async def oracle_coa(user: CurrentUser):
    cx = get_cortex()
    sql = f"""
    SELECT *
    FROM `{cx.data_project}.{settings.bq_oracle_cdc_dataset}.gl_code_combinations`
    LIMIT 500
    """
    rows = cx.query(sql)
    return {"count": len(rows), "data": rows}


# ── Salesforce ─────────────────────────────────────────────────────────
@router.get("/sfdc/accounts")
async def sfdc_accounts(user: CurrentUser):
    cx = get_cortex()
    sql = f"""
    SELECT * FROM `{cx.data_project}.{settings.bq_sfdc_cdc_dataset}.account` LIMIT 100
    """
    rows = cx.query(sql)
    return {"count": len(rows), "data": rows}

"""
SAP ECC / S/4HANA Connector via Cortex CDC.
Reads from CORTEX_SAP_CDC tables: bkpf, bseg, ska1, skat, anla, anlc, cepc, t001, etc.
"""

from __future__ import annotations

import logging
from typing import Optional

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient

log = logging.getLogger("cortex.sap")


class SAPConnector:
    """
    High-level access to SAP financial data replicated via Cortex CDC into BigQuery.
    Abstracts the raw SAP table joins into business-meaningful queries.
    """

    def __init__(self, client: CortexClient | None = None):
        self.cx = client or CortexClient()
        self.cdc = cfg.SAP_CDC_DATASET
        self.dise = cfg.DISE_DATASET
        self.p = cfg.PROJECT

    # ── GL Account Master ───────────────────────────────────

    def get_gl_accounts(self, company_code: str | None = None,
                        fiscal_year: str | None = None,
                        exclude_balance_sheet: bool = True) -> list[dict]:
        """
        Returns all P&L GL accounts with descriptions and posting totals.
        Joins bkpf (doc header) → bseg (line items) → ska1 (account master) → skat (texts).
        """
        cc = company_code or cfg.COMPANY_CODE
        fy = fiscal_year or cfg.FISCAL_YEAR

        sql = f"""
        SELECT
          bseg.HKONT                                       AS gl_account,
          COALESCE(skat.TXT50, skat.TXT20, bseg.HKONT)   AS description,
          ROUND(SUM(bseg.DMBTR), 0)                        AS posting_amount
        FROM `{self.p}.{self.cdc}.bkpf` bkpf
        JOIN `{self.p}.{self.cdc}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        JOIN `{self.p}.{self.cdc}.ska1` ska1
          ON  bseg.HKONT = ska1.SAKNR AND bseg.MANDT = ska1.MANDT
          AND ska1.ktopl = @chart_of_accounts
        LEFT JOIN `{self.p}.{self.cdc}.skat` skat
          ON  bseg.HKONT = skat.SAKNR AND bseg.MANDT = skat.MANDT
          AND skat.ktopl = @chart_of_accounts AND skat.SPRAS = 'E'
        WHERE bkpf.GJAHR = @fiscal_year
          AND bkpf.BUKRS = @company_code
          AND bkpf.BLART NOT IN ('AA', 'AF', 'AB')
          {"AND (ska1.xbilk = '' OR ska1.xbilk IS NULL)" if exclude_balance_sheet else ""}
        GROUP BY 1, 2
        HAVING SUM(bseg.DMBTR) > 0
        ORDER BY posting_amount DESC
        """
        return self.cx.query(sql, [
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("company_code", "STRING", cc),
            self.cx.param("chart_of_accounts", "STRING", cfg.CHART_OF_ACCOUNTS),
        ])

    def get_unmapped_accounts(self, company_code: str | None = None,
                              fiscal_year: str | None = None) -> list[dict]:
        """
        Returns P&L accounts with postings that are NOT yet in gl_dise_mapping
        and NOT already in pending_mappings.
        """
        cc = company_code or cfg.COMPANY_CODE
        fy = fiscal_year or cfg.FISCAL_YEAR

        sql = f"""
        SELECT
          bseg.HKONT                                       AS gl_account,
          COALESCE(skat.TXT50, skat.TXT20, bseg.HKONT)   AS description,
          ROUND(SUM(bseg.DMBTR), 0)                        AS posting_amount
        FROM `{self.p}.{self.cdc}.bkpf` bkpf
        JOIN `{self.p}.{self.cdc}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        JOIN `{self.p}.{self.cdc}.ska1` ska1
          ON  bseg.HKONT = ska1.SAKNR AND bseg.MANDT = ska1.MANDT
          AND ska1.ktopl = @chart_of_accounts
        LEFT JOIN `{self.p}.{self.cdc}.skat` skat
          ON  bseg.HKONT = skat.SAKNR AND bseg.MANDT = skat.MANDT
          AND skat.ktopl = @chart_of_accounts AND skat.SPRAS = 'E'
        LEFT JOIN `{self.p}.{self.dise}.gl_dise_mapping` m
          ON  bseg.HKONT = m.gl_account
        LEFT JOIN `{self.p}.{self.dise}.pending_mappings` p
          ON  bseg.HKONT = p.gl_account AND p.fiscal_year = @fiscal_year
          AND p.status IN ('PENDING', 'APPROVED')
        WHERE bkpf.GJAHR   = @fiscal_year
          AND bkpf.BUKRS   = @company_code
          AND bkpf.BLART   NOT IN ('AA', 'AF', 'AB')
          AND (ska1.xbilk = '' OR ska1.xbilk IS NULL)
          AND m.gl_account IS NULL
          AND p.gl_account IS NULL
        GROUP BY 1, 2
        HAVING SUM(bseg.DMBTR) > 0
        ORDER BY posting_amount DESC
        """
        return self.cx.query(sql, [
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("company_code", "STRING", cc),
            self.cx.param("chart_of_accounts", "STRING", cfg.CHART_OF_ACCOUNTS),
        ])

    # ── Journal Entry Detail ────────────────────────────────

    def get_journal_entries(self, gl_account: str, fiscal_year: str | None = None,
                           company_code: str | None = None, limit: int = 100) -> list[dict]:
        """Returns individual journal entry lines for a GL account — the 'Link 1' of the audit trail."""
        fy = fiscal_year or cfg.FISCAL_YEAR
        cc = company_code or cfg.COMPANY_CODE

        sql = f"""
        SELECT
          bkpf.BELNR AS document_number,
          bkpf.BLDAT AS document_date,
          bkpf.BUDAT AS posting_date,
          bkpf.BLART AS document_type,
          bseg.HKONT AS gl_account,
          bseg.DMBTR AS amount_lc,
          bseg.WRBTR AS amount_dc,
          bseg.SHKZG AS debit_credit,
          bseg.SGTXT AS item_text,
          bseg.KOSTL AS cost_center
        FROM `{self.p}.{self.cdc}.bkpf` bkpf
        JOIN `{self.p}.{self.cdc}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        WHERE bseg.HKONT = @gl_account
          AND bkpf.GJAHR = @fiscal_year
          AND bkpf.BUKRS = @company_code
        ORDER BY bkpf.BUDAT DESC, bkpf.BELNR
        LIMIT @limit
        """
        return self.cx.query(sql, [
            self.cx.param("gl_account", "STRING", gl_account),
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("company_code", "STRING", cc),
            self.cx.param("limit", "INT64", limit),
        ])

    # ── Aggregates for Reconciliation ───────────────────────

    def get_trial_balance(self, fiscal_year: str | None = None,
                          company_code: str | None = None) -> list[dict]:
        """Returns GL trial balance — all accounts with debit/credit totals."""
        fy = fiscal_year or cfg.FISCAL_YEAR
        cc = company_code or cfg.COMPANY_CODE

        sql = f"""
        SELECT
          bseg.HKONT AS gl_account,
          COALESCE(skat.TXT50, bseg.HKONT) AS description,
          SUM(CASE WHEN bseg.SHKZG = 'S' THEN bseg.DMBTR ELSE 0 END) AS debit_total,
          SUM(CASE WHEN bseg.SHKZG = 'H' THEN bseg.DMBTR ELSE 0 END) AS credit_total,
          SUM(bseg.DMBTR) AS net_amount,
          COUNT(*) AS line_count
        FROM `{self.p}.{self.cdc}.bkpf` bkpf
        JOIN `{self.p}.{self.cdc}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        LEFT JOIN `{self.p}.{self.cdc}.skat` skat
          ON  bseg.HKONT = skat.SAKNR AND bseg.MANDT = skat.MANDT
          AND skat.SPRAS = 'E'
        WHERE bkpf.GJAHR = @fiscal_year AND bkpf.BUKRS = @company_code
          AND bkpf.BLART NOT IN ('AA', 'AF', 'AB')
        GROUP BY 1, 2
        ORDER BY net_amount DESC
        """
        return self.cx.query(sql, [
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("company_code", "STRING", cc),
        ])

    def get_yoy_comparison(self, fiscal_year: str | None = None,
                           company_code: str | None = None) -> list[dict]:
        """Returns current vs prior year amounts by GL account for anomaly detection."""
        fy = fiscal_year or cfg.FISCAL_YEAR
        prior_fy = str(int(fy) - 1)
        cc = company_code or cfg.COMPANY_CODE

        sql = f"""
        SELECT
          bseg.HKONT AS gl_account,
          COALESCE(skat.TXT50, bseg.HKONT) AS description,
          ROUND(SUM(CASE WHEN bkpf.GJAHR = @fiscal_year  THEN bseg.DMBTR ELSE 0 END), 0) AS current_year,
          ROUND(SUM(CASE WHEN bkpf.GJAHR = @prior_year   THEN bseg.DMBTR ELSE 0 END), 0) AS prior_year
        FROM `{self.p}.{self.cdc}.bkpf` bkpf
        JOIN `{self.p}.{self.cdc}.bseg` bseg
          ON  bkpf.MANDT = bseg.MANDT AND bkpf.BUKRS = bseg.BUKRS
          AND bkpf.BELNR = bseg.BELNR AND bkpf.GJAHR = bseg.GJAHR
        LEFT JOIN `{self.p}.{self.cdc}.skat` skat
          ON  bseg.HKONT = skat.SAKNR AND bseg.MANDT = skat.MANDT
          AND skat.SPRAS = 'E'
        WHERE bkpf.GJAHR IN (@fiscal_year, @prior_year)
          AND bkpf.BUKRS = @company_code
          AND bkpf.BLART NOT IN ('AA', 'AF', 'AB')
        GROUP BY 1, 2
        HAVING SUM(bseg.DMBTR) > 0
        ORDER BY current_year DESC
        """
        return self.cx.query(sql, [
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("prior_year", "STRING", prior_fy),
            self.cx.param("company_code", "STRING", cc),
        ])

    # ── Fixed Assets (for Depreciation/Amortization) ────────

    def get_asset_depreciation(self, fiscal_year: str | None = None,
                               company_code: str | None = None) -> list[dict]:
        """Returns asset depreciation amounts from ANLA/ANLC tables."""
        fy = fiscal_year or cfg.FISCAL_YEAR
        cc = company_code or cfg.COMPANY_CODE

        sql = f"""
        SELECT
          anla.ANLN1 AS asset_number,
          anla.ANLN2 AS sub_number,
          ankt.TXA50 AS asset_description,
          anla.ANLKL AS asset_class,
          anlc.NAFAB AS depreciation_amount,
          anlc.GJAHR AS fiscal_year
        FROM `{self.p}.{self.cdc}.anla` anla
        JOIN `{self.p}.{self.cdc}.anlc` anlc
          ON  anla.MANDT = anlc.MANDT AND anla.BUKRS = anlc.BUKRS
          AND anla.ANLN1 = anlc.ANLN1 AND anla.ANLN2 = anlc.ANLN2
        LEFT JOIN `{self.p}.{self.cdc}.ankt` ankt
          ON  anla.MANDT = ankt.MANDT AND anla.ANLKL = ankt.ANLKL
          AND ankt.SPRAS = 'E'
        WHERE anla.BUKRS = @company_code AND anlc.GJAHR = @fiscal_year
        ORDER BY anlc.NAFAB DESC
        """
        return self.cx.query(sql, [
            self.cx.param("fiscal_year", "STRING", fy),
            self.cx.param("company_code", "STRING", cc),
        ])

    # ── Company Code Master ─────────────────────────────────

    def get_company_codes(self) -> list[dict]:
        """Returns all company codes from T001."""
        sql = f"""
        SELECT DISTINCT BUKRS AS company_code, BUTXT AS company_name
        FROM `{self.p}.{self.cdc}.t001`
        ORDER BY BUKRS
        """
        return self.cx.query(sql)

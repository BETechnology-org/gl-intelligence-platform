"""
Oracle EBS Connector via Cortex CDC.
Reads from CORTEX_ORACLE_EBS_CDC: GL_CODE_COMBINATIONS, GL_BALANCING_SEG,
GL_ACCOUNT_SEG, GL_LEDGERS, and CORTEX_ORACLE_EBS_REPORTING views.
"""

from __future__ import annotations

import logging

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient

log = logging.getLogger("cortex.oracle")


class OracleEBSConnector:
    """
    High-level access to Oracle EBS financial data via Cortex CDC in BigQuery.
    """

    def __init__(self, client: CortexClient | None = None):
        self.cx = client or CortexClient()
        self.cdc = cfg.ORACLE_CDC_DATASET
        self.rpt = cfg.ORACLE_REPORTING
        self.p = cfg.PROJECT

    def get_chart_of_accounts(self) -> list[dict]:
        """Returns Oracle GL code combinations (chart of accounts)."""
        sql = f"""
        SELECT
          cc.CODE_COMBINATION_ID,
          cc.SEGMENT1 AS company,
          cc.SEGMENT3 AS account_code,
          cc.SEGMENT6 AS cost_center,
          cc.ACCOUNT_TYPE,
          cc.ENABLED_FLAG,
          cc.DESCRIPTION
        FROM `{self.p}.{self.cdc}.GL_CODE_COMBINATIONS` cc
        WHERE cc.ENABLED_FLAG = 'Y'
        ORDER BY cc.SEGMENT3
        """
        return self.cx.query(sql)

    def get_account_segments(self) -> list[dict]:
        """Returns Oracle GL account segment values and descriptions."""
        sql = f"""
        SELECT *
        FROM `{self.p}.{self.cdc}.GL_ACCOUNT_SEG`
        ORDER BY 1
        """
        return self.cx.query(sql)

    def get_ledgers(self) -> list[dict]:
        """Returns Oracle GL ledgers."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.cdc}.GL_LEDGERS`
        """
        return self.cx.query(sql)

    def get_invoices(self, limit: int = 100) -> list[dict]:
        """Returns invoice headers from Oracle EBS reporting views."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.rpt}.InvoiceHeaders`
        ORDER BY 1 DESC
        LIMIT @limit
        """
        return self.cx.query(sql, [self.cx.param("limit", "INT64", limit)])

    def get_invoice_lines_with_gl(self, limit: int = 100) -> list[dict]:
        """Returns invoice lines with GL distribution for expense analysis."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.rpt}.InvoiceLineLedger`
        LIMIT @limit
        """
        return self.cx.query(sql, [self.cx.param("limit", "INT64", limit)])

    def get_payments(self, limit: int = 100) -> list[dict]:
        """Returns payments from Oracle EBS."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.rpt}.Payments`
        LIMIT @limit
        """
        return self.cx.query(sql, [self.cx.param("limit", "INT64", limit)])

    def get_orders(self, limit: int = 100) -> list[dict]:
        """Returns sales orders from Oracle EBS."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.rpt}.SalesOrders`
        LIMIT @limit
        """
        return self.cx.query(sql, [self.cx.param("limit", "INT64", limit)])

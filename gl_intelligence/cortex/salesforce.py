"""
Salesforce Connector via Cortex CDC.
Reads from CORTEX_SFDC_CDC and CORTEX_SFDC_REPORTING.
"""

from __future__ import annotations

import logging

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient

log = logging.getLogger("cortex.salesforce")


class SalesforceConnector:
    """
    High-level access to Salesforce data via Cortex CDC in BigQuery.
    Primarily used for revenue data cross-referencing in reconciliation.
    """

    def __init__(self, client: CortexClient | None = None):
        self.cx = client or CortexClient()
        self.cdc = cfg.SFDC_CDC_DATASET
        self.p = cfg.PROJECT

    def get_accounts(self, limit: int = 100) -> list[dict]:
        """Returns Salesforce accounts."""
        sql = f"""
        SELECT * FROM `{self.p}.{self.cdc}.accounts`
        LIMIT @limit
        """
        return self.cx.query(sql, [self.cx.param("limit", "INT64", limit)])

    def get_available_tables(self) -> list[str]:
        """Returns list of available SFDC CDC tables."""
        return self.cx.list_tables(self.cdc)

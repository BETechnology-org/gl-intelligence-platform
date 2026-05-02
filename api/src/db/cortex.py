"""BigQuery client wrapper — ported from gl_intelligence/cortex/client.py.

Cortex datasets (read-only from this app):
  - CORTEX_SAP_CDC / CORTEX_SAP_REPORTING
  - CORTEX_ORACLE_EBS_CDC / CORTEX_ORACLE_EBS_REPORTING
  - CORTEX_SFDC_CDC

Application datasets:
  - dise_reporting (mirrors of approved mappings + analytical views)
"""

from __future__ import annotations

import decimal
import logging
from functools import lru_cache
from typing import Any

from google.cloud import bigquery

from ..config import settings

log = logging.getLogger(__name__)


class CortexClient:
    """Thin wrapper around BigQuery, scoped to Cortex datasets."""

    def __init__(self) -> None:
        self.data_project = settings.bq_data_project
        self.billing_project = settings.bq_billing_project
        self._bq: bigquery.Client | None = None
        log.info(
            "CortexClient: data=%s billing=%s dataset=%s",
            self.data_project, self.billing_project, settings.bq_dataset,
        )

    @property
    def bq(self) -> bigquery.Client:
        if self._bq is None:
            self._bq = bigquery.Client(project=self.billing_project)
        return self._bq

    @property
    def available(self) -> bool:
        try:
            _ = self.bq
            return True
        except Exception:
            return False

    def query(self, sql: str, params: list | None = None, timeout: float = 120) -> list[dict]:
        job_config = None
        if params:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = self.bq.query(sql, job_config=job_config).result(timeout=timeout)
        out = []
        for r in rows:
            d = dict(r)
            for k, v in d.items():
                if isinstance(v, decimal.Decimal):
                    d[k] = float(v)
            out.append(d)
        return out

    def query_single(self, sql: str, params: list | None = None) -> dict | None:
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def insert_rows(self, table_ref: str, rows: list[dict]) -> list:
        return self.bq.insert_rows_json(table_ref, rows)

    def table_ref(self, dataset: str, table: str) -> str:
        return f"`{self.data_project}.{dataset}.{table}`"

    def param(self, name: str, type: str, value: Any) -> bigquery.ScalarQueryParameter:
        return bigquery.ScalarQueryParameter(name, type, value)


@lru_cache(maxsize=1)
def get_cortex() -> CortexClient:
    return CortexClient()

"""
BigQuery client wrapper with Cortex-aware dataset routing.
All ERP connectors use this as their data access layer.
"""

from __future__ import annotations

import logging
from typing import Any

from google.cloud import bigquery

from gl_intelligence.config import cfg

log = logging.getLogger("cortex.client")


class CortexClient:
    """
    Thin wrapper around BigQuery that knows about Cortex dataset layout.
    Provides parameterized queries, schema introspection, and connection pooling.
    """

    def __init__(self, project: str | None = None):
        self.project = project or cfg.PROJECT
        self._bq = bigquery.Client(project=self.project)
        log.info(f"CortexClient initialized — project={self.project}")

    @property
    def bq(self) -> bigquery.Client:
        return self._bq

    def query(self, sql: str, params: list | None = None, timeout: float = 120) -> list[dict]:
        """Execute a parameterized query and return rows as dicts with JSON-safe types."""
        import decimal
        job_config = None
        if params:
            job_config = bigquery.QueryJobConfig(query_parameters=params)
        rows = self._bq.query(sql, job_config=job_config).result(timeout=timeout)
        results = []
        for r in rows:
            d = dict(r)
            # Convert Decimal to float for JSON serialization
            for k, v in d.items():
                if isinstance(v, decimal.Decimal):
                    d[k] = float(v)
            results.append(d)
        return results

    def query_single(self, sql: str, params: list | None = None) -> dict | None:
        """Execute query expecting a single row. Returns None if empty."""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def insert_rows(self, table_ref: str, rows: list[dict]) -> list:
        """Insert rows via streaming API. Returns list of errors (empty = success)."""
        return self._bq.insert_rows_json(table_ref, rows)

    def table_ref(self, dataset: str, table: str) -> str:
        """Build fully-qualified table reference."""
        return f"`{self.project}.{dataset}.{table}`"

    def list_tables(self, dataset: str) -> list[str]:
        """List all table names in a dataset."""
        return [t.table_id for t in self._bq.list_tables(dataset)]

    def get_schema(self, dataset: str, table: str) -> list[dict]:
        """Get column names and types for a table."""
        ref = self._bq.get_table(f"{self.project}.{dataset}.{table}")
        return [{"name": f.name, "type": f.field_type, "mode": f.mode} for f in ref.schema]

    def param(self, name: str, type: str, value: Any) -> bigquery.ScalarQueryParameter:
        """Shortcut for creating a query parameter."""
        return bigquery.ScalarQueryParameter(name, type, value)

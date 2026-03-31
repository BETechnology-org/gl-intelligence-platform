"""Centralized configuration for the GL Intelligence Platform."""

from __future__ import annotations
import os


class Config:
    """All configuration loaded from environment variables with sensible defaults."""

    # GCP / BigQuery
    PROJECT: str           = os.environ.get("GOOGLE_CLOUD_PROJECT", "diplomatic75")
    REGION: str            = os.environ.get("GCP_REGION", "us-central1")

    # Cortex datasets
    SAP_CDC_DATASET: str   = os.environ.get("BQ_SAP_CDC_DATASET", "CORTEX_SAP_CDC")
    SAP_REPORTING: str     = os.environ.get("BQ_SAP_REPORTING",   "CORTEX_SAP_REPORTING")
    ORACLE_CDC_DATASET: str= os.environ.get("BQ_ORACLE_CDC_DATASET", "CORTEX_ORACLE_EBS_CDC")
    ORACLE_REPORTING: str  = os.environ.get("BQ_ORACLE_REPORTING",   "CORTEX_ORACLE_EBS_REPORTING")
    SFDC_CDC_DATASET: str  = os.environ.get("BQ_SFDC_CDC_DATASET",   "CORTEX_SFDC_CDC")

    # DISE / application dataset
    DISE_DATASET: str      = os.environ.get("BQ_DATASET", "dise_reporting")

    # Company context
    COMPANY_CODE: str      = os.environ.get("COMPANY_CODE", "C006")
    FISCAL_YEAR: str       = os.environ.get("FISCAL_YEAR", "2023")
    CHART_OF_ACCOUNTS: str = os.environ.get("CHART_OF_ACCOUNTS", "CA01")

    # Claude / AI
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str      = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    API_DELAY: float       = float(os.environ.get("API_DELAY_SECONDS", "0.3"))
    MAX_RETRIES: int       = int(os.environ.get("MAX_RETRIES", "2"))

    # Server
    PORT: int              = int(os.environ.get("PORT", "8080"))
    HOST: str              = os.environ.get("HOST", "0.0.0.0")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required config items."""
        issues = []
        if not cls.ANTHROPIC_API_KEY:
            issues.append("ANTHROPIC_API_KEY not set")
        return issues

    @classmethod
    def summary(cls) -> dict:
        return {
            "project": cls.PROJECT,
            "sap_cdc": cls.SAP_CDC_DATASET,
            "oracle_cdc": cls.ORACLE_CDC_DATASET,
            "sfdc_cdc": cls.SFDC_CDC_DATASET,
            "dise_dataset": cls.DISE_DATASET,
            "company_code": cls.COMPANY_CODE,
            "fiscal_year": cls.FISCAL_YEAR,
            "model": cls.CLAUDE_MODEL,
        }


cfg = Config()

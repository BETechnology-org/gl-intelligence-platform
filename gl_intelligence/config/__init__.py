"""Centralized configuration for the GL Intelligence Platform."""

from __future__ import annotations
import os

# Load .env file if present (before class definition so env vars are set)
def _load_dotenv():
    import pathlib
    env_path = pathlib.Path(__file__).parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_dotenv()


class Config:
    """All configuration loaded from environment variables with sensible defaults."""

    # GCP / BigQuery
    # BQ_BILLING_PROJECT: the GCP project that pays for query jobs (= Cloud Run project)
    BILLING_PROJECT: str   = os.environ.get("GOOGLE_CLOUD_PROJECT", "trufflesai-loans")
    # PROJECT: the GCP project where the actual BigQuery datasets live
    PROJECT: str           = os.environ.get("BQ_DATA_PROJECT", "diplomatic75")
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

    # Claude / AI — direct Anthropic API key (optional if using Bedrock)
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str      = os.environ.get("CLAUDE_MODEL", "anthropic.claude-sonnet-4-6")
    API_DELAY: float       = float(os.environ.get("API_DELAY_SECONDS", "0.3"))
    MAX_RETRIES: int       = int(os.environ.get("MAX_RETRIES", "2"))

    # AWS Bedrock
    AWS_ACCESS_KEY_ID: str     = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_BEDROCK_REGION: str    = os.environ.get("AWS_BEDROCK_REGION", "ap-south-1")

    @classmethod
    def use_bedrock(cls) -> bool:
        """True when AWS Bedrock credentials are configured."""
        return bool(cls.AWS_ACCESS_KEY_ID and cls.AWS_SECRET_ACCESS_KEY)

    # Server
    PORT: int              = int(os.environ.get("PORT", "8080"))
    HOST: str              = os.environ.get("HOST", "0.0.0.0")

    @classmethod
    def validate(cls) -> list[str]:
        """Return list of missing required config items."""
        issues = []
        if not cls.use_bedrock() and not cls.ANTHROPIC_API_KEY:
            issues.append("No AI credentials: set AWS_ACCESS_KEY_ID+AWS_SECRET_ACCESS_KEY (Bedrock) or ANTHROPIC_API_KEY")
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

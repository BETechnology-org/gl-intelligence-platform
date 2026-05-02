"""Centralized configuration loaded from env vars."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _load_dotenv() -> None:
    """Load .env from project root (BE Tech/.env) before settings are read."""
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── Service ────────────────────────────────────────────────
    environment: str = Field(default="development", alias="ENVIRONMENT")
    port: int = Field(default=8001, alias="PORT")
    host: str = Field(default="0.0.0.0", alias="HOST")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    app_version: str = Field(default="0.1.0", alias="APP_VERSION")

    # ── CORS ───────────────────────────────────────────────────
    cors_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ALLOWED_ORIGINS",
    )

    # ── Supabase ───────────────────────────────────────────────
    supabase_url: str = Field(alias="SUPABASE_URL")
    supabase_anon_key: str | None = Field(default=None, alias="SUPABASE_ANON_KEY")
    supabase_service_role_key: str = Field(alias="SUPABASE_SERVICE_ROLE_KEY")
    # JWT verification — Supabase signs tokens with this secret.
    supabase_jwt_secret: str = Field(alias="SUPABASE_JWT_SECRET")

    # ── BigQuery (Cortex) ──────────────────────────────────────
    bq_billing_project: str = Field(default="trufflesai-loans", alias="BQ_BILLING_PROJECT")
    bq_data_project: str = Field(default="diplomatic75", alias="BQ_DATA_PROJECT")
    bq_dataset: str = Field(default="dise_reporting", alias="BQ_DATASET")
    bq_sap_cdc_dataset: str = Field(default="CORTEX_SAP_CDC", alias="BQ_SAP_CDC_DATASET")
    bq_oracle_cdc_dataset: str = Field(
        default="CORTEX_ORACLE_EBS_CDC", alias="BQ_ORACLE_CDC_DATASET"
    )
    bq_sfdc_cdc_dataset: str = Field(default="CORTEX_SFDC_CDC", alias="BQ_SFDC_CDC_DATASET")

    # ── Claude / Anthropic ─────────────────────────────────────
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    claude_model: str = Field(
        default="claude-sonnet-4-6",
        alias="CLAUDE_MODEL",
    )
    claude_max_turns: int = Field(default=50, alias="CLAUDE_MAX_TURNS")
    claude_extended_thinking: bool = Field(default=False, alias="CLAUDE_EXTENDED_THINKING")

    # ── AWS Bedrock (optional) ─────────────────────────────────
    aws_access_key_id: str | None = Field(default=None, alias="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str | None = Field(default=None, alias="AWS_SECRET_ACCESS_KEY")
    aws_bedrock_region: str = Field(default="us-east-1", alias="AWS_BEDROCK_REGION")

    # ── Rate limiting ──────────────────────────────────────────
    rate_limit_per_minute: int = Field(default=120, alias="RATE_LIMIT_PER_MINUTE")
    max_json_bytes: int = Field(default=1_048_576, alias="MAX_JSON_BYTES")

    # ── Sessions ───────────────────────────────────────────────
    sessions_root_dir: str = Field(default="/tmp/bl_sessions", alias="SESSIONS_ROOT_DIR")
    session_idle_timeout_seconds: int = Field(
        default=3600, alias="SESSION_IDLE_TIMEOUT_SECONDS"
    )

    @property
    def is_prod(self) -> bool:
        return self.environment.lower() in ("production", "prod")

    @property
    def use_bedrock(self) -> bool:
        return bool(self.aws_access_key_id and self.aws_secret_access_key)

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


settings = get_settings()

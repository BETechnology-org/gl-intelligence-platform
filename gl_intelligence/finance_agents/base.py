"""BaseFinanceAgent — the standard contract every GL Intelligence agent obeys.

Spec source: GL_Agent_Contract_Templates.docx (April 2026).

Standard input contract:
  company_code  (str, required)
  fiscal_year   (str, required)
  fiscal_period (str, default 'Full Year')
  run_id        (auto-generated as `{module}-{fiscal_year}-{sequence}`)
  dry_run       (bool, default False)

Standard output columns (every agent's output table must have these):
  run_id, company_code, fiscal_year, fiscal_period, status, approved,
  created_at, agent_version, model_used.

BigQuery write pattern: INSERT new rows with new run_id every run —
NEVER TRUNCATE. The disclosure generator selects the latest approved
run, not the only run.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from gl_intelligence.persistence import supabase_available
from gl_intelligence.persistence.supabase_client import (
    DEFAULT_COMPANY_ID,
    get_supabase,
)


_DEFAULT_FISCAL_YEAR = os.environ.get("FISCAL_YEAR", "2024")
_DEFAULT_FISCAL_PERIOD = "Full Year"
_DEFAULT_COMPANY_CODE = os.environ.get("COMPANY_CODE", "C006")
_DEFAULT_MODEL = os.environ.get(
    "CLAUDE_MODEL", "apac.anthropic.claude-sonnet-4-5-20250929-v1:0"
)


@dataclass
class AgentInput:
    """Standard agent input parameters (Agent Contract Templates §1)."""
    company_code: str = _DEFAULT_COMPANY_CODE
    fiscal_year: str = _DEFAULT_FISCAL_YEAR
    fiscal_period: str = _DEFAULT_FISCAL_PERIOD
    run_id: Optional[str] = None
    dry_run: bool = False
    company_id: str = DEFAULT_COMPANY_ID  # Supabase FK; legacy company_code stays for BQ ↔ output naming
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentOutput:
    """Standard agent run summary, returned by every agent.run()."""
    run_id: str
    module: str
    rows_written: int = 0
    summary: dict[str, Any] = field(default_factory=dict)
    duration_ms: int = 0
    status: str = "draft"
    error: Optional[str] = None


class BaseFinanceAgent:
    """Base class. Subclasses implement `_execute(input)` and declare:
      MODULE         (str — the run_id prefix, e.g. 'cfo')
      DISPLAY_NAME   (str — human label)
      OUTPUT_TABLE   (str — primary Supabase table to write to)
      AGENT_VERSION  (str — semver)
      INPUT_TABLES   (list[str] — for documentation / Agent Contract §6)
      OUTPUT_TABLES  (list[str] — secondary outputs if multi-table)
      GCS_GROUNDING  (list[str] — GCS doc paths agents cite in prompts)

    The base class handles run_id generation, sequence tracking,
    standard-column injection on writes, and the agent_runs registry.
    """

    MODULE: str = "base"
    DISPLAY_NAME: str = "Base Agent"
    OUTPUT_TABLE: str = ""
    AGENT_VERSION: str = "v1.0.0"
    INPUT_TABLES: list[str] = []
    OUTPUT_TABLES: list[str] = []
    GCS_GROUNDING: list[str] = []
    MODEL: str = _DEFAULT_MODEL

    def __init__(self) -> None:
        self.log = logging.getLogger(f"finance_agents.{self.MODULE}")

    # ── Public entry point ───────────────────────────────────────────
    def run(self, params: Optional[AgentInput] = None, **kwargs) -> AgentOutput:
        params = params or AgentInput(**{k: v for k, v in kwargs.items() if k in AgentInput.__annotations__})
        if not params.run_id:
            seq = self._next_sequence(params)
            params.run_id = f"{self.MODULE}-{params.fiscal_year}-{seq:03d}"
        out = AgentOutput(run_id=params.run_id, module=self.MODULE)
        start = time.monotonic()
        try:
            self.log.info(
                "[%s] %s starting (company=%s fy=%s period=%s dry_run=%s)",
                params.run_id, self.DISPLAY_NAME,
                params.company_code, params.fiscal_year,
                params.fiscal_period, params.dry_run,
            )
            self._execute(params, out)
            out.duration_ms = int((time.monotonic() - start) * 1000)
            out.status = "draft"
            self._write_run_log(params, out)
            self.log.info(
                "[%s] %s ✓ rows=%d duration=%dms",
                params.run_id, self.DISPLAY_NAME, out.rows_written, out.duration_ms,
            )
            return out
        except Exception as exc:  # noqa: BLE001
            out.duration_ms = int((time.monotonic() - start) * 1000)
            out.status = "error"
            out.error = f"{type(exc).__name__}: {exc}"
            self.log.exception("[%s] %s failed: %s", params.run_id, self.DISPLAY_NAME, exc)
            self._write_run_log(params, out)
            return out

    # ── Subclass hook ────────────────────────────────────────────────
    def _execute(self, params: AgentInput, out: AgentOutput) -> None:
        raise NotImplementedError("subclass must implement _execute")

    # ── Helpers subclasses call ──────────────────────────────────────
    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _standard_columns(self, params: AgentInput) -> dict[str, Any]:
        """Returns the 9 standard output columns to merge into every row."""
        return {
            "run_id":        params.run_id,
            "company_code":  params.company_code,
            "fiscal_year":   params.fiscal_year,
            "fiscal_period": params.fiscal_period,
            "status":        "draft",
            "approved":      False,
            "agent_version": self.AGENT_VERSION,
            "model_used":    self.MODEL,
        }

    def write_rows(self, table: str, rows: list[dict], params: AgentInput) -> int:
        """Insert rows into a Supabase table with the standard columns
        merged in. NEVER truncates. Returns count actually written
        (0 in dry_run mode)."""
        if not rows:
            return 0
        if params.dry_run:
            self.log.info("[%s] dry_run — skipping write of %d rows to %s",
                          params.run_id, len(rows), table)
            return 0
        if not supabase_available():
            self.log.warning("[%s] Supabase unavailable — skipping write to %s",
                             params.run_id, table)
            return 0
        std = self._standard_columns(params)
        merged = [{**std, **r} for r in rows]
        try:
            get_supabase().table(table).insert(merged).execute()
            return len(merged)
        except Exception as e:
            self.log.error("[%s] write_rows(%s) failed: %s", params.run_id, table, e)
            raise

    def call_claude(self, system: str, prompt: str, max_tokens: int = 800) -> str:
        """Bedrock-routed Claude call. Empty string on failure (non-fatal)."""
        try:
            import anthropic  # type: ignore
            client = anthropic.AnthropicBedrock(
                aws_access_key=os.environ["AWS_ACCESS_KEY_ID"],
                aws_secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
                aws_region=os.environ.get("AWS_BEDROCK_REGION", "ap-south-1"),
            )
            res = client.messages.create(
                model=self.MODEL, max_tokens=max_tokens,
                system=system, messages=[{"role": "user", "content": prompt}],
            )
            return res.content[0].text.strip() if res.content else ""
        except Exception as e:  # noqa: BLE001
            self.log.warning("call_claude failed (non-fatal): %s", e)
            return ""

    def grounding_block(self) -> str:
        """Returns a system-prompt block listing the GCS docs this agent
        is grounded in (Agent Contract §6)."""
        if not self.GCS_GROUNDING:
            return ""
        bullets = "\n".join(f"- gs://gl-intelligence-docs/{d}" for d in self.GCS_GROUNDING)
        return (
            "GROUNDING — base every claim and citation on these documents:\n"
            f"{bullets}\n"
        )

    # ── Internals ────────────────────────────────────────────────────
    def _next_sequence(self, params: AgentInput) -> int:
        if not supabase_available():
            return 1
        try:
            res = get_supabase().rpc("next_agent_run_sequence", {
                "p_module":       self.MODULE,
                "p_fiscal_year":  params.fiscal_year,
                "p_company_code": params.company_code,
            }).execute()
            return int(res.data) if res.data else 1
        except Exception as e:
            self.log.warning("next_agent_run_sequence failed: %s — using 1", e)
            return 1

    def _write_run_log(self, params: AgentInput, out: AgentOutput) -> None:
        if params.dry_run or not supabase_available():
            return
        try:
            seq = int(params.run_id.rsplit("-", 1)[-1]) if "-" in (params.run_id or "") else 0
        except (ValueError, AttributeError):
            seq = 0
        try:
            get_supabase().table("agent_runs").insert({
                "run_id":        params.run_id,
                "module":        self.MODULE,
                "company_code":  params.company_code,
                "fiscal_year":   params.fiscal_year,
                "fiscal_period": params.fiscal_period,
                "sequence":      seq,
                "status":        out.status,
                "dry_run":       params.dry_run,
                "agent_version": self.AGENT_VERSION,
                "model_used":    self.MODEL,
                "input_summary": {
                    "company_code": params.company_code,
                    "fiscal_year":  params.fiscal_year,
                    "extra":        params.extra,
                },
                "output_summary": out.summary,
                "duration_ms":   out.duration_ms,
                "error":         out.error,
            }).execute()
        except Exception as e:
            self.log.warning("write agent_runs failed: %s", e)

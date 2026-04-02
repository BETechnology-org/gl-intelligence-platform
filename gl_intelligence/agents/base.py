"""
Base agent class — all financial agents inherit from this.
Provides Claude AI access, Cortex data tools, and audit logging.
"""

from __future__ import annotations

import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import anthropic

from gl_intelligence.config import cfg
from gl_intelligence.cortex.client import CortexClient

log = logging.getLogger("agents.base")

# ── Offline classified data (from Excel → Claude pipeline) ──
_offline_data_cache: list[dict] | None = None

def load_offline_data() -> list[dict]:
    """Load the 501 classified accounts from dise_full_mapping.json."""
    global _offline_data_cache
    if _offline_data_cache is not None:
        return _offline_data_cache
    import os
    paths = [
        os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS", "dise_full_mapping.json"),
        os.path.join(os.path.dirname(__file__), "..", "..", "FASB DISE ASSETS", "dise_mapping_results.json"),
        # Docker / container path
        "/app/data/dise_full_mapping.json",
        "/app/data/dise_mapping_results.json",
    ]
    for p in paths:
        try:
            with open(p) as f:
                data = json.load(f)
                _offline_data_cache = [d for d in data if d.get("suggested_category") and not d.get("error")]
                log.info(f"Loaded {len(_offline_data_cache)} classified accounts from {os.path.basename(p)}")
                return _offline_data_cache
        except (FileNotFoundError, json.JSONDecodeError):
            continue
    log.warning("No offline classified data found")
    _offline_data_cache = []
    return _offline_data_cache


@dataclass
class AgentResult:
    """Standardized result from any agent run."""
    agent_id: str
    status: str  # "success" | "partial" | "error"
    processed: int = 0
    errors: int = 0
    results: list[dict] = field(default_factory=list)
    summary: dict = field(default_factory=dict)
    started_at: str = ""
    completed_at: str = ""
    elapsed_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "status": self.status,
            "processed": self.processed,
            "errors": self.errors,
            "summary": self.summary,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "elapsed_seconds": self.elapsed_seconds,
            "result_count": len(self.results),
        }


class BaseAgent:
    """
    Abstract base for all financial agents.
    Subclasses implement run() with their specific workflow.
    """

    AGENT_ID: str = "BASE_AGENT"
    DESCRIPTION: str = "Base agent"

    def __init__(self, cortex: CortexClient | None = None):
        self.cx = cortex or CortexClient()
        self.claude = anthropic.Anthropic(api_key=cfg.ANTHROPIC_API_KEY)
        self.model = cfg.CLAUDE_MODEL
        self._run_id = str(uuid.uuid4())[:8]

    def run(self, **kwargs) -> AgentResult:
        """Override in subclass. Execute the agent's workflow."""
        raise NotImplementedError

    # ── Claude API ──────────────────────────────────────────

    def call_claude(self, system: str, user_prompt: str,
                    max_tokens: int = 1024, expect_json: bool = True) -> dict | str | None:
        """
        Call Claude with retry logic. If expect_json=True, parses response as JSON.
        Returns parsed dict, raw string, or None on failure.
        """
        for attempt in range(1, cfg.MAX_RETRIES + 2):
            try:
                response = self.claude.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user_prompt}],
                    timeout=60.0,
                )
                raw = response.content[0].text.strip()

                if not expect_json:
                    return raw

                # Strip markdown fences
                cleaned = self._strip_fences(raw)
                return json.loads(cleaned)

            except anthropic.RateLimitError:
                log.warning(f"Rate limited (attempt {attempt}), waiting...")
                time.sleep(5 * attempt)
            except anthropic.APIConnectionError as e:
                log.warning(f"API connection error (attempt {attempt}): {e}")
                time.sleep(2 ** attempt)
            except (json.JSONDecodeError, ValueError) as e:
                log.warning(f"Parse error (attempt {attempt}): {e}")
                if attempt > cfg.MAX_RETRIES:
                    log.error(f"Raw response: {raw[:500]}")
                time.sleep(1)
            except Exception as e:
                log.error(f"Unexpected error: {type(e).__name__}: {e}")
                return None

        return None

    # ── DISE Application Tables ─────────────────────────────

    # ── Offline Classified Data (Excel pipeline) ──────────

    def get_classified_accounts(self) -> list[dict]:
        """Returns the 501 accounts classified offline from the Excel data."""
        return load_offline_data()

    def get_classified_pivot(self) -> dict:
        """Build DISE pivot from offline classified data."""
        data = self.get_classified_accounts()
        pivot = {}
        for d in data:
            cat = d.get("suggested_category", "Other expenses")
            cap = d.get("suggested_caption", "SG&A")
            key = (cap, cat)
            pivot[key] = pivot.get(key, 0) + float(d.get("posting_amount", 0))
        return [{"expense_caption": k[0], "dise_category": k[1], "amount": v} for k, v in sorted(pivot.items())]

    def get_classified_by_category(self) -> dict[str, list[dict]]:
        """Group classified accounts by DISE category."""
        data = self.get_classified_accounts()
        groups = {}
        for d in data:
            cat = d.get("suggested_category", "Other expenses")
            groups.setdefault(cat, []).append(d)
        return groups

    # ── BigQuery DISE Tables (Max's 86 demo accounts) ─────

    def get_approved_mappings(self) -> list[dict]:
        """Returns all approved GL-to-DISE mappings. Falls back to offline data."""
        if not self.cx.available:
            return [{
                **a,
                "dise_category": a.get("suggested_category", ""),
                "expense_caption": a.get("suggested_caption", ""),
                "asc_citation": a.get("suggested_citation", ""),
                "status": "mapped",
            } for a in self.get_classified_accounts()]
        sql = f"""
        SELECT gl_account, description, dise_category, expense_caption, asc_citation, status, reviewer
        FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.gl_dise_mapping`
        WHERE status = 'mapped'
        ORDER BY gl_account
        """
        return self.cx.query(sql)

    def get_pending_mappings(self) -> list[dict]:
        """Returns all pending mapping decisions awaiting human review."""
        if not self.cx.available:
            return []
        sql = f"""
        SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.pending_mappings`
        WHERE status = 'PENDING'
        ORDER BY
          CASE materiality_flag WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END,
          confidence_score DESC
        """
        return self.cx.query(sql)

    def get_dise_pivot(self, fiscal_year: str | None = None) -> list[dict]:
        """Returns the live DISE pivot from the BigQuery view. Falls back to offline data."""
        if not self.cx.available:
            return self.get_classified_pivot()
        fy = fiscal_year or cfg.FISCAL_YEAR
        sql = f"""
        SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.v_dise_pivot`
        WHERE fiscal_year = @fy
        ORDER BY expense_caption, dise_category
        """
        return self.cx.query(sql, [self.cx.param("fy", "STRING", fy)])

    def get_close_tracker(self) -> list[dict]:
        """Returns current close task status."""
        if not self.cx.available:
            return []
        sql = f"""
        SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.v_close_tracker`
        ORDER BY sort_order
        """
        return self.cx.query(sql)

    def get_anomaly_alerts(self, status: str = "open") -> list[dict]:
        """Returns anomaly alerts."""
        if not self.cx.available:
            return []
        sql = f"""
        SELECT * FROM `{cfg.PROJECT}.{cfg.DISE_DATASET}.v_anomaly_alerts`
        WHERE status = @status
        """
        return self.cx.query(sql, [self.cx.param("status", "STRING", status)])

    def write_audit_event(self, event_type: str, gl_account: str, data: dict) -> None:
        """Writes an immutable event to the mapping_decisions_log."""
        row = {
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "event_timestamp": datetime.now(timezone.utc).isoformat(),
            "gl_account": gl_account,
            "actor": self.AGENT_ID,
            "actor_type": "AGENT",
            "model_version": self.model,
            **data,
        }
        errors = self.cx.insert_rows(
            f"{cfg.PROJECT}.{cfg.DISE_DATASET}.mapping_decisions_log", [row]
        )
        if errors:
            log.error(f"Audit log error: {errors}")

    # ── Utilities ───────────────────────────────────────────

    @staticmethod
    def _strip_fences(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            inner = parts[1] if len(parts) >= 3 else parts[1] if len(parts) > 1 else raw
            inner = re.sub(r"^[a-zA-Z]*\n?", "", inner, count=1)
            return inner.strip()
        return raw

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

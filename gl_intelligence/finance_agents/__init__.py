"""GL Intelligence finance agents — 9 specialized agents per the
April-2026 spec docs (Kyndryl Brief, India Onboarding, Cross-Agent
Architecture, Agent Contract Templates).

Six main agents (Cross-Agent Architecture):
  CFO, FP&A, Tax (Provision), Internal Audit, Accounting, IR

Three Phase-1 priority agents (India Team Onboarding):
  Close Tracker enhancement, ESG Emissions v2, ETR Narrative Drafter v2

Every agent obeys the standard contract (see Agent Contract Templates
doc): input parameters, output columns, run_id format, BigQuery write
pattern, GCS grounding, error handling, dry-run support.
"""

from .base import AgentInput, AgentOutput, BaseFinanceAgent
from .registry import (
    list_agents,
    get_agent,
    AGENT_MODULES,
    AGENT_DISPLAY_NAMES,
)

__all__ = [
    "AgentInput",
    "AgentOutput",
    "BaseFinanceAgent",
    "list_agents",
    "get_agent",
    "AGENT_MODULES",
    "AGENT_DISPLAY_NAMES",
]

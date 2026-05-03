"""Agent registry — single source of truth for which agents exist.

Maps `module` (the run_id prefix from the Agent Contract Templates §3)
to the concrete agent class. The Flask /api/finance/* routes use this.
"""

from __future__ import annotations

from typing import Type

from .accounting_agent import AccountingAgent
from .audit_agent import InternalAuditAgent
from .base import BaseFinanceAgent
from .cfo_agent import CFOAgent
from .close_tracker_agent import CloseTrackerAgent
from .esg_agent import ESGEmissionsAgent
from .etr_narrative_agent import ETRNarrativeDrafterAgent
from .fpa_agent import FPAAgent
from .ir_agent import IRAgent
from .tax_provision_agent import TaxProvisionAgent

# Registry keyed by URL slug. Multiple agents can share a `MODULE`
# prefix (e.g. close_tracker + accounting both use 'acct') but each
# slug is unique.
_AGENTS: dict[str, Type[BaseFinanceAgent]] = {
    "cfo":             CFOAgent,
    "fpa":             FPAAgent,
    "tax_provision":   TaxProvisionAgent,
    "audit":           InternalAuditAgent,
    "accounting":      AccountingAgent,
    "ir":              IRAgent,
    "close_tracker":   CloseTrackerAgent,
    "esg":             ESGEmissionsAgent,
    "etr_narrative":   ETRNarrativeDrafterAgent,
}

AGENT_MODULES = list(_AGENTS.keys())

# Phase 1 priorities first, then the 6 main agents (per the docs).
_DISPLAY_ORDER = [
    "close_tracker", "esg", "etr_narrative",
    "cfo", "fpa", "tax_provision", "audit", "accounting", "ir",
]

AGENT_DISPLAY_NAMES = {slug: cls.DISPLAY_NAME for slug, cls in _AGENTS.items()}


def list_agents() -> list[dict]:
    """Returns metadata for every registered agent (for /api/finance/agents)."""
    out = []
    for slug in _DISPLAY_ORDER:
        cls = _AGENTS[slug]
        out.append({
            "slug":          slug,
            "module":        cls.MODULE,
            "display_name":  cls.DISPLAY_NAME,
            "agent_version": cls.AGENT_VERSION,
            "input_tables":  cls.INPUT_TABLES,
            "output_tables": cls.OUTPUT_TABLES,
            "primary_output": cls.OUTPUT_TABLE,
            "gcs_grounding": cls.GCS_GROUNDING,
        })
    return out


def get_agent(slug: str) -> BaseFinanceAgent:
    if slug not in _AGENTS:
        raise ValueError(f"Unknown agent slug: {slug}. Known: {list(_AGENTS.keys())}")
    return _AGENTS[slug]()

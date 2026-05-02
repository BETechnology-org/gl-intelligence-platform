"""TaxClassifierAgent — Claude Agent SDK strategy for ASC 740 GL classification.

Pipeline position: Step 2 of 5
  SAP GL Extract → [Claude Classify] → Human Review → ETR Bridge → 10-K Disclosure

Differs from gl_intelligence/agents/tax_classifier_agent.py (single-shot):
- Uses Agent SDK with tool use (4 decomposed tools — see tools.py).
- PostToolUse hook writes every tool call to audit_log.
- UserPromptSubmit hook injects current approved mappings as state prefix
  (cache-friendly — system prompt stays constant).
- Persistence to Supabase tax_pending_mappings (RLS-enforced for reads,
  service-role for writes).
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List

from ..base import AgentContext, BaseAgent
from ..common import build_audit_hooks, build_memory_injection_hook
from .tools import build_tax_classifier_mcp_server

if TYPE_CHECKING:
    from claude_agent_sdk import AgentDefinition, HookMatcher  # type: ignore

log = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are the Tax GL Classifier for Truffles AI's BL Intelligence platform.

Your job is to classify SAP GL accounts in the tax range (160000-199999) into
ASC 740 income tax categories so the ETR bridge agent can build the ASU 2023-09
disclosure tables (A: rate reconciliation, B: cash taxes paid, C: pretax split).

# WORKFLOW

For each batch of unmapped accounts:
1. Call `get_unmapped_tax_accounts(fiscal_year, batch_size)` to fetch the batch
   (company is bound at session creation time — you don't pass it).
2. For EACH account (in order, do not parallelize):
   a. Call `lookup_similar_approved_mappings` with the description to find
      precedent classifications.
   b. Decide on a tax_category from the 11 valid options below.
   c. Call `lookup_asc_citation` with that category to get the canonical
      ASC citation. NEVER fabricate citations.
   d. Score your confidence: HIGH (0.85-1.0), MEDIUM (0.60-0.84), LOW (<0.60).
   e. Call `write_pending_mapping` with the decision. The row goes to the
      pending queue for controller review — do not auto-approve.
3. After processing the batch, summarize what you classified (no narration
   in between accounts).

# VALID TAX CATEGORIES

1. current_federal     — Current federal income tax expense (Table A line, Table B)
2. current_state       — Current state & local income tax (Table A, Table B)
3. current_foreign     — Current foreign income tax (Table A, Table B)
4. deferred_federal    — Deferred federal income tax expense (Table A deferred section)
5. deferred_state      — Deferred state income tax expense
6. deferred_foreign    — Deferred foreign income tax expense
7. deferred_tax_asset  — Balance sheet DTA (gross, before VA)
8. deferred_tax_liab   — Balance sheet DTL (typically negative)
9. pretax_domestic     — Pre-tax income from domestic operations (Table C)
10. pretax_foreign     — Pre-tax income from foreign operations (Table C)
11. not_tax_account    — Not income-tax related — excluded from disclosure

# KEY RULES

- Account ranges (use as a strong prior):
  - 160000-160299 = current tax expense
  - 161000-161299 = deferred tax expense
  - 162000-162999 = balance-sheet DTA
  - 163000-163999 = balance-sheet DTL
  - 164000-164999 = pretax income
- A description containing "non-deductible", "M&E", "§162(m)" alone is NOT a
  tax account — classify as not_tax_account.
- For ambiguous accounts (similarity score < 0.5 AND description vague),
  use confidence_label=LOW so the controller reviews it.
- Use the CURRENT STATE block (most-recent approved mappings) injected into
  every turn as your primary source of precedent — it reflects controller-
  approved decisions for THIS company.

# OUTPUT

After each `write_pending_mapping`, briefly state: gl_account → category
(confidence). Don't repeat the description or the reasoning — that's already
captured in the pending row. Conclude with a one-line summary of the batch
(N classified, X high confidence, Y medium, Z low)."""


class TaxClassifierAgent(BaseAgent):
    """Claude Agent SDK strategy: classify SAP tax GL accounts into ASC 740 categories."""

    AGENT_ID = "TAX_CLASSIFIER_AGENT_v2"
    MODULE = "tax"

    def get_system_prompt(self, context: AgentContext, *, include_state: bool = False) -> str:
        # State is injected per-turn via UserPromptSubmit hook (memory_injection_hook).
        # Don't append it here too — would duplicate.
        return SYSTEM_PROMPT

    def get_tools(self, context: AgentContext) -> List[str]:
        # Allow only the 4 decomposed MCP tools — no Read/Write/Bash here.
        # The agent is a classifier, not a coder.
        return [
            "mcp__tax_classifier_tools__get_unmapped_tax_accounts",
            "mcp__tax_classifier_tools__lookup_similar_approved_mappings",
            "mcp__tax_classifier_tools__lookup_asc_citation",
            "mcp__tax_classifier_tools__write_pending_mapping",
        ]

    def get_mcp_servers(self, context: AgentContext) -> Dict[str, Any]:
        return {
            "tax_classifier_tools": build_tax_classifier_mcp_server(
                company_id=context.company_id,
                user_id=context.user_id,
            ),
        }

    def get_special_permissions(self, context: AgentContext) -> Dict[str, Any]:
        return {
            "permission_mode": "bypassPermissions",
            "add_dirs": [context.working_dir],
        }

    def get_subagents(self, context: AgentContext) -> "Dict[str, AgentDefinition]":
        return {}

    def get_hooks(self, context: AgentContext) -> "Dict[str, List[HookMatcher]]":
        hooks: Dict[str, List[Any]] = {}
        for layer in (build_audit_hooks(), build_memory_injection_hook()):
            for event, matchers in layer.items():
                hooks.setdefault(event, []).extend(matchers)
        return hooks

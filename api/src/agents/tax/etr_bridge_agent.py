"""ETRBridgeAgent — Phase 2 (placeholder).

Will aggregate approved tax mappings into ASU 2023-09 Tables A, B, C
using decomposed deterministic tools (compute_pretax_split, compute_rate_recon_line,
check_jurisdictional_threshold, compute_state_majority, lookup_asc_citation).

See gl_intelligence/agents/etr_bridge_agent.py for the legacy single-shot version.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from ..base import AgentContext, BaseAgent

if TYPE_CHECKING:
    from claude_agent_sdk import AgentDefinition, HookMatcher  # type: ignore


class ETRBridgeAgent(BaseAgent):
    AGENT_ID = "ETR_BRIDGE_AGENT_v2"
    MODULE = "tax"

    def get_system_prompt(self, context: AgentContext, *, include_state: bool = False) -> str:
        return "ETRBridgeAgent — not yet implemented (Phase 2)."

    def get_tools(self, context: AgentContext) -> List[str]:
        return []

    def get_mcp_servers(self, context: AgentContext) -> Dict[str, Any]:
        return {}

    def get_special_permissions(self, context: AgentContext) -> Dict[str, Any]:
        return {"permission_mode": "default"}

    def get_subagents(self, context: AgentContext) -> "Dict[str, AgentDefinition]":
        return {}

    def get_hooks(self, context: AgentContext) -> "Dict[str, List[HookMatcher]]":
        return {}

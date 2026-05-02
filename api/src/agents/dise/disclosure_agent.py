"""DISEDisclosureAgent — Phase 3 placeholder."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from ..base import AgentContext, BaseAgent

if TYPE_CHECKING:
    from claude_agent_sdk import AgentDefinition, HookMatcher  # type: ignore


class DISEDisclosureAgent(BaseAgent):
    AGENT_ID = "DISE_DISCLOSURE_AGENT_v2"
    MODULE = "dise"

    def get_system_prompt(self, context: AgentContext, *, include_state: bool = False) -> str:
        return "DISEDisclosureAgent — not yet implemented (Phase 3)."

    def get_tools(self, context: AgentContext) -> List[str]: return []
    def get_mcp_servers(self, context: AgentContext) -> Dict[str, Any]: return {}
    def get_special_permissions(self, context: AgentContext) -> Dict[str, Any]:
        return {"permission_mode": "default"}
    def get_subagents(self, context: AgentContext) -> "Dict[str, AgentDefinition]": return {}
    def get_hooks(self, context: AgentContext) -> "Dict[str, List[HookMatcher]]": return {}

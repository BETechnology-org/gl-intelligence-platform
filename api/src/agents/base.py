"""BaseAgent Protocol — copied from claude-code-sdk-1/src/agents/base.py.

Each domain agent (tax_classifier, etr_bridge, mapping, etc.) implements
this Protocol. The session worker reads `get_system_prompt`, `get_tools`,
`get_mcp_servers`, `get_special_permissions`, `get_subagents`, `get_hooks`
and passes them to ClaudeAgentOptions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Protocol

if TYPE_CHECKING:
    from claude_agent_sdk import AgentDefinition, HookMatcher  # type: ignore


@dataclass
class AgentContext:
    """Runtime context passed to every agent strategy method."""
    job_id: str
    user_id: str
    company_id: str
    fiscal_year: str
    working_dir: str
    metadata: Optional[Dict[str, Any]] = None


class BaseAgent(Protocol):
    """Strategy interface. See claude-code-sdk-1/src/agents/general/agent.py for a model implementation."""

    def get_system_prompt(self, context: AgentContext, *, include_state: bool = False) -> str:
        ...

    def get_tools(self, context: AgentContext) -> List[str]:
        ...

    def get_mcp_servers(self, context: AgentContext) -> Dict[str, Any]:
        ...

    def get_special_permissions(self, context: AgentContext) -> Dict[str, Any]:
        ...

    def get_subagents(self, context: AgentContext) -> "Dict[str, AgentDefinition]":
        ...

    def get_hooks(self, context: AgentContext) -> "Dict[str, List[HookMatcher]]":
        return {}

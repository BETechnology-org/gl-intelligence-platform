"""Agent strategies — DISE + Tax + shared tools/hooks."""

from .base import AgentContext, BaseAgent
from .registry import AgentRegistry, get_agent

__all__ = ["AgentContext", "BaseAgent", "AgentRegistry", "get_agent"]

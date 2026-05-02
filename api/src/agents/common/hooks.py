"""Cross-cutting hooks attached to every agent.

- build_audit_hooks(): PostToolUse → write each tool call to audit_log.
- build_memory_injection_hook(): UserPromptSubmit → inject current
  approved-mappings state prefix without busting prompt cache.

Pattern lifted from claude-code-sdk-1/src/agents/common/memory_injection.py.
The cache breakpoint sits BEFORE the user message, so memory injection
on UserPromptSubmit doesn't invalidate the system prompt cache.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .. import db_helpers  # type: ignore  # local import — see helpers below
from ...config import settings
from ...db import audit  # type: ignore

log = logging.getLogger(__name__)


# Defer SDK imports to runtime so the package is importable without claude_agent_sdk
def _hook_matcher_factory():
    from claude_agent_sdk import HookMatcher  # type: ignore
    return HookMatcher


# ── Audit hooks ────────────────────────────────────────────────────────


async def _post_tool_use_audit(
    input_data: Dict[str, Any],
    tool_use_id: Optional[str],
    context: Any,
) -> Dict[str, Any]:
    """PostToolUse → append a TOOL_USE row to audit_log."""
    try:
        ctx = getattr(context, "agent_context", None)
        if ctx is None:
            return {}
        await audit.write(
            company_id=ctx.company_id,
            module=getattr(context, "module", "platform"),
            event_type="TOOL_USE",
            actor=getattr(context, "agent_id", "unknown_agent"),
            actor_type="AGENT",
            user_id=ctx.user_id,
            fiscal_year=ctx.fiscal_year,
            tool_name=input_data.get("tool_name"),
            tool_input=input_data.get("tool_input"),
            tool_result=input_data.get("tool_response"),
            payload={"tool_use_id": tool_use_id},
        )
    except Exception as e:
        log.warning("audit hook failed (non-fatal): %s", e)
    return {}


def build_audit_hooks() -> Dict[str, List[Any]]:
    HookMatcher = _hook_matcher_factory()
    return {"PostToolUse": [HookMatcher(hooks=[_post_tool_use_audit])]}


# ── Memory injection (state prefix per turn) ──────────────────────────


async def _inject_state_prefix(
    input_data: Dict[str, Any],
    tool_use_id: Optional[str],
    context: Any,
) -> Dict[str, Any]:
    """UserPromptSubmit → append a CURRENT STATE block from Supabase.

    Reads the most recent approved mappings for the company so the agent
    has up-to-date reference material on every turn — without changing
    the system prompt (cache stays warm).
    """
    try:
        ctx = getattr(context, "agent_context", None)
        if ctx is None:
            return {}
        block = await db_helpers.build_state_prefix(
            company_id=ctx.company_id,
            fiscal_year=ctx.fiscal_year,
            module=getattr(context, "module", "tax"),
        )
        if not block:
            return {}
        return {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": block,
            }
        }
    except Exception as e:
        log.warning("memory injection hook failed (non-fatal): %s", e)
        return {}


def build_memory_injection_hook() -> Dict[str, List[Any]]:
    HookMatcher = _hook_matcher_factory()
    return {"UserPromptSubmit": [HookMatcher(hooks=[_inject_state_prefix])]}

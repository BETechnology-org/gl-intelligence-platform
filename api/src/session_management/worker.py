"""Session worker — runs a Claude Agent SDK client and streams events.

Phase 1 pattern: connect → drain input queue → stream → disconnect. No
1-hour idle reuse yet (Phase 2). The agent strategy is selected from
the registry by `ctx.agent_type`.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Optional

from ..agents import AgentContext, get_agent
from ..config import settings
from .types import QueryItem, SessionContext

log = logging.getLogger(__name__)

IDLE_TIMEOUT_SECONDS = 600  # 10 min for v1 (vs 3600s in sdk-1)


async def run_session_worker(ctx: SessionContext) -> None:
    """Long-running task that owns one ClaudeSDKClient for a job.

    Lifecycle:
      1. Resolve agent strategy from ctx.agent_type
      2. Build ClaudeAgentOptions from strategy
      3. Connect once, process queries from input queue
      4. Disconnect on idle timeout / cancel
    """
    from claude_agent_sdk import (  # type: ignore
        AssistantMessage,
        ClaudeAgentOptions,
        ClaudeSDKClient,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
    )

    job_id = ctx.job_id
    client: Optional[ClaudeSDKClient] = None
    log.info("[%s] worker starting (agent=%s)", job_id, ctx.agent_type)

    try:
        agent = get_agent(ctx.agent_type)
        agent_ctx = AgentContext(
            job_id=ctx.job_id,
            user_id=ctx.user_id,
            company_id=ctx.company_id,
            fiscal_year=ctx.fiscal_year,
            working_dir=ctx.working_dir,
            metadata=ctx.metadata,
        )

        options_kwargs: dict[str, Any] = {
            "system_prompt": agent.get_system_prompt(agent_ctx),
            "allowed_tools": agent.get_tools(agent_ctx),
            "mcp_servers": agent.get_mcp_servers(agent_ctx),
            "hooks": agent.get_hooks(agent_ctx),
            "max_turns": settings.claude_max_turns,
            "model": settings.claude_model,
        }
        special = agent.get_special_permissions(agent_ctx)
        if "permission_mode" in special:
            options_kwargs["permission_mode"] = special["permission_mode"]
        if "add_dirs" in special:
            options_kwargs["add_dirs"] = special["add_dirs"]
        if subagents := agent.get_subagents(agent_ctx):
            options_kwargs["agents"] = subagents

        options = ClaudeAgentOptions(**options_kwargs)
        client = ClaudeSDKClient(options=options)
        await client.connect()
        ctx.client = client
        log.info("[%s] connected to Claude SDK", job_id)

        while True:
            try:
                item: QueryItem = await asyncio.wait_for(
                    ctx.input_queue.get(), timeout=IDLE_TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                log.info("[%s] idle timeout reached", job_id)
                break

            ctx.is_processing = True
            ctx.query_started_at = time.time()

            try:
                await client.query(item.prompt)
                async for msg in client.receive_response():
                    event = _msg_to_event(msg)
                    if event:
                        await item.response_queue.put(event)
                    if isinstance(msg, ResultMessage):
                        break
            except asyncio.CancelledError:
                await item.response_queue.put({"type": "cancelled", "reason": "task_cancelled"})
                raise
            except Exception as e:
                log.exception("[%s] query failed: %s", job_id, e)
                await item.response_queue.put({"type": "error", "message": str(e)})
            finally:
                await item.response_queue.put({"type": "done"})
                await item.response_queue.put(None)  # sentinel for SSE generator
                ctx.is_processing = False
                ctx.query_started_at = None
                ctx.last_activity = time.time()

    except asyncio.CancelledError:
        log.info("[%s] worker cancelled", job_id)
        raise
    except Exception as e:
        log.exception("[%s] worker fatal: %s", job_id, e)
    finally:
        if client is not None:
            try:
                await client.disconnect()
            except Exception:
                pass
        log.info("[%s] worker exit", job_id)


def _msg_to_event(msg: Any) -> dict | None:
    """Convert Claude SDK message types into SSE-friendly dicts."""
    from claude_agent_sdk import (  # type: ignore
        AssistantMessage,
        ResultMessage,
        SystemMessage,
        TextBlock,
        ThinkingBlock,
        ToolResultBlock,
        ToolUseBlock,
    )

    if isinstance(msg, SystemMessage):
        return {"type": "system", "subtype": getattr(msg, "subtype", None)}

    if isinstance(msg, AssistantMessage):
        blocks = []
        for b in msg.content:
            if isinstance(b, TextBlock):
                blocks.append({"type": "text", "text": b.text})
            elif isinstance(b, ThinkingBlock):
                blocks.append({"type": "thinking", "text": b.thinking})
            elif isinstance(b, ToolUseBlock):
                blocks.append({
                    "type": "tool_use",
                    "id": b.id,
                    "name": b.name,
                    "input": b.input,
                })
            elif isinstance(b, ToolResultBlock):
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": b.tool_use_id,
                    "content": b.content,
                    "is_error": b.is_error,
                })
        return {"type": "assistant", "blocks": blocks}

    if isinstance(msg, ResultMessage):
        return {
            "type": "result",
            "subtype": msg.subtype,
            "duration_ms": msg.duration_ms,
            "duration_api_ms": msg.duration_api_ms,
            "num_turns": msg.num_turns,
            "total_cost_usd": msg.total_cost_usd,
            "session_id": msg.session_id,
        }

    return None

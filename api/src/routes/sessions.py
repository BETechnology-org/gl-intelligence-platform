"""Session management routes — SSE streaming, status, cancel, replay.

Mirrors the streaming roadmap from claude-code-sdk-1/AGENT_STREAMING_ROADMAP.md.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from ..auth import CurrentUser
from ..services.session_service import session_service

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status/{job_id}")
async def session_status(job_id: str, user: CurrentUser) -> dict:
    info = session_service.session_manager.get_session_info(job_id)
    if info is None:
        return {"job_id": job_id, "worker_alive": False, "is_processing": False}
    if info["user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="not authorized for this session")
    return {
        "job_id": job_id,
        "worker_alive": info["task_alive"],
        "is_processing": info.get("is_processing", False),
        "queue_depth": info["queue_size"],
        "elapsed_ms": info.get("elapsed_ms"),
    }


@router.post("/cancel/{job_id}")
async def session_cancel(job_id: str, user: CurrentUser) -> dict:
    info = session_service.session_manager.get_session_info(job_id)
    if info is None:
        raise HTTPException(status_code=404, detail="no active session")
    if info["user_id"] != user.user_id:
        raise HTTPException(status_code=403, detail="not authorized")
    cancelled = await session_service.session_manager.cancel(job_id, reason="user_cancel")
    return {"cancelled": cancelled, "job_id": job_id}


async def _sse_generator(response_queue) -> Any:
    """Drain the response queue and emit SSE events."""
    while True:
        event = await response_queue.get()
        if event is None:
            break
        yield {"event": event.get("type", "message"), "data": event}
        if event.get("type") in ("done", "cancelled", "error"):
            break


@router.post("/{job_id}/stream")
async def session_stream(job_id: str, body: dict, user: CurrentUser):
    """Open SSE stream for a session. Body: {"agent_type": "...", "prompt": "..."}."""
    agent_type = body.get("agent_type")
    prompt = body.get("prompt")
    if not agent_type or not prompt:
        raise HTTPException(status_code=400, detail="agent_type and prompt required")

    response_queue = await session_service.submit(
        job_id=job_id,
        user_id=user.user_id,
        agent_type=agent_type,
        prompt=prompt,
        metadata=body.get("metadata"),
    )

    return EventSourceResponse(_sse_generator(response_queue))

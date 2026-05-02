"""SessionManager — per-job worker registry with cancel + status.

Phase 1: one worker per job_id, shorter idle timeout, no replay buffer.
Phase 2: lift the full pattern from claude-code-sdk-1/src/session_management/manager.py.
"""

from __future__ import annotations

import asyncio
import logging
import time
from asyncio import Queue
from typing import Any, Dict, Optional, Tuple

from .types import QueryItem, SessionContext
from .worker import run_session_worker

log = logging.getLogger(__name__)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, SessionContext] = {}
        self._lock = asyncio.Lock()
        log.info("SessionManager initialized")

    async def submit_query(
        self,
        *,
        job_id: str,
        user_id: str,
        company_id: str,
        fiscal_year: str,
        agent_type: str,
        prompt: str,
        working_dir: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Queue, bool]:
        async with self._lock:
            ctx = self._sessions.get(job_id)
            is_new = ctx is None or (ctx.task and ctx.task.done())
            if is_new:
                ctx = SessionContext(
                    job_id=job_id,
                    user_id=user_id,
                    company_id=company_id,
                    fiscal_year=fiscal_year,
                    agent_type=agent_type,
                    working_dir=working_dir,
                    metadata=metadata,
                    input_queue=Queue(maxsize=10),
                )
                ctx.task = asyncio.create_task(run_session_worker(ctx))
                self._sessions[job_id] = ctx
                log.info("[%s] Created worker (agent_type=%s)", job_id, agent_type)
            else:
                if ctx.user_id != user_id:
                    raise ValueError(f"Session {job_id} belongs to a different user")
                log.info("[%s] Reusing worker", job_id)

        response_queue: Queue = Queue()
        try:
            await asyncio.wait_for(
                ctx.input_queue.put(QueryItem(prompt=prompt, response_queue=response_queue)),
                timeout=5.0,
            )
        except asyncio.TimeoutError as exc:
            raise ValueError("Session queue full — try again shortly") from exc

        ctx.last_activity = time.time()
        return response_queue, is_new

    def get_session_info(self, job_id: str) -> Optional[Dict[str, Any]]:
        ctx = self._sessions.get(job_id)
        if not ctx:
            return None
        return {
            "job_id": ctx.job_id,
            "user_id": ctx.user_id,
            "company_id": ctx.company_id,
            "agent_type": ctx.agent_type,
            "task_alive": bool(ctx.task and not ctx.task.done()),
            "queue_size": ctx.input_queue.qsize(),
            "is_processing": ctx.is_processing,
            "elapsed_ms": (
                int((time.time() - ctx.query_started_at) * 1000)
                if ctx.query_started_at
                else None
            ),
        }

    async def cancel(self, job_id: str, reason: str = "user_cancel") -> bool:
        ctx = self._sessions.get(job_id)
        if not ctx or not ctx.task or ctx.task.done():
            return False
        log.info("[%s] cancel requested (%s)", job_id, reason)
        if ctx.client is not None:
            try:
                await ctx.client.interrupt()  # type: ignore[func-returns-value]
            except Exception as e:
                log.warning("[%s] interrupt() failed: %s", job_id, e)
        ctx.task.cancel()
        return True

    async def shutdown_all(self) -> None:
        log.info("Shutting down all sessions...")
        async with self._lock:
            tasks = [c.task for c in self._sessions.values() if c.task and not c.task.done()]
            for t in tasks:
                t.cancel()
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
            self._sessions.clear()

    def get_active_session_count(self) -> int:
        return len(self._sessions)

"""Session service singleton — entrypoint for /api/sessions/* routes."""

from __future__ import annotations

import logging
import os
from asyncio import Queue
from pathlib import Path

from ..config import settings
from ..session_management import SessionManager

log = logging.getLogger(__name__)


class SessionService:
    def __init__(self) -> None:
        self.session_manager = SessionManager()
        self.sessions_root = Path(settings.sessions_root_dir)
        self.sessions_root.mkdir(parents=True, exist_ok=True)

    async def submit(
        self,
        *,
        job_id: str,
        user_id: str,
        agent_type: str,
        prompt: str,
        company_id: str | None = None,
        fiscal_year: str | None = None,
        metadata: dict | None = None,
    ) -> Queue:
        working_dir = self.sessions_root / job_id
        working_dir.mkdir(parents=True, exist_ok=True)

        # Side-channel for hooks that need user_id (memory_injection pattern).
        (working_dir / ".session-info.json").write_text(
            f'{{"user_id": "{user_id}", "company_id": "{company_id or ""}", "agent_type": "{agent_type}"}}'
        )

        queue, _ = await self.session_manager.submit_query(
            job_id=job_id,
            user_id=user_id,
            company_id=company_id or "",
            fiscal_year=fiscal_year or settings.environment,
            agent_type=agent_type,
            prompt=prompt,
            working_dir=str(working_dir),
            metadata=metadata,
        )
        return queue

    async def shutdown_all(self) -> None:
        await self.session_manager.shutdown_all()


session_service = SessionService()

"""Session context types — minimal Phase-1 shape.

Phase 2 will extend with replay_buffer, last_event_seq, validation_retries
(see claude-code-sdk-1/src/session_management/types.py for the full version).
"""

from __future__ import annotations

import asyncio
import time
from asyncio import Queue
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from claude_agent_sdk import ClaudeSDKClient  # type: ignore


@dataclass
class SessionContext:
    job_id: str
    user_id: str
    company_id: str
    fiscal_year: str
    agent_type: str
    working_dir: str
    metadata: Optional[Dict[str, Any]] = None
    input_queue: Queue = field(default_factory=Queue)
    last_activity: float = field(default_factory=time.time)
    task: Optional[asyncio.Task] = None
    client: Optional["ClaudeSDKClient"] = None
    is_processing: bool = False
    query_started_at: Optional[float] = None


@dataclass
class QueryItem:
    prompt: str
    response_queue: Queue
    submitted_at: float = field(default_factory=time.time)

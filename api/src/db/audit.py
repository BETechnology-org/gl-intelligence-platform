"""Append-only audit log writer.

All agent runs and human review actions write at least:
  - module: 'dise' | 'tax' | 'platform'
  - event_type: AGENT_DRAFT / TOOL_USE / HUMAN_APPROVED / etc.
  - actor / actor_type
  - payload (JSONB)

Writes go through the service-role client (bypasses RLS), but each row
is tagged with the acting user_id so RLS reads still work.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from .supabase import get_supabase_admin

log = logging.getLogger(__name__)


async def write(
    *,
    company_id: UUID | str,
    module: str,
    event_type: str,
    actor: str,
    actor_type: str,
    user_id: UUID | str | None = None,
    gl_account: str | None = None,
    fiscal_year: str | None = None,
    pending_id: UUID | str | None = None,
    approved_id: UUID | str | None = None,
    model_version: str | None = None,
    prompt_version: str | None = None,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_result: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Append one audit_log row. Non-fatal on failure (logs and continues)."""
    row: dict[str, Any] = {
        "company_id": str(company_id),
        "module": module,
        "event_type": event_type,
        "actor": actor,
        "actor_type": actor_type,
        "payload": payload or {},
    }
    optional = {
        "user_id": str(user_id) if user_id else None,
        "gl_account": gl_account,
        "fiscal_year": fiscal_year,
        "pending_id": str(pending_id) if pending_id else None,
        "approved_id": str(approved_id) if approved_id else None,
        "model_version": model_version,
        "prompt_version": prompt_version,
        "tool_name": tool_name,
        "tool_input": tool_input,
        "tool_result": tool_result,
    }
    for k, v in optional.items():
        if v is not None:
            row[k] = v

    try:
        get_supabase_admin().table("audit_log").insert(row).execute()
    except Exception as e:
        log.error("audit_log insert failed (non-fatal): %s | row=%s", e, event_type)

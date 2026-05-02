"""Append-only audit log writer.

Every agent action and human review decision lands a row in the
public.audit_log table (created by migrations/supabase/0001). Writes
go through the service-role client. Failures are non-fatal — the
agent continues even if the audit write errors out (logged for
operational visibility).
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from .supabase_client import DEFAULT_COMPANY_ID, get_supabase

log = logging.getLogger("persistence.audit")


def write_audit_event(
    *,
    module: str,                       # 'dise' | 'tax' | 'platform'
    event_type: str,                   # AGENT_DRAFT / HUMAN_APPROVED / TOOL_USE / ...
    actor: str,
    actor_type: str,                   # 'AGENT' | 'HUMAN' | 'SYSTEM'
    company_id: Optional[str] = None,
    user_id: Optional[str] = None,
    gl_account: Optional[str] = None,
    fiscal_year: Optional[str] = None,
    pending_id: Optional[str] = None,
    approved_id: Optional[str] = None,
    model_version: Optional[str] = None,
    prompt_version: Optional[str] = None,
    tool_name: Optional[str] = None,
    tool_input: Optional[dict[str, Any]] = None,
    tool_result: Optional[dict[str, Any]] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Append one audit_log row. Non-fatal on failure."""
    sb = get_supabase()
    if sb is None:
        return  # Supabase not configured; legacy state path is the source of truth.

    row: dict[str, Any] = {
        "company_id": company_id or DEFAULT_COMPANY_ID,
        "module": module,
        "event_type": event_type,
        "actor": actor,
        "actor_type": actor_type,
        "payload": payload or {},
    }
    optional = {
        "user_id": user_id,
        "gl_account": gl_account,
        "fiscal_year": fiscal_year,
        "pending_id": pending_id,
        "approved_id": approved_id,
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
        sb.table("audit_log").insert(row).execute()
    except Exception as e:  # noqa: BLE001
        log.error("audit_log insert failed (non-fatal): %s | event=%s", e, event_type)
